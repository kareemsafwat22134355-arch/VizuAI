from monter_bridge.sound_director import decide_boundary_sound
from monter_bridge.sound_director_models import AudioWindowMetrics, BoundaryAudioEvidence


def window(activity: float, asset_id: str = "a") -> AudioWindowMetrics:
    return AudioWindowMetrics(
        asset_id=asset_id,
        source_start_seconds=0,
        source_end_seconds=.3,
        duration_seconds=.3,
        rms_dbfs=-20 if activity > .5 else -55,
        peak_dbfs=-10 if activity > .5 else -45,
        active_frame_fraction=activity,
        activity_score=activity,
    )


def evidence(out_pre: float, out_post: float, in_pre: float, in_post: float) -> BoundaryAudioEvidence:
    return BoundaryAudioEvidence(
        boundary_index=1,
        visual_cut_seconds=2,
        outgoing_pre=window(out_pre, "left"),
        outgoing_post=window(out_post, "left"),
        incoming_pre=window(in_pre, "right"),
        incoming_post=window(in_post, "right"),
        outgoing_handle_seconds=.3,
        incoming_handle_seconds=.3,
    )


def test_quiet_boundary_preserves_sync_and_silence():
    decision = decide_boundary_sound(evidence(.05, .05, .04, .05))
    assert decision.recommendation == "sync"
    assert decision.overlap_seconds == 0
    assert "preserve" in decision.reason.lower()


def test_ambiguous_active_both_sides_preserves_visual_boundary():
    decision = decide_boundary_sound(evidence(.9, .9, .9, .9))
    assert decision.recommendation == "sync"
    assert "similarly strong" in decision.reason


def test_clear_incoming_activity_selects_j_cut():
    decision = decide_boundary_sound(evidence(.05, .05, .95, .9))
    assert decision.recommendation == "j_cut"
    assert .12 <= decision.overlap_seconds <= .28
    assert decision.confidence >= .58


def test_clear_outgoing_activity_selects_l_cut():
    decision = decide_boundary_sound(evidence(.9, .95, .05, .05))
    assert decision.recommendation == "l_cut"
    assert .12 <= decision.overlap_seconds <= .28
    assert decision.confidence >= .58


def test_short_handles_prevent_jl_even_with_active_audio():
    item = evidence(.05, .95, .95, .05)
    item.outgoing_handle_seconds = .05
    item.incoming_handle_seconds = .05
    decision = decide_boundary_sound(item)
    assert decision.recommendation == "sync"
