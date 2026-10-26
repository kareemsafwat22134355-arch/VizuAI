from __future__ import annotations

from pathlib import Path

from .analysis_models import VirProject
from .audio_edit import build_audio_edit_plan
from .audio_edit_models import AudioBoundaryIntent, AudioEditPlan
from .ctl_models import CtlProgram
from .models import MonterProject
from .sound_director_models import BoundaryAudioEvidence, SoundBoundaryDecision, SoundDirectorReport
from .source_audio_analysis import analyze_boundary_audio

MIN_HANDLE_SECONDS = 0.12
MIN_EDGE_ACTIVITY = 0.42
MIN_CONTINUITY_ACTIVITY = 0.28
MIN_MOTIVATION = 0.58
AMBIGUOUS_MARGIN = 0.08


def _activity(window) -> float:
    return window.activity_score if window is not None else 0.0


def _candidate_scores(evidence: BoundaryAudioEvidence) -> tuple[float | None, float | None]:
    outgoing_pre = _activity(evidence.outgoing_pre)
    outgoing_post = _activity(evidence.outgoing_post)
    incoming_pre = _activity(evidence.incoming_pre)
    incoming_post = _activity(evidence.incoming_post)

    j_score: float | None = None
    if (
        evidence.incoming_handle_seconds >= MIN_HANDLE_SECONDS
        and evidence.incoming_pre is not None
        and evidence.incoming_post is not None
        and incoming_pre >= MIN_EDGE_ACTIVITY
        and incoming_post >= MIN_CONTINUITY_ACTIVITY
    ):
        j_score = 0.50 * incoming_pre + 0.25 * incoming_post + 0.25 * (1.0 - outgoing_pre)

    l_score: float | None = None
    if (
        evidence.outgoing_handle_seconds >= MIN_HANDLE_SECONDS
        and evidence.outgoing_pre is not None
        and evidence.outgoing_post is not None
        and outgoing_post >= MIN_EDGE_ACTIVITY
        and outgoing_pre >= MIN_CONTINUITY_ACTIVITY
    ):
        l_score = 0.50 * outgoing_post + 0.25 * outgoing_pre + 0.25 * (1.0 - incoming_post)

    return j_score, l_score


def _overlap(handle_seconds: float, motivation: float) -> float:
    target = 0.18 + 0.10 * max(0.0, min(1.0, (motivation - MIN_MOTIVATION) / (1.0 - MIN_MOTIVATION)))
    return max(MIN_HANDLE_SECONDS, min(handle_seconds, 0.28, target))


