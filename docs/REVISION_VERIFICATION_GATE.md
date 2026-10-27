# MONTER v0.30 — Revision Verification Gate

v0.30 closes a safety gap in the post-render revision transaction.

Before this milestone, a candidate edit could be created from reliable selective dense-flow timing evidence, rendered again, and accepted if the Final Critic passed. That was necessary but not sufficient for advanced action-timing rolls: the boundary that motivated the mutation should also be re-measured after the mutation and explicitly confirmed by the same advanced evidence class.

## Contract

An advanced action-timing roll now carries a typed revision marker:

- `verificationKind = "advanced_action_timing"`

That marker is written by the deterministic revision engine, not inferred later from prose.

The post-render transaction collects all boundaries carrying this marker and treats them as mandatory verification boundaries.

## Forced advanced re-analysis

A revised action boundary must be re-run through selective dense flow even if cheap VIR phase evidence becomes very strong after the roll.

`build_advanced_analysis_plan(...)` therefore accepts a set of forced action boundaries.

For a forced boundary:

- the boundary must still be a feasible `action_cut` opportunity;
- adjacent timewarp ownership still blocks the request;
- dense flow is mandatory;
- priority is `1.0`;
- the request carries `forcedRevisionVerification = true`;
- mandatory requests consume advanced-analysis budget before optional requests;
- if mandatory requests exceed the configured budget, the effective budget expands rather than silently dropping verification.

If the revised boundary is no longer a feasible action-cut opportunity, no fake verification result is synthesized. The later verification gate fails closed.

## Verification rule

A revision marked `advanced_action_timing` passes verification only when the candidate `transition-refinement.json` contains the same boundary with:

- `status = "confirmed"`
- `baseMechanism = "action_cut"`
- `refinedMechanism = "action_cut"`

The following all fail verification:

- missing refinement result;
- `unchanged`;
- `unresolved`;
- `demoted`;
- confirmation of a different mechanism;
- advanced pass disabled or unavailable.

This is intentionally stricter than simply checking that the old `action_cut_timing_shift_needed` finding disappeared.

## Candidate acceptance

Candidate promotion now requires both:

1. `Final Critic == pass`
2. revision verification is not `failed`

For ordinary replacement/slip/roll revisions that do not carry a verification marker, the verification status is `not_required` and the existing transaction behavior is preserved.

For advanced action-timing revisions:

- `pass` allows normal promotion;
- `failed` rejects the candidate even when Final Critic is otherwise `pass`.

Rejected candidates remain inspectable under `post-render-candidate-01`, and canonical baseline artifacts remain untouched.

## Transaction report

`post-render-revision-report.json` remains the single transaction artifact and now records:

- `verificationStatus`: `not_required | pass | failed`
- `verifiedBoundaries`
- `failedVerificationBoundaries`

Studio imports these fields directly from portable `.monter.zip` bundles.

## Why this matters

MONTER is intended to revise edits because stronger evidence justified a change, not because a mutation happened to remove a warning. v0.30 makes that distinction executable.

The evidence loop is now:

`dense-flow evidence → typed roll authorization → bounded mutation → forced dense-flow re-analysis → explicit confirmation → render/re-watch → Final Critic → promotion`

The order of rendering and verification execution may overlap in implementation, but promotion requires both gates to succeed.

## Intentional limits

v0.30 does not:

- introduce another edit primitive;
- run dense flow globally;
- retry multiple timing candidates;
- override timewarp ownership;
- treat `unchanged` as equivalent to `confirmed`;
- promote a candidate merely because the Final Critic finding disappeared;
- change the one-candidate rollback-safe transaction policy.

## Acceptance gates

The milestone is accepted only if:

- an advanced action-timing revision action is tagged automatically;
- strong cheap phase evidence cannot skip mandatory dense-flow re-verification;
- missing or non-confirmed refinement fails closed;
- confirmed action-cut refinement passes;
- normal non-advanced revisions remain `not_required` and retain existing behavior;
- Studio preserves the verification fields through bundle import;
- existing Studio build/tests and Bridge pytest + encoded/real-media smoke remain green.
