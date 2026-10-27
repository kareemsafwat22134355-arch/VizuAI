# MONTER v0.24+ — Final Critic

The CINEMA-0 loop should not finish with separate islands of evidence.

Before v0.24, MONTER had:

- a pre-render editorial `critic-report.json`,
- a post-encode `render-analysis.json`,
- and an optional `audio-mix-audit.json`.

`final-critic-report.json` consolidates those sources while preserving their domains and keeping reviseability explicit.

## Why another critic artifact?

A render-integrity failure is not the same kind of problem as a weak shot selection or recoverable cut timing.

For example:

```text
energy_mismatch
motion_match_timing_weak
motion_match_boundary_roll_weak
```

may be addressable by a deterministic edit action.

But:

```text
duration_drift
near_black_render
audio_headroom_failure
```

should not be “fixed” by randomly changing the edit. They indicate renderer, media, or mix integrity problems.

The Final Critic makes that distinction machine-readable before MONTER is allowed to attempt a post-render revision loop.

## Schema

```text
final-critic-0.1
```

Each finding includes:

- `domain`
- `severity`
- `reviseability`
- `sourceArtifact`
- optional segment/boundary references
- the evidence message

Domains are:

```text
editorial
render_integrity
audio_integrity
```

Reviseability is:

```text
automatic_candidate
manual_only
not_applicable
```

## Automatic-candidate policy

The policy remains intentionally strict.

Only editorial finding codes already supported by the deterministic revision engine are marked `automatic_candidate`:

```text
energy_mismatch
low_confidence_selection
immediate_repetition
motion_match_timing_weak
motion_match_boundary_roll_weak
```

The first three are segment-replacement actions.

`motion_match_timing_weak`, added in v0.26, is a bounded **slip edit**: source windows move while timeline cut position and clip durations stay fixed.

`motion_match_boundary_roll_weak`, added in v0.27, is a bounded **roll edit** fallback: the timeline boundary moves while the left and right clip durations change by equal-and-opposite amounts so the total sequence duration stays fixed.

The roll action is considered only when the less-invasive slip action is not feasible.

Everything else remains `manual_only` unless a real deterministic fix contract is implemented and explicitly whitelisted.

## Status semantics

The final critic uses three states:

```text
pass
needs_revision
needs_review
```

### `needs_review`

Takes priority when render or audio integrity contains an error.

Examples:

- encoded duration failure,
- catastrophic blank render,
- unsafe post-encode audio headroom.

### `needs_revision`

Used when the editorial critic still requires revision and there is no higher-priority integrity error.

### `pass`

Used when there is no integrity error and the editorial critic passes.

Warning-only render evidence such as a long static hold or cheap energy mismatch does not automatically fail the final critic.

## Metrics remain separate

The Final Critic copies editorial metrics into the `editorial` domain and adds physical metrics such as:

- render duration drift,
- black-frame fraction,
- render energy alignment,
- decoded audio max dBFS.

MONTER still does not collapse these into a single quality score.

## Production integration

A full run follows:

```text
EDIT / CTL CRITIC
  -> RENDER
  -> AUDIO MIX AUDIT
  -> RENDER RE-ANALYSIS
  -> FINAL CRITIC
  -> OPTIONAL BOUNDED POST-RENDER REVISION
  -> PRODUCTION REPORT
```

`production-report.json` derives its overall pass/review state from the canonical Final Critic.

The earlier `critic-report.json` remains in the project because it is still useful pre-render editorial evidence and revision input.

## Portable review

`final-critic-report.json` is included in `.monter.zip`.

Studio imports it as typed evidence and rejects it if its `projectId` does not match the project manifest.

## Intentional limits

The Final Critic does not:

- claim that render warnings are edit-fixable,
- map renderer failures to code patches,
- measure semantic continuity,
- judge logo/text readability,
- infer a single aesthetic score,
- or automatically grant reviseability to a newly invented finding code.

Every automatic finding must map to a deterministic edit action and remain subject to the single-candidate post-render transaction gate.
