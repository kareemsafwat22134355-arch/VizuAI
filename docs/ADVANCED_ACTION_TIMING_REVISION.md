# MONTER v0.29 — Advanced Action-Timing Revision

v0.29 closes the loop opened by v0.28.

v0.28 can use selective dense optical flow to say:

```text
this is still a valid action-cut idea,
but both sides support moving the shared cut by approximately +d seconds
```

v0.29 turns that evidence into a deterministic, rollback-safe edit action.

## Separation of responsibilities

The layers stay intentionally separate:

```text
ADVANCED ANALYSIS
  -> localize motion peak/onset times

TRANSITION REFINEMENT
  -> confirm / demote / expose suggestedBoundaryShiftSeconds

CTL
  -> carry advancedSuggestedBoundaryShiftSeconds as typed transition evidence

CRITIC
  -> revalidate physical edit feasibility
  -> emit action_cut_timing_shift_needed

REVISION
  -> apply a bounded roll edit using the authorized typed shift

POST-RENDER TRANSACTION
  -> recompile / re-analyze / re-render / re-watch
  -> promote only if Final Critic == pass
```

The refinement layer still does not mutate the timeline.

## Critic finding

The new editorial finding is:

```text
action_cut_timing_shift_needed
```

It is emitted only when the canonical CTL boundary is still:

```text
mechanism = motion_peak_cut
advancedRefinementStatus = unchanged
advancedBaseMechanism = action_cut
advancedRefinedMechanism = action_cut
```

and CTL carries a numeric:

```text
advancedSuggestedBoundaryShiftSeconds
```

The Critic does not trust that value blindly. It rechecks the current edit against VIR shot bounds before authorizing mutation.

## Typed shift evidence

`CriticFinding` now includes the additive field:

```text
suggestedShiftSeconds
```

`FinalCriticFinding` preserves the same field so the post-render authorization remains machine-readable all the way through the consolidated quality gate.

The shift is therefore not recovered from prose and is not recomputed from a different heuristic.

## Physical feasibility gate

The action is rejected unless all of these remain true at revision time:

- boundary index still exists,
- `abs(shift) <= 0.45s`,
- both adjacent shots still exist in VIR,
- left clip remains at least `0.60s`,
- right clip remains at least `0.60s`,
- shifted left source-out stays inside the detected left shot,
- shifted right source-in stays inside the detected right shot,
- source ranges remain positive,
- the timeline stays contiguous,
- and neither adjacent segment is being replaced in the same revision pass.

## Re-analysis eligibility guard

A subtle failure mode is possible if a timing revision removes the cheap evidence that originally made the boundary an action-cut candidate.

Without a guard, the revised candidate could become a cheap `hard_cut`, skip dense-flow analysis, lose the original finding, and appear to pass without verifying the new action timing.

v0.29 prevents that.

Before authorizing the roll, MONTER applies the proposed delta to a temporary copy of the edit and reruns transition-opportunity synthesis.

The same boundary must still resolve to:

```text
action_cut
```

Otherwise the revision is rejected.

This guarantees that the post-render candidate can re-enter the v0.28 dense-flow timing pass and verify the new cut location.

## Mutation

The actual NLE operation is still the typed:

```text
roll_boundary
```

because the timeline operation is identical to a normal roll edit.

For delta `d`:

```text
left.timelineOut += d
left.sourceOut   += d
right.timelineIn += d
right.sourceIn   += d
```

The first timeline in-point and final timeline out-point do not move, so total sequence duration remains unchanged.

The revision report stores:

```text
boundaryIndex
boundaryShiftSeconds
```

The action reason explicitly records that the shift came from selective dense-flow timing evidence rather than cheap motion anchors.

## Final Critic policy

`action_cut_timing_shift_needed` is explicitly whitelisted as:

```text
automatic_candidate
```

It still cannot authorize a mutation when the Final Critic contains a render-integrity or audio-integrity error.

The post-render transaction keeps its existing one-attempt limit.

## Candidate acceptance

After the roll, MONTER rebuilds dependent evidence:

```text
transition opportunities
advanced analysis plan
selective dense flow
transition refinement
CTL
editorial critic
sound plan
audio plan
render
mix audit
render re-analysis
Final Critic
```

The candidate is promoted only when:

```text
candidate final-critic-report.json status == pass
```

A disappearing finding by itself is not enough.

## Conflict policy

If either adjacent segment is also scheduled for whole-shot replacement in the same revision pass, the advanced timing roll is skipped.

Replacing the shot pair invalidates the flow evidence that localized the original action timing.

## Intentional limits

v0.29 does not:

- invent timing shifts without completed v0.28 evidence,
- move deliberate hard cuts,
- operate across timewarp-owned boundaries,
- exceed the 0.45s local timing window,
- retry multiple timing candidates,
- use pose/gaze/semantic action models,
- or bypass candidate render/re-analysis.

The system now has a closed deterministic chain from selective physical timing evidence to a typed edit mutation and back through full post-render verification.
