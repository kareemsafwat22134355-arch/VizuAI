from __future__ import annotations

from dataclasses import dataclass, field

from .critic_models import RevisionReport
from .post_render_revision_models import RevisionVerificationStatus
from .transition_refinement_models import TransitionRefinementReport


@dataclass(frozen=True)
class RevisionVerificationResult:
    status: RevisionVerificationStatus
    verified_boundaries: list[int] = field(default_factory=list)
    failed_boundaries: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def required_advanced_action_boundaries(revision: RevisionReport) -> set[int]:
    return {
        action.boundary_index
        for action in revision.actions
        if action.verification_kind == "advanced_action_timing"
        and action.boundary_index is not None
    }


def verify_revision_actions(
    revision: RevisionReport,
    refinement: TransitionRefinementReport | None,
) -> RevisionVerificationResult:
    required = sorted(required_advanced_action_boundaries(revision))
    if not required:
        return RevisionVerificationResult(
            status="not_required",
            notes=["No revision action requires post-mutation advanced verification."],
        )

    if refinement is None:
        return RevisionVerificationResult(
            status="failed",
            failed_boundaries=required,
            notes=[
                "At least one advanced action-timing roll requires verification, but the candidate has no transition-refinement report."
            ],
        )

    by_boundary = {item.boundary_index: item for item in refinement.boundaries}
    verified: list[int] = []
    failed: list[int] = []
    notes: list[str] = []

    for boundary_index in required:
        item = by_boundary.get(boundary_index)
        if item is None:
            failed.append(boundary_index)
            notes.append(
                f"Boundary {boundary_index}: mandatory advanced action-timing verification result is missing."
            )
            continue

        passed = (
            item.status == "confirmed"
            and item.base_mechanism == "action_cut"
            and item.refined_mechanism == "action_cut"
        )
        if passed:
            verified.append(boundary_index)
            notes.append(
                f"Boundary {boundary_index}: selective dense flow confirmed the revised action-cut timing."
            )
        else:
            failed.append(boundary_index)
            notes.append(
                f"Boundary {boundary_index}: verification returned status={item.status}, "
                f"base={item.base_mechanism}, refined={item.refined_mechanism}; confirmation is required."
            )

    return RevisionVerificationResult(
        status="pass" if not failed else "failed",
        verified_boundaries=verified,
        failed_boundaries=failed,
        notes=notes,
    )
