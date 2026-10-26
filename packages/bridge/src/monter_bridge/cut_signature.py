from __future__ import annotations

from pydantic import Field

from .analysis_models import ShotAnalysis
from .models import PortableModel
from .planning_models import EditSegment


class CutSignature(PortableModel):
    direction_compatibility: float = Field(ge=0, le=1)
    zoom_compatibility: float = Field(ge=0, le=1)
    phase_compatibility: float = Field(ge=0, le=1)
    global_motion_confidence: float = Field(ge=0, le=1)
    relation_score: float = Field(ge=0, le=1)


def _direction_score(left: ShotAnalysis, right: ShotAnalysis) -> float:
    a = left.global_motion.dominant_screen_direction
    b = right.global_motion.dominant_screen_direction
    if a == b and a not in {"static", "mixed"}:
        return 1.0
    if a == b == "static":
        return 0.65
    if "mixed" in {a, b}:
        return 0.4
    if "static" in {a, b}:
        return 0.3
    opposite = {("left", "right"), ("right", "left"), ("up", "down"), ("down", "up")}
    return 0.0 if (a, b) in opposite else 0.25


def _zoom_score(left: ShotAnalysis, right: ShotAnalysis) -> float:
    a = left.global_motion.zoom_direction
    b = right.global_motion.zoom_direction
    if a == b and a != "mixed":
        return 1.0 if a != "static" else 0.7
    if "mixed" in {a, b}:
        return 0.4
    if "static" in {a, b}:
        return 0.45
    return 0.0


def _near_anchor(shot: ShotAnalysis, anchor_types: set[str], time_seconds: float, tolerance: float = 0.38) -> bool:
    return any(
        anchor.type in anchor_types and abs(anchor.time_seconds - time_seconds) <= tolerance
        for anchor in shot.edit_anchors
    )


def _phase_score(left_segment: EditSegment, right_segment: EditSegment, left: ShotAnalysis, right: ShotAnalysis) -> float:
    outgoing_peak = _near_anchor(left, {"motion_peak"}, left_segment.source_out_seconds)
    incoming_onset = _near_anchor(right, {"motion_onset", "motion_peak"}, right_segment.source_in_seconds)
    if outgoing_peak and incoming_onset:
        return 1.0
    if outgoing_peak or incoming_onset:
        return 0.6
    outgoing_settle = _near_anchor(left, {"motion_settle"}, left_segment.source_out_seconds)
    incoming_settle = _near_anchor(right, {"motion_settle"}, right_segment.source_in_seconds)
    return 0.4 if outgoing_settle and incoming_settle else 0.15


def build_cut_signature(
    left_segment: EditSegment,
    right_segment: EditSegment,
    left_shot: ShotAnalysis,
    right_shot: ShotAnalysis,
) -> CutSignature:
    direction = _direction_score(left_shot, right_shot)
    zoom = _zoom_score(left_shot, right_shot)
    phase = _phase_score(left_segment, right_segment, left_shot, right_shot)
    confidence = min(left_shot.global_motion.confidence, right_shot.global_motion.confidence)
    physical_score = 0.55 * direction + 0.15 * zoom + 0.30 * phase
    relation = physical_score * (0.55 + 0.45 * confidence)
    return CutSignature(
        direction_compatibility=direction,
        zoom_compatibility=zoom,
        phase_compatibility=phase,
        global_motion_confidence=confidence,
        relation_score=max(0.0, min(1.0, relation)),
    )
