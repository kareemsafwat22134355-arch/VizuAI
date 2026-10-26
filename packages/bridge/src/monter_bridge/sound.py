from __future__ import annotations

from .ctl_models import AudioBoundaryIntent, TimeWarpIntent
from .models import MonterProject
from .planning_models import EditPlan


def select_audio_boundaries(
    edit: EditPlan,
    project: MonterProject,
    time_warps: list[TimeWarpIntent],
    max_intents: int = 1,
    offset_seconds: float = 0.24,
) -> list[AudioBoundaryIntent]:
    assets = {asset.id: asset for asset in project.assets}
    warped = {intent.segment_id for intent in time_warps}
    candidates: list[tuple[float, AudioBoundaryIntent]] = []

    for boundary_index, (left, right) in enumerate(zip(edit.segments, edit.segments[1:]), start=1):
        if left.id in warped or right.id in warped:
            continue
        left_asset = assets.get(left.asset_id)
        right_asset = assets.get(right.asset_id)
        if not left_asset or not right_asset or not left_asset.has_audio or not right_asset.has_audio:
            continue

        # L-cut: outgoing source audio survives the picture cut. This requires a clean source
        # handle after the selected outgoing picture range and enough incoming material to trim.
        l_role_score = 1.0 if right.role in {"reveal", "payoff"} else 0.65 if left.role in {"rupture", "vacuum"} else 0.0
        left_handle = left_asset.duration_seconds - left.source_out_seconds
        right_picture_duration = right.source_out_seconds - right.source_in_seconds
        if l_role_score > 0 and left_handle >= offset_seconds and right_picture_duration >= offset_seconds + 0.45:
            candidates.append((l_role_score, AudioBoundaryIntent(
                boundary_index=boundary_index,
                mechanism="l_cut",
                offset_seconds=offset_seconds,
                reason=(
                    f"Outgoing source audio carries {offset_seconds:.2f}s under the {right.role} picture, "
                    "creating continuity before the incoming sound takes over."
                ),
            )))

        # J-cut: incoming source audio arrives before its picture. Only use it when the incoming
        # select has a real pre-roll handle; never synthesize missing audio.
        j_role_score = 0.9 if right.role in {"promise", "reveal"} else 0.0
        if j_role_score > 0 and right.source_in_seconds >= offset_seconds and (left.source_out_seconds - left.source_in_seconds) >= offset_seconds + 0.45:
            candidates.append((j_role_score, AudioBoundaryIntent(
                boundary_index=boundary_index,
                mechanism="j_cut",
                offset_seconds=offset_seconds,
                reason=(
                    f"Incoming source audio enters {offset_seconds:.2f}s before the {right.role} picture, "
                    "using an available source pre-roll handle."
                ),
            )))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[AudioBoundaryIntent] = []
    used_boundaries: set[int] = set()
    for _, intent in candidates:
        if intent.boundary_index in used_boundaries:
            continue
        selected.append(intent)
        used_boundaries.add(intent.boundary_index)
        if len(selected) >= max_intents:
            break
    return sorted(selected, key=lambda intent: intent.boundary_index)
