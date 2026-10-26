from __future__ import annotations

from .audio_mix_models import AudioMixAudit
from .critic_models import CriticReport
from .final_critic_models import FinalCriticFinding, FinalCriticMetric, FinalCriticReport
from .render_analysis_models import RenderAnalysisReport

AUTO_EDITORIAL_CODES = {
    "energy_mismatch",
    "low_confidence_selection",
    "immediate_repetition",
    "motion_match_timing_weak",
}


def build_final_critic(
    editorial: CriticReport,
    render_analysis: RenderAnalysisReport | None = None,
    audio_audit: AudioMixAudit | None = None,
) -> FinalCriticReport:
    if render_analysis is not None and render_analysis.project_id != editorial.project_id:
        raise ValueError("Render analysis projectId does not match editorial critic")

    findings: list[FinalCriticFinding] = []
    metrics: list[FinalCriticMetric] = []

    for metric in editorial.metrics:
        metrics.append(FinalCriticMetric(
            name=metric.name,
            domain="editorial",
            value=metric.value,
            target=metric.target,
            passed=metric.passed,
        ))

    for finding in editorial.findings:
        reviseability = "automatic_candidate" if finding.code in AUTO_EDITORIAL_CODES else "manual_only"
        findings.append(FinalCriticFinding(
            code=finding.code,
            domain="editorial",
            severity=finding.severity,
            reviseability=reviseability,
            message=finding.message,
            source_artifact="critic-report.json",
            segment_id=finding.segment_id,
            boundary_index=finding.boundary_index,
        ))

    if render_analysis is not None:
        duration_ok = not any(
            finding.code == "duration_drift" and finding.severity == "error"
            for finding in render_analysis.findings
        )
        metrics.extend([
            FinalCriticMetric(
                name="render_duration_drift_seconds",
                domain="render_integrity",
                value=abs(render_analysis.duration_drift_seconds),
                target="<= render-analysis encoded-duration tolerance",
                passed=duration_ok,
            ),
            FinalCriticMetric(
                name="render_black_frame_fraction",
                domain="render_integrity",
                value=render_analysis.black_frame_fraction,
                target="< 0.98 catastrophic-blank gate",
                passed=render_analysis.black_frame_fraction < 0.98,
            ),
            FinalCriticMetric(
                name="render_energy_alignment",
                domain="render_integrity",
                value=render_analysis.energy_alignment,
                target=">= 0.45 diagnostic target (warning-only)",
                passed=render_analysis.energy_alignment >= 0.45,
            ),
        ])
        for finding in render_analysis.findings:
            findings.append(FinalCriticFinding(
                code=finding.code,
                domain="render_integrity",
                severity=finding.severity,
                reviseability="manual_only",
                message=finding.message,
                source_artifact="render-analysis.json",
            ))

    if audio_audit is not None:
        metrics.append(FinalCriticMetric(
            name="audio_max_volume_dbfs",
            domain="audio_integrity",
            value=audio_audit.max_volume_dbfs,
            target=f"<= {audio_audit.safety_threshold_dbfs:.2f} dBFS decoded-sample peak",
            passed=audio_audit.clipping_safe,
        ))
        if not audio_audit.clipping_safe:
            findings.append(FinalCriticFinding(
                code="audio_headroom_failure",
                domain="audio_integrity",
                severity="error",
                reviseability="manual_only",
                message=(
                    f"Decoded audio peak is {audio_audit.max_volume_dbfs:.2f} dBFS, above the "
                    f"{audio_audit.safety_threshold_dbfs:.2f} dBFS safety threshold."
                ),
                source_artifact="audio-mix-audit.json",
            ))

    automatic_revision_candidates = sum(
        finding.reviseability == "automatic_candidate"
        for finding in findings
    )
    manual_review_findings = sum(
        finding.reviseability == "manual_only" and finding.severity in {"warning", "error"}
        for finding in findings
    )

    integrity_error = any(
        finding.severity == "error" and finding.domain in {"render_integrity", "audio_integrity"}
        for finding in findings
    )
    if integrity_error:
        status = "needs_review"
    elif editorial.status == "needs_revision":
        status = "needs_revision"
    else:
        status = "pass"

    return FinalCriticReport(
        project_id=editorial.project_id,
        status=status,
        automatic_revision_candidates=automatic_revision_candidates,
        manual_review_findings=manual_review_findings,
        metrics=metrics,
        findings=findings,
        notes=[
            "The final critic keeps editorial, render-integrity, and audio-integrity evidence in separate domains instead of collapsing quality into one score.",
            "Only finding codes already supported by the deterministic edit revision engine are labeled automatic_candidate.",
            "Render/audio integrity findings remain manual_only; no edit mutation is attempted as a substitute for fixing a broken renderer or mix.",
        ],
    )
