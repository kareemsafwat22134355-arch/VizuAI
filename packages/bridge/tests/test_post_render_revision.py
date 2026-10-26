from pathlib import Path

from monter_bridge.critic_models import CriticFinding, CriticMetric, CriticReport
from monter_bridge.final_critic_models import FinalCriticFinding, FinalCriticReport
from monter_bridge.post_render_revision import (
    _promote_candidate,
    _snapshot_baseline,
    filter_automatic_editorial_critic,
    should_attempt_post_render_revision,
)


def editorial(findings=None):
    return CriticReport(
        project_id="p",
        status="needs_revision",
        metrics=[CriticMetric(name="mean_energy_error", value=.4, target="<= .3", passed=False)],
        findings=findings or [],
        notes=[],
    )


def final(status="needs_revision", findings=None, automatic=1):
    return FinalCriticReport(
        project_id="p",
        status=status,
        automatic_revision_candidates=automatic,
        manual_review_findings=0,
        metrics=[],
        findings=findings or [],
        notes=[],
    )


def test_post_render_revision_requires_needs_revision_and_automatic_candidate():
    assert should_attempt_post_render_revision(final()) is True
    assert should_attempt_post_render_revision(final(status="pass")) is False
    assert should_attempt_post_render_revision(final(automatic=0)) is False


def test_integrity_error_blocks_edit_mutation_even_when_editorial_candidate_exists():
    report = final(findings=[
        FinalCriticFinding(
            code="near_black_render",
            domain="render_integrity",
            severity="error",
            reviseability="manual_only",
            message="blank",
            source_artifact="render-analysis.json",
        )
    ])
    assert should_attempt_post_render_revision(report) is False


def test_filter_passes_only_supported_automatic_editorial_findings():
    source = editorial(findings=[
        CriticFinding(code="energy_mismatch", severity="warning", segment_id="s1", message="replaceable"),
        CriticFinding(code="transition_repetition", severity="warning", message="manual"),
    ])
    consolidated = final(findings=[
        FinalCriticFinding(
            code="energy_mismatch",
            domain="editorial",
            severity="warning",
            reviseability="automatic_candidate",
            message="replaceable",
            source_artifact="critic-report.json",
            segment_id="s1",
        ),
        FinalCriticFinding(
            code="transition_repetition",
            domain="editorial",
            severity="warning",
            reviseability="manual_only",
            message="manual",
            source_artifact="critic-report.json",
        ),
    ])

    filtered = filter_automatic_editorial_critic(source, consolidated)
    assert filtered.status == "needs_revision"
    assert [finding.code for finding in filtered.findings] == ["energy_mismatch"]
    assert filtered.findings[0].segment_id == "s1"


def test_filter_preserves_boundary_identity_for_motion_match_trim_realign():
    source = editorial(findings=[CriticFinding(
        code="motion_match_timing_weak",
        severity="warning",
        boundary_index=2,
        message="recoverable boundary timing",
    )])
    consolidated = final(findings=[FinalCriticFinding(
        code="motion_match_timing_weak",
        domain="editorial",
        severity="warning",
        reviseability="automatic_candidate",
        message="recoverable boundary timing",
        source_artifact="critic-report.json",
        boundary_index=2,
    )])

    filtered = filter_automatic_editorial_critic(source, consolidated)
    assert filtered.status == "needs_revision"
    assert len(filtered.findings) == 1
    assert filtered.findings[0].code == "motion_match_timing_weak"
    assert filtered.findings[0].boundary_index == 2
    assert filtered.findings[0].segment_id is None


def test_candidate_promotion_snapshots_baseline_and_ignores_stale_candidate_files(tmp_path: Path):
    work = tmp_path / ".monter"
    work.mkdir()
    candidate = work / "post-render-candidate-01"
    candidate.mkdir()
    baseline = work / "post-render-baseline"

    (work / "edit-plan.json").write_text("baseline-edit", encoding="utf-8")
    (work / "ctl.json").write_text("baseline-ctl", encoding="utf-8")
    (candidate / "edit-plan.json").write_text("candidate-edit", encoding="utf-8")
    (candidate / "ctl.json").write_text("candidate-ctl", encoding="utf-8")

    copied = _snapshot_baseline(work, baseline)
    promoted = _promote_candidate(candidate, work)

    assert {"edit-plan.json", "ctl.json"}.issubset(copied)
    assert {"edit-plan.json", "ctl.json"}.issubset(promoted)
    assert (baseline / "edit-plan.json").read_text(encoding="utf-8") == "baseline-edit"
    assert (work / "edit-plan.json").read_text(encoding="utf-8") == "candidate-edit"
    assert (work / "ctl.json").read_text(encoding="utf-8") == "candidate-ctl"
