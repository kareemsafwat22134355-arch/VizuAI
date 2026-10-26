from monter_bridge.audio_mix_models import AudioMixAudit
from monter_bridge.critic_models import CriticFinding, CriticMetric, CriticReport
from monter_bridge.final_critic import build_final_critic
from monter_bridge.render_analysis_models import RenderAnalysisFinding, RenderAnalysisReport


def editorial(status="pass", findings=None):
    return CriticReport(
        project_id="p",
        status=status,
        metrics=[CriticMetric(name="mean_energy_error", value=.2, target="<= .3", passed=True)],
        findings=findings or [],
        notes=[],
    )


def render_report(status="pass", findings=None):
    return RenderAnalysisReport(
        project_id="p",
        path_label="rough-cut.mp4",
        status=status,
        duration_seconds=4,
        expected_duration_seconds=4,
        duration_drift_seconds=0,
        has_audio=False,
        sampled_frames=16,
        mean_motion=.4,
        peak_motion=1,
        black_frame_fraction=0,
        freeze_pair_fraction=.1,
        longest_freeze_seconds=.25,
        energy_alignment=.72,
        energy_bins=[],
        findings=findings or [],
        notes=[],
    )


def test_final_critic_marks_supported_editorial_replacement_as_automatic_candidate():
    report = build_final_critic(editorial(
        status="needs_revision",
        findings=[CriticFinding(
            code="energy_mismatch",
            severity="warning",
            segment_id="s1",
            message="energy differs",
        )],
    ))

    assert report.status == "needs_revision"
    assert report.automatic_revision_candidates == 1
    assert report.findings[0].domain == "editorial"
    assert report.findings[0].reviseability == "automatic_candidate"


def test_render_integrity_error_overrides_editorial_pass_and_remains_manual_only():
    render = render_report(
        status="needs_review",
        findings=[RenderAnalysisFinding(
            code="duration_drift",
            severity="error",
            message="encoded duration is wrong",
        )],
    )
    report = build_final_critic(editorial(), render_analysis=render)

    finding = next(item for item in report.findings if item.code == "duration_drift")
    assert report.status == "needs_review"
    assert finding.domain == "render_integrity"
    assert finding.reviseability == "manual_only"
    assert report.automatic_revision_candidates == 0


def test_audio_headroom_failure_is_manual_integrity_review():
    audit = AudioMixAudit(
        path_label="rough-cut.mp4",
        mean_volume_dbfs=-8,
        max_volume_dbfs=-0.1,
        clipping_safe=False,
        safety_threshold_dbfs=-0.5,
        notes=[],
    )
    report = build_final_critic(editorial(), audio_audit=audit)

    finding = next(item for item in report.findings if item.code == "audio_headroom_failure")
    assert report.status == "needs_review"
    assert finding.domain == "audio_integrity"
    assert finding.reviseability == "manual_only"


def test_warning_only_render_evidence_does_not_turn_pass_into_failure():
    render = render_report(
        status="pass",
        findings=[RenderAnalysisFinding(
            code="long_freeze_span",
            severity="warning",
            message="review intentional freeze",
        )],
    )
    report = build_final_critic(editorial(), render_analysis=render)

    assert report.status == "pass"
    assert report.manual_review_findings == 1
