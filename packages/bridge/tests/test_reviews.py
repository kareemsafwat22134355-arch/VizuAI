from pathlib import Path

import pytest

from monter_bridge.corrections import load_correction_ledger
from monter_bridge.review_models import DecisionReviewLedger
from monter_bridge.reviews import (
    build_review_summary,
    load_review_ledger,
    record_accepted_review,
    record_corrected_review,
)


def test_review_summary_uses_all_reviewed_decisions_as_denominator(tmp_path: Path):
    reviews_path = tmp_path / "decision-reviews.json"
    corrections_path = tmp_path / "human-corrections.json"

    record_accepted_review(
        reviews_path,
        "p",
        kind="transition",
        target_type="boundary",
        target_ref="1",
        ai_decision={"mechanism": "directional_bridge"},
        context={"directorRole": "build"},
        reason="The bridge carries the motion cleanly.",
    )
    record_accepted_review(
        reviews_path,
        "p",
        kind="transition",
        target_type="boundary",
        target_ref="2",
        ai_decision={"mechanism": "hard_cut"},
        context={"directorRole": "rupture"},
    )
    record_corrected_review(
        reviews_path,
        corrections_path,
        "p",
        kind="transition",
        target_type="boundary",
        target_ref="3",
        ai_decision={"mechanism": "directional_bridge"},
        human_decision={"mechanism": "hard_cut"},
        context={"directorRole": "rupture"},
        reason="Rupture should stay abrupt.",
    )

    reviews = load_review_ledger(reviews_path)
    corrections = load_correction_ledger(corrections_path)
    summary = build_review_summary(reviews, corrections)

    assert summary.reviewed == 3
    assert summary.accepted == 2
    assert summary.corrected == 1
    assert summary.acceptance_rate == pytest.approx(2 / 3)
    assert summary.by_kind["transition"].reviewed == 3
    assert summary.by_director_role["rupture"].acceptance_rate == pytest.approx(0.5)
    assert summary.by_transition_mechanism["directional_bridge"].reviewed == 2
    assert summary.by_transition_mechanism["directional_bridge"].acceptance_rate == pytest.approx(0.5)


def test_corrected_review_references_exact_correction(tmp_path: Path):
    reviews_path = tmp_path / "decision-reviews.json"
    corrections_path = tmp_path / "human-corrections.json"

    _, corrections, review = record_corrected_review(
        reviews_path,
        corrections_path,
        "p",
        kind="trim",
        target_type="segment",
        target_ref="segment_001",
        ai_decision={"sourceIn": 1.0},
        human_decision={"sourceIn": 1.25},
        context={"directorRole": "build"},
        reason="The earlier frames feel hesitant.",
    )

    assert review.correction_id == corrections.corrections[0].id
    assert corrections.corrections[0].human_decision["sourceIn"] == 1.25


def test_missing_referenced_correction_is_detected():
    reviews = DecisionReviewLedger.new("p")
    from monter_bridge.review_models import DecisionReview
    reviews.reviews.append(
        DecisionReview(
            id="review_1",
            kind="transition",
            target_type="boundary",
            target_ref="1",
            ai_decision={"mechanism": "directional_bridge"},
            outcome="corrected",
            correction_id="correction_missing",
            context={},
            reason="fixture",
            created_at="2026-10-26T00:00:00Z",
        )
    )
    from monter_bridge.correction_models import CorrectionLedger
    corrections = CorrectionLedger.new("p")

    with pytest.raises(ValueError, match="missing correction"):
        build_review_summary(reviews, corrections)


def test_empty_summary_is_explicit():
    summary = build_review_summary(DecisionReviewLedger.new("p"))
    assert summary.reviewed == 0
    assert summary.acceptance_rate == 0
    assert "No reviewed decisions" in summary.notes[0]


def test_low_sample_buckets_are_marked_descriptive(tmp_path: Path):
    path = tmp_path / "decision-reviews.json"
    record_accepted_review(
        path,
        "p",
        kind="role",
        target_type="segment",
        target_ref="segment_1",
        ai_decision={"role": "build"},
    )
    summary = build_review_summary(load_review_ledger(path))
    assert any("Low-sample" in note and "role" in note for note in summary.notes)
