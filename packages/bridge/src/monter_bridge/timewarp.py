from __future__ import annotations

from .analysis_models import ShotAnalysis, VirProject
from .ctl_models import TimeWarpIntent, TimeWarpSlice
from .planning_models import EditPlan, EditSegment

ROLE_BONUS = {"escalate": 0.7, "barrage": 0.8, "payoff": 0.35, "build": 0.2}


def timewarp_output_duration(intent: TimeWarpIntent) -> float:
    return sum(
        (slice_.source_out_seconds - slice_.source_in_seconds) / slice_.playback_rate
        for slice_ in intent.slices
    )


def build_timewarp_intent(segment: EditSegment, shot: ShotAnalysis) -> TimeWarpIntent | None:
    duration = segment.source_out_seconds - segment.source_in_seconds
    if duration < 1.2:
        return None

    peaks = [
        anchor for anchor in shot.edit_anchors
        if anchor.type == "motion_peak" and segment.source_in_seconds < anchor.time_seconds < segment.source_out_seconds
    ]
    if not peaks:
        return None
    peak = max(peaks, key=lambda anchor: anchor.confidence)

    half_burst = min(0.32, duration * 0.14)
    middle_in = max(segment.source_in_seconds + 0.16, peak.time_seconds - half_burst)
    middle_out = min(segment.source_out_seconds - 0.16, peak.time_seconds + half_burst)
    if middle_out - middle_in < 0.18:
        return None

    bounds = [segment.source_in_seconds, middle_in, middle_out, segment.source_out_seconds]
    source_durations = [bounds[i + 1] - bounds[i] for i in range(3)]
    relative_rates = [0.82, 1.9, 0.86]

    # One global factor preserves the clip's total timeline duration exactly while retaining
    # the slow→burst→settle relationship around the measured motion event.
    normalization = sum(d / r for d, r in zip(source_durations, relative_rates)) / duration
    rates = [rate * normalization for rate in relative_rates]
    slices = [
        TimeWarpSlice(source_in_seconds=bounds[i], source_out_seconds=bounds[i + 1], playback_rate=rates[i])
        for i in range(3)
    ]
    intent = TimeWarpIntent(
        segment_id=segment.id,
        anchor_seconds=peak.time_seconds,
        reason=(
            f"Measured motion apex at {peak.time_seconds:.2f}s motivates a duration-preserving "
            "slow→burst→settle retime instead of a stock speed ramp."
        ),
        slices=slices,
    )
    return intent


def select_timewarp_intents(edit_plan: EditPlan, vir: VirProject, max_intents: int = 2) -> list[TimeWarpIntent]:
    shots = {shot.id: shot for shot in vir.shots}
    candidates: list[tuple[float, TimeWarpIntent]] = []

    for segment in edit_plan.segments:
        shot = shots.get(segment.shot_id)
        if shot is None:
            continue
        intent = build_timewarp_intent(segment, shot)
        if intent is None:
            continue
        dynamic_ratio = shot.peak_motion / max(shot.mean_motion, 0.05)
        salience = dynamic_ratio + ROLE_BONUS.get(segment.role, 0.0)
        if salience >= 1.25:
            candidates.append((salience, intent))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = [intent for _, intent in candidates[:max_intents]]
    order = {segment.id: index for index, segment in enumerate(edit_plan.segments)}
    return sorted(selected, key=lambda intent: order[intent.segment_id])
