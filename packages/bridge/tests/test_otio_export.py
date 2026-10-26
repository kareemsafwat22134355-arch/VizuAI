from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.otio_export import build_otio_timeline
from monter_bridge.planning_models import EditPlan, EditSegment


def test_otio_uses_relative_media_references_and_monter_metadata():
    project = MonterProject(
        project_id="p",
        project_name="OTIO Test",
        created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW",
        source_bytes=10,
        proxy_bytes=0,
        assets=[
            MediaAsset(id="a", filename="A.mov", source_rel_path="camera/A.mov", source_size_bytes=10, duration_seconds=5, width=1920, height=1080, fps=25, codec="h264", has_audio=True)
        ],
    )
    edit = EditPlan(
        project_id="p",
        target_duration_seconds=2,
        actual_duration_seconds=2,
        segments=[
            EditSegment(id="s1", asset_id="a", shot_id="shot_a", source_in_seconds=1, source_out_seconds=3, timeline_in_seconds=0, timeline_out_seconds=2, role="setup", target_energy=.2, shot_energy=.3, confidence=.9, reason="fixture")
        ],
    )

    timeline = build_otio_timeline(project, edit)
    clip = timeline.tracks[0][0]

    assert timeline.name == "OTIO Test"
    assert clip.media_reference.target_url == "camera/A.mov"
    assert clip.metadata["MONTER"]["shotId"] == "shot_a"
    assert clip.source_range.duration.value == 50
    assert clip.source_range.duration.rate == 25
