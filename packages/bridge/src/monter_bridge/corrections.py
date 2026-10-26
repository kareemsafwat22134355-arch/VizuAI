from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import orjson

from .correction_models import (
    CorrectionKind,
    CorrectionLedger,
    CorrectionSource,
    CorrectionTargetType,
    DecisionScalar,
    HumanCorrection,
)


def load_correction_ledger(path: Path) -> CorrectionLedger:
    return CorrectionLedger.model_validate(orjson.loads(path.read_bytes()))


def write_correction_ledger(path: Path, ledger: CorrectionLedger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(orjson.dumps(ledger.model_dump(by_alias=True), option=orjson.OPT_INDENT_2))
    temp.replace(path)


def load_or_create_ledger(path: Path, project_id: str) -> CorrectionLedger:
    if not path.exists():
        return CorrectionLedger.new(project_id)
    ledger = load_correction_ledger(path)
    if ledger.project_id != project_id:
        raise ValueError(
            f"Correction ledger projectId {ledger.project_id!r} does not match project {project_id!r}"
        )
    return ledger


def record_correction(
    ledger: CorrectionLedger,
    *,
    kind: CorrectionKind,
    target_type: CorrectionTargetType,
    target_ref: str | None,
    ai_decision: dict[str, DecisionScalar],
    human_decision: dict[str, DecisionScalar],
    reason: str,
    context: dict[str, DecisionScalar] | None = None,
    source: CorrectionSource = "cli",
) -> HumanCorrection:
    now = datetime.now(timezone.utc).isoformat()
    correction = HumanCorrection(
        id=f"correction_{uuid4().hex}",
        kind=kind,
        target_type=target_type,
        target_ref=target_ref,
        ai_decision=ai_decision,
        human_decision=human_decision,
        context=context or {},
        reason=reason.strip(),
        source=source,
        created_at=now,
    )
    ledger.corrections.append(correction)
    ledger.updated_at = now
    return correction


def append_correction(
    path: Path,
    project_id: str,
    **kwargs,
) -> tuple[CorrectionLedger, HumanCorrection]:
    ledger = load_or_create_ledger(path, project_id)
    correction = record_correction(ledger, **kwargs)
    write_correction_ledger(path, ledger)
    return ledger, correction
