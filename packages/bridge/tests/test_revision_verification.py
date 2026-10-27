from monter_bridge.critic_models import RevisionAction, RevisionReport
from monter_bridge.revision_verification import (
    required_advanced_action_boundaries,
    verify_revision_actions,
)
from monter_bridge.transition_refinement_models import (
    BoundaryTransitionRefinement,
    TransitionRefinementReport,
)


def revision(*actions: RevisionAction) -> RevisionReport:
    return RevisionReport(project_id="p", changed=bool(actions), actions=list(actions))


def refinement(status="confirmed", base="action_cut", refined="action_cut", boundary=1):
    return TransitionRefinementReport(
        project_id="p",
        boundaries=[BoundaryTransitionRefinement(
            boundary_index=boundary,
            base_mechanism=base,
            refined_mechanism=refined,
            status=status,
            reason="fixture",
        )],
    )


def test_non_advanced_revision_requires_no_extra_verification():
    report = revision(RevisionAction(
        kind="roll_boundary",
        boundary_index=1,
        boundary_shift_seconds=.2,
        reason="cheap motion-match roll",
    ))
    assert required_advanced_action_boundaries(report) == set()
    result = verify_revision_actions(report, None)
    assert result.status == "not_required"
    assert result.verified_boundaries == []
    assert result.failed_boundaries == []


def test_advanced_action_roll_requires_same_boundary_confirmed_as_action_cut():
    report = revision(RevisionAction(
        kind="roll_boundary",
        boundary_index=1,
        boundary_shift_seconds=.25,
        verification_kind="advanced_action_timing",
        reason="dense flow roll",
    ))
    assert required_advanced_action_boundaries(report) == {1}

    result = verify_revision_actions(report, refinement())
    assert result.status == "pass"
    assert result.verified_boundaries == [1]
    assert result.failed_boundaries == []


def test_missing_refinement_fails_mandatory_verification():
    report = revision(RevisionAction(
        kind="roll_boundary",
        boundary_index=2,
        boundary_shift_seconds=.2,
        verification_kind="advanced_action_timing",
        reason="dense flow roll",
    ))
    result = verify_revision_actions(report, None)
    assert result.status == "failed"
    assert result.failed_boundaries == [2]


def test_unchanged_unresolved_or_demoted_refinement_is_not_enough():
    report = revision(RevisionAction(
        kind="roll_boundary",
        boundary_index=1,
        boundary_shift_seconds=.2,
        verification_kind="advanced_action_timing",
        reason="dense flow roll",
    ))
    for status in ("unchanged", "unresolved", "demoted"):
        result = verify_revision_actions(report, refinement(status=status, refined="hard_cut" if status == "demoted" else "action_cut"))
        assert result.status == "failed"
        assert result.failed_boundaries == [1]


def test_confirmation_of_wrong_mechanism_fails_verification():
    report = revision(RevisionAction(
        kind="roll_boundary",
        boundary_index=1,
        boundary_shift_seconds=.2,
        verification_kind="advanced_action_timing",
        reason="dense flow roll",
    ))
    result = verify_revision_actions(report, refinement(status="confirmed", base="directional_bridge", refined="directional_bridge"))
    assert result.status == "failed"
    assert result.failed_boundaries == [1]
