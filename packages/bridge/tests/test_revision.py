from monter_bridge.analysis_models import ShotAnalysis, TimeRange, VirProject
from monter_bridge.critic_models import CriticFinding, CriticReport
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.revision import revise_edit_plan


def mkshot(id_: str, energy: float) -> ShotAnalysis:
    return ShotAnalysis(
        id=id_, asset_id=id_, range=TimeRange(start_seconds=0, end_seconds=5),
        mean_motion=energy, peak_motion=energy, motion_samples=[], edit_anchors=[],
    )


def mkseg(id_: str, shot: str, tin: float, tout: float, target: float, actual: float) -> EditSegment:
    return EditSegment(
        id=id_, asset_id=shot, shot_id=shot,
        source_in_seconds=0, source_out_seconds=tout-tin,
        timeline_in_seconds=tin, timeline_out_seconds=tout,
        role="build", target_energy=target, shot_energy=actual,
        confidence=.3, reason="fixture",
    )


def test_revision_replaces_only_flagged_segment_with_better_candidate():
    vir = VirProject.new("p", [mkshot("low", .1), mkshot("mid", .5), mkshot("high", 1.0), mkshot("alt", .8)])
    edit = EditPlan(
        project_id="p", target_duration_seconds=4, actual_duration_seconds=4,
        segments=[mkseg("s1", "low", 0, 2, .2, .0), mkseg("s2", "low", 2, 4, .9, .0)],
    )
    report = CriticReport(
        project_id="p", status="needs_revision", metrics=[],
        findings=[CriticFinding(code="immediate_repetition", severity="error", segment_id="s2", message="repeat")],
    )

    revised, revision = revise_edit_plan(edit, vir, report)

    assert revision.changed is True
    assert revised.segments[0].shot_id == "low"
    assert revised.segments[1].shot_id != "low"
    assert revised.segments[1].shot_id not in {revised.segments[0].shot_id}
    assert revision.actions[0].kind == "replace_segment"
