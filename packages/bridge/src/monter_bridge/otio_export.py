from __future__ import annotations

from pathlib import Path

import opentimelineio as otio

from .models import MonterProject
from .planning_models import EditPlan


def build_otio_timeline(project: MonterProject, edit_plan: EditPlan) -> otio.schema.Timeline:
    assets = {asset.id: asset for asset in project.assets}
    timeline = otio.schema.Timeline(name=project.project_name)
    track = otio.schema.Track(name="MONTER V1", kind=otio.schema.TrackKind.Video)

    for segment in edit_plan.segments:
        asset = assets.get(segment.asset_id)
        if asset is None:
            raise ValueError(f"Edit plan references unknown asset: {segment.asset_id}")
        fps = asset.fps or 24.0
        duration = segment.source_out_seconds - segment.source_in_seconds
        reference = otio.schema.ExternalReference(target_url=asset.source_rel_path)
        clip = otio.schema.Clip(
            name=f"{asset.filename} / {segment.role}",
            media_reference=reference,
            source_range=otio.opentime.TimeRange(
                start_time=otio.opentime.RationalTime(segment.source_in_seconds * fps, fps),
                duration=otio.opentime.RationalTime(duration * fps, fps),
            ),
        )
        clip.metadata["MONTER"] = {
            "segmentId": segment.id,
            "shotId": segment.shot_id,
            "role": segment.role,
            "confidence": segment.confidence,
            "reason": segment.reason,
        }
        track.append(clip)

    timeline.tracks.append(track)
    return timeline


def export_otio(project: MonterProject, edit_plan: EditPlan, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    timeline = build_otio_timeline(project, edit_plan)
    otio.adapters.write_to_file(timeline, str(output))
