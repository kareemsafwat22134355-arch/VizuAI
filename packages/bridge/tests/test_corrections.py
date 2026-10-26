from pathlib import Path

import pytest

from monter_bridge.correction_models import CorrectionLedger
from monter_bridge.corrections import append_correction, load_correction_ledger, record_correction, write_correction_ledger


def test_record_correction_preserves_ai_human_context_and_reason(tmp_path: Path):
    path = tmp_path / "human-corrections.json"
    ledger, correction = append_correction(
        path,
        "project_a",
        kind="transition",
        target_type="boundary",
        target_ref="3",
        ai_decision={"mechanism": "directional_bridge", "durationSeconds": 0.12},
        human_decision={"mechanism": "hard_cut", "durationSeconds": 0.0},
        context={"relationScore": 0.74, "directorRole": "rupture"},
        reason="The rupture reads stronger without a smoothing bridge.",
        source="cli",
    )

    restored = load_correction_ledger(path)
    restored_correction = restored.corrections[0]

    assert correction.id.startswith("correction_")
    assert restored.project_id == "project_a"
    assert restored_correction.ai_decision["mechanism"] == "directional_bridge"
    assert restored_correction.human_decision["mechanism"] == "hard_cut"
    assert restored_correction.context["directorRole"] == "rupture"
    assert "stronger" in restored_correction.reason
    assert len(ledger.corrections) == 1
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_correction_must_change_the_ai_decision():
    ledger = CorrectionLedger.new("p")
    with pytest.raises(ValueError, match="must differ"):
        record_correction(
            ledger,
            kind="transition",
            target_type="boundary",
            target_ref="1",
            ai_decision={"mechanism": "hard_cut"},
            human_decision={"mechanism": "hard_cut"},
            reason="fixture",
        )


def test_segment_or_boundary_correction_requires_target_ref():
    ledger = CorrectionLedger.new("p")
    with pytest.raises(ValueError, match="target_ref"):
        record_correction(
            ledger,
            kind="trim",
            target_type="segment",
            target_ref=None,
            ai_decision={"sourceIn": 1.0},
            human_decision={"sourceIn": 1.2},
            reason="fixture",
        )


def test_existing_ledger_rejects_other_project(tmp_path: Path):
    path = tmp_path / "human-corrections.json"
    write_correction_ledger(path, CorrectionLedger.new("project_a"))

    with pytest.raises(ValueError, match="does not match"):
        append_correction(
            path,
            "project_b",
            kind="role",
            target_type="segment",
            target_ref="segment_001",
            ai_decision={"role": "build"},
            human_decision={"role": "rupture"},
            reason="fixture",
        )


def test_project_level_correction_can_omit_target_ref():
    ledger = CorrectionLedger.new("p")
    correction = record_correction(
        ledger,
        kind="other",
        target_type="project",
        target_ref=None,
        ai_decision={"ending": "dense"},
        human_decision={"ending": "vacuum"},
        reason="The payoff needs a silence pocket before the logo.",
    )
    assert correction.target_ref is None


def test_non_finite_numeric_evidence_is_rejected():
    ledger = CorrectionLedger.new("p")
    with pytest.raises(ValueError, match="finite number"):
        record_correction(
            ledger,
            kind="transition",
            target_type="boundary",
            target_ref="2",
            ai_decision={"relationScore": float("nan")},
            human_decision={"relationScore": 0.7},
            reason="fixture",
        )