def decide_boundary_sound(evidence: BoundaryAudioEvidence) -> SoundBoundaryDecision:
    j_score, l_score = _candidate_scores(evidence)
    metrics = {
        "outgoingPreActivity": _activity(evidence.outgoing_pre),
        "outgoingPostActivity": _activity(evidence.outgoing_post),
        "incomingPreActivity": _activity(evidence.incoming_pre),
        "incomingPostActivity": _activity(evidence.incoming_post),
        "outgoingHandleSeconds": evidence.outgoing_handle_seconds,
        "incomingHandleSeconds": evidence.incoming_handle_seconds,
    }
    if j_score is not None:
        metrics["jMotivation"] = j_score
    if l_score is not None:
        metrics["lMotivation"] = l_score

    if j_score is None and l_score is None:
        return SoundBoundaryDecision(
            boundary_index=evidence.boundary_index,
            recommendation="sync",
            overlap_seconds=0.0,
            confidence=0.85 if max(metrics["outgoingPreActivity"], metrics["incomingPostActivity"]) < 0.25 else 0.65,
            reason=(
                "No source-audio handle carries enough continuous activity to justify crossing the picture cut; preserve sync/silence."
                if evidence.blocked_reason is None
                else f"Preserve sync because J/L evidence is unavailable: {evidence.blocked_reason}."
            ),
            evidence=metrics,
        )

    if j_score is not None and l_score is not None and abs(j_score - l_score) < AMBIGUOUS_MARGIN:
        return SoundBoundaryDecision(
            boundary_index=evidence.boundary_index,
            recommendation="sync",
            overlap_seconds=0.0,
            confidence=max(j_score, l_score),
            reason="Incoming and outgoing audio continuities are similarly strong; avoid an arbitrary overlap and preserve the visual boundary.",
            evidence=metrics,
        )

    if j_score is not None and (l_score is None or j_score > l_score):
        if j_score < MIN_MOTIVATION:
            return SoundBoundaryDecision(
                boundary_index=evidence.boundary_index,
                recommendation="sync",
                overlap_seconds=0.0,
                confidence=1.0 - j_score,
                reason="Incoming pre-roll is audible but not sufficiently dominant to justify leading the next shot.",
                evidence=metrics,
            )
        return SoundBoundaryDecision(
            boundary_index=evidence.boundary_index,
            recommendation="j_cut",
            overlap_seconds=_overlap(evidence.incoming_handle_seconds, j_score),
            confidence=min(1.0, j_score),
            reason="Incoming source audio is active before the picture cut, continues into the incoming shot, and is cleaner than the outgoing tail; lead the next scene with sound.",
            evidence=metrics,
        )

    assert l_score is not None
    if l_score < MIN_MOTIVATION:
        return SoundBoundaryDecision(
            boundary_index=evidence.boundary_index,
            recommendation="sync",
            overlap_seconds=0.0,
            confidence=1.0 - l_score,
            reason="Outgoing post-roll remains audible but is not sufficiently dominant to justify trailing across the picture cut.",
            evidence=metrics,
        )
    return SoundBoundaryDecision(
        boundary_index=evidence.boundary_index,
        recommendation="l_cut",
        overlap_seconds=_overlap(evidence.outgoing_handle_seconds, l_score),
        confidence=min(1.0, l_score),
        reason="Outgoing source audio remains active after the picture cut while the incoming head is quieter; let the previous scene trail over the new image.",
        evidence=metrics,
    )


def direct_sound(
    project: MonterProject,
    ctl: CtlProgram,
    vir: VirProject,
    proxy_dir: Path,
    max_jl_cuts: int = 2,
) -> SoundDirectorReport:
    if max_jl_cuts < 0 or max_jl_cuts > 8:
        raise ValueError("max_jl_cuts must be between 0 and 8")
    boundaries = analyze_boundary_audio(project, ctl, vir, proxy_dir)
    decisions = [decide_boundary_sound(evidence) for evidence in boundaries]
    non_sync = [decision for decision in decisions if decision.recommendation != "sync"]
    non_sync.sort(key=lambda item: (-item.confidence, item.boundary_index))
    selected = non_sync[:max_jl_cuts]

    return SoundDirectorReport(
        project_id=project.project_id,
        boundaries=boundaries,
        decisions=decisions,
        selected_intents=selected,
        max_jl_cuts=max_jl_cuts,
        notes=[
            "v0.20 uses local source-audio activity and handle evidence only; it does not infer speech semantics or scene meaning.",
            "Silence and synchronous boundaries remain first-class outcomes; the director never forces a J/L cut merely to add complexity.",
            f"At most {max_jl_cuts} non-sync audio boundaries are selected to avoid turning every cut into an overlap.",
        ],
    )


def build_sound_directed_audio_plan(
    project: MonterProject,
    ctl: CtlProgram,
    report: SoundDirectorReport,
    source_gain_db: float = -3.0,
    music_gain_db: float = -8.0,
) -> AudioEditPlan:
    if report.project_id != project.project_id or report.project_id != ctl.project_id:
        raise ValueError("Sound Director report projectId does not match project/CTL")
    intents = [
        AudioBoundaryIntent(
            boundary_index=decision.boundary_index,
            kind=decision.recommendation,
            overlap_seconds=decision.overlap_seconds,
            reason=decision.reason,
        )
        for decision in report.selected_intents
    ]
    return build_audio_edit_plan(
        project,
        ctl,
        boundary_intents=intents,
        source_gain_db=source_gain_db,
        music_gain_db=music_gain_db,
    )
