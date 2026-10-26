from __future__ import annotations

from collections import Counter

from .analysis_models import ShotAnalysis, VirProject
from .director import energy_at, role_at
from .planning_models import AudioAnalysis, DirectorPlan, EditPlan, EditSegment


def normalized_shot_energies(shots: list[ShotAnalysis]) -> dict[str, float]:
    raw = {
        shot.id: 0.65 * shot.mean_motion + 0.35 * shot.peak_motion
        for shot in shots
    }
    values = list(raw.values())
    low = min(values, default=0.0)
    high = max(values, default=0.0)
    if high - low < 1e-9:
        return {shot_id: 0.5 for shot_id in raw}
    return {shot_id: (value - low) / (high - low) for shot_id, value in raw.items()}


def snapped_boundaries(
    duration: float,
    segment_count: int,
    beats_seconds: list[float] | None = None,
    snap_window: float = 0.18,
) -> list[float]:
    if segment_count <= 0:
        raise ValueError("segment_count must be > 0")
    boundaries = [duration * index / segment_count for index in range(segment_count + 1)]
    beats = beats_seconds or []
    if not beats:
        return boundaries

    snapped = [0.0]
    for boundary in boundaries[1:-1]:
        nearest = min(beats, key=lambda beat: abs(beat - boundary))
        candidate = nearest if abs(nearest - boundary) <= snap_window else boundary
        if candidate <= snapped[-1] + 0.55:
            candidate = boundary
        if candidate >= duration - 0.55:
            candidate = boundary
        snapped.append(candidate)
    snapped.append(duration)
    return snapped


def _source_window(shot: ShotAnalysis, desired_duration: float) -> tuple[float, float]:
    shot_duration = shot.range.duration_seconds
    duration = min(desired_duration, shot_duration)
    peak = next((anchor for anchor in shot.edit_anchors if anchor.type == "motion_peak"), None)
    center = peak.time_seconds if peak else (shot.range.start_seconds + shot.range.end_seconds) / 2
    start = center - duration * 0.45
    start = max(shot.range.start_seconds, min(start, shot.range.end_seconds - duration))
    return start, start + duration


def build_edit_plan(
    vir: VirProject,
    director: DirectorPlan,
    audio: AudioAnalysis | None = None,
) -> EditPlan:
    if not vir.shots:
        raise ValueError("VIR contains no analyzable shots")

    target = director.target_duration_seconds
    initial_count = min(8, max(4, len(vir.shots)))
    boundaries = snapped_boundaries(target, initial_count, audio.beats_seconds if audio else None)
    energies = normalized_shot_energies(vir.shots)
    uses: Counter[str] = Counter()
    previous_shot_id: str | None = None
    segments: list[EditSegment] = []

    for index, (timeline_in, timeline_out) in enumerate(zip(boundaries, boundaries[1:])):
        desired_duration = timeline_out - timeline_in
        midpoint = ((timeline_in + timeline_out) / 2) / target
        target_energy = energy_at(director, midpoint)
        role = role_at(director, midpoint)

        candidates = [shot for shot in vir.shots if shot.range.duration_seconds >= desired_duration]
        if not candidates:
            candidates = sorted(vir.shots, key=lambda shot: shot.range.duration_seconds, reverse=True)[: max(1, min(4, len(vir.shots)))]

        def score(shot: ShotAnalysis) -> float:
            energy_fit = 1.0 - abs(energies[shot.id] - target_energy)
            duration_fit = min(1.0, shot.range.duration_seconds / max(desired_duration, 1e-6))
            novelty = 1.0 / (1.0 + uses[shot.id])
            immediate_penalty = 0.55 if shot.id == previous_shot_id and len(candidates) > 1 else 0.0
            return 0.62 * energy_fit + 0.22 * duration_fit + 0.16 * novelty - immediate_penalty

        chosen = max(candidates, key=score)
        source_in, source_out = _source_window(chosen, desired_duration)
        actual_duration = source_out - source_in
        actual_timeline_out = timeline_in + actual_duration
        shot_energy = energies[chosen.id]
        confidence = max(0.0, min(1.0, score(chosen)))

        segments.append(
            EditSegment(
                id=f"segment_{index:03d}",
                asset_id=chosen.asset_id,
                shot_id=chosen.id,
                source_in_seconds=source_in,
                source_out_seconds=source_out,
                timeline_in_seconds=timeline_in,
                timeline_out_seconds=actual_timeline_out,
                role=role,
                target_energy=target_energy,
                shot_energy=shot_energy,
                confidence=confidence,
                reason=(
                    f"{role}: target energy {target_energy:.2f}; selected shot energy {shot_energy:.2f}; "
                    "trim is centered toward a motion peak when available."
                ),
            )
        )
        uses[chosen.id] += 1
        previous_shot_id = chosen.id

    # Keep the rough cut contiguous when a short source shot forced an early segment end.
    cursor = 0.0
    for segment in segments:
        duration = segment.timeline_out_seconds - segment.timeline_in_seconds
        segment.timeline_in_seconds = cursor
        segment.timeline_out_seconds = cursor + duration
        cursor += duration

    return EditPlan(
        project_id=vir.project_id,
        target_duration_seconds=target,
        actual_duration_seconds=cursor,
        segments=segments,
        strategy_notes=[
            "Energy fit is normalized within this project rather than against a universal motion scale.",
            "Music beats only snap nearby boundaries; the planner intentionally avoids cut-on-every-beat behavior.",
            "This pass uses hard-cut structure. Event-driven retiming and CTL transitions are compiled in later passes.",
        ],
    )
