from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import orjson

from .correction_models import CorrectionLedger, CorrectionKind, CorrectionSource, CorrectionTargetType, DecisionScalar
from .corrections import load_correction_ledger, load_or_create_ledger as load_or_create_corrections, record_correction
from .review_models import DecisionReview, DecisionReviewLedger, DecisionReviewSummary, ReviewBucket


def load_review_ledger(path: Path) -> DecisionReviewLedger:
    return DecisionReviewLedger.model_validate(orjson.loads(path.read_bytes()))


def write_review_ledger(path: Path, ledger: DecisionReviewLedger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(orjson.dumps(ledger.model_dump(by_alias=True), option=orjson.OPT_INDENT_2))
    temp.replace(path)


def load_or_create_reviews(path: Path, project_id: str) -> DecisionReviewLedger:
    if not path.exists():
        return DecisionReviewLedger.new(project_id)
    ledger = load_review_ledger(path)
    if ledger.project_id != project_id:
        raise ValueError(f"Decision review ledger projectId {ledger.project_id!r} does not match project {project_id!r}")
    return ledger


def _new_review(
    ledger: DecisionReviewLedger,
    *,
    kind: CorrectionKind,
    target_type: CorrectionTargetType,
    target_ref: str | None,
    ai_decision: dict[str, DecisionScalar],
    outcome: str,
    correction_id: str | None,
    context: dict[str, DecisionScalar] | None,
    reason: str,
    source: CorrectionSource,
) -> DecisionReview:
    now = datetime.now(timezone.utc).isoformat()
    review = DecisionReview(
        id=f"review_{uuid4().hex}",
        kind=kind,
        target_type=target_type,
        target_ref=target_ref,
        ai_decision=ai_decision,
        outcome=outcome,
        correction_id=correction_id,
        context=context or {},
        reason=reason.strip(),
        source=source,
        created_at=now,
    )
    ledger.reviews.append(review)
    ledger.updated_at = now
    return review


def record_accepted_review(
    review_path: Path,
    project_id: str,
    *,
    kind: CorrectionKind,
    target_type: CorrectionTargetType,
    target_ref: str | None,
    ai_decision: dict[str, DecisionScalar],
    context: dict[str, DecisionScalar] | None = None,
    reason: str = "Accepted as-is.",
    source: CorrectionSource = "cli",
) -> tuple[DecisionReviewLedger, DecisionReview]:
    ledger = load_or_create_reviews(review_path, project_id)
    review = _new_review(
        ledger,
        kind=kind,
        target_type=target_type,
        target_ref=target_ref,
        ai_decision=ai_decision,
        outcome="accepted",
        correction_id=None,
        context=context,
        reason=reason,
        source=source,
    )
    write_review_ledger(review_path, ledger)
    return ledger, review


def record_corrected_review(
    review_path: Path,
    correction_path: Path,
    project_id: str,
    *,
    kind: CorrectionKind,
    target_type: CorrectionTargetType,
    target_ref: str | None,
    ai_decision: dict[str, DecisionScalar],
    human_decision: dict[str, DecisionScalar],
    context: dict[str, DecisionScalar] | None,
    reason: str,
    source: CorrectionSource = "cli",
) -> tuple[DecisionReviewLedger, CorrectionLedger, DecisionReview]:
    reviews = load_or_create_reviews(review_path, project_id)
    corrections = load_or_create_corrections(correction_path, project_id)
    correction = record_correction(
        corrections,
        kind=kind,
        target_type=target_type,
        target_ref=target_ref,
        ai_decision=ai_decision,
        human_decision=human_decision,
        context=context or {},
        reason=reason,
        source=source,
    )
    review = _new_review(
        reviews,
        kind=kind,
        target_type=target_type,
        target_ref=target_ref,
        ai_decision=ai_decision,
        outcome="corrected",
        correction_id=correction.id,
        context=context,
        reason=reason,
        source=source,
    )

    # Prepare both files before either final path is replaced. The two-ledger update is
    # intentionally small and local; if the second replace fails we restore the first.
    review_path.parent.mkdir(parents=True, exist_ok=True)
    correction_path.parent.mkdir(parents=True, exist_ok=True)
    review_tmp = review_path.with_suffix(review_path.suffix + ".txn.tmp")
    correction_tmp = correction_path.with_suffix(correction_path.suffix + ".txn.tmp")
    review_tmp.write_bytes(orjson.dumps(reviews.model_dump(by_alias=True), option=orjson.OPT_INDENT_2))
    correction_tmp.write_bytes(orjson.dumps(corrections.model_dump(by_alias=True), option=orjson.OPT_INDENT_2))
    old_corrections = correction_path.read_bytes() if correction_path.exists() else None
    try:
        correction_tmp.replace(correction_path)
        try:
            review_tmp.replace(review_path)
        except Exception:
            if old_corrections is None:
                correction_path.unlink(missing_ok=True)
            else:
                correction_path.write_bytes(old_corrections)
            raise
    finally:
        review_tmp.unlink(missing_ok=True)
        correction_tmp.unlink(missing_ok=True)
    return reviews, corrections, review


def _bucket(items: list[DecisionReview]) -> ReviewBucket:
    reviewed = len(items)
    accepted = sum(item.outcome == "accepted" for item in items)
    corrected = sum(item.outcome == "corrected" for item in items)
    return ReviewBucket(
        reviewed=reviewed,
        accepted=accepted,
        corrected=corrected,
        acceptance_rate=accepted / reviewed if reviewed else 0.0,
    )


def build_review_summary(
    reviews: DecisionReviewLedger,
    corrections: CorrectionLedger | None = None,
) -> DecisionReviewSummary:
    if corrections is not None and corrections.project_id != reviews.project_id:
        raise ValueError("Correction ledger projectId does not match decision review ledger")
    correction_ids = {item.id for item in corrections.corrections} if corrections is not None else set()
    for review in reviews.reviews:
        if review.outcome == "corrected" and corrections is not None and review.correction_id not in correction_ids:
            raise ValueError(f"Review references missing correction: {review.correction_id}")

    if not reviews.reviews:
        return DecisionReviewSummary.empty(reviews.project_id)

    by_kind: dict[str, list[DecisionReview]] = defaultdict(list)
    by_role: dict[str, list[DecisionReview]] = defaultdict(list)
    by_mechanism: dict[str, list[DecisionReview]] = defaultdict(list)
    for review in reviews.reviews:
        by_kind[review.kind].append(review)
        role = review.context.get("directorRole")
        if isinstance(role, str) and role:
            by_role[role].append(review)
        if review.kind == "transition":
            mechanism = review.ai_decision.get("mechanism")
            if isinstance(mechanism, str) and mechanism:
                by_mechanism[mechanism].append(review)

    overall = _bucket(reviews.reviews)
    notes = [
        "Acceptance rates use every reviewed decision as the denominator; correction-only data is never treated as a rejection rate.",
        "Buckets with very few reviews are descriptive only and must not be promoted into policy automatically.",
    ]
    low_sample = [name for name, items in by_kind.items() if len(items) < 5]
    if low_sample:
        notes.append("Low-sample decision kinds (<5 reviews): " + ", ".join(sorted(low_sample)) + ".")

    return DecisionReviewSummary(
        project_id=reviews.project_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        reviewed=overall.reviewed,
        accepted=overall.accepted,
        corrected=overall.corrected,
        acceptance_rate=overall.acceptance_rate,
        by_kind={key: _bucket(items) for key, items in sorted(by_kind.items())},
        by_director_role={key: _bucket(items) for key, items in sorted(by_role.items())},
        by_transition_mechanism={key: _bucket(items) for key, items in sorted(by_mechanism.items())},
        notes=notes,
    )
