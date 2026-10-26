# MONTER v0.24 — Final Critic

The CINEMA-0 loop should not finish with separate islands of evidence.

Before v0.24, MONTER had:

- a pre-render editorial `critic-report.json`,
- a post-encode `render-analysis.json`,
- and an optional `audio-mix-audit.json`.

`final-critic-report.json` now consolidates those sources while preserving their domains and keeping reviseability explicit.

## Why another critic artifact?

A render-integrity failure is not the same kind of problem as a weak shot selection.

For example:

```text
energy_mismatch
```

may be addressable by replacing a segment with another analyzed shot.

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

v0.24 is intentionally strict.

Only editorial finding codes already supported by the deterministic revision engine are marked `automatic_candidate`:

```text
energy_mismatch
low_confidence_selection
immediate_repetition
```

This does **not** mean v0.24 automatically executes another revision after rendering. It means the final critic can safely identify which findings are candidates for a future bounded second-pass loop.

Everything else remains `manual_only` unless a real deterministic fix contract is implemented.

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

A full run now follows:

```text
EDIT / CTL CRITIC
  -> RENDER
  -> AUDIO MIX AUDIT
  -> RENDER RE-ANALYSIS
  -> FINAL CRITIC
  -> PRODUCTION REPORT
```

`production-report.json` derives its overall pass/review state from the Final Critic.

The earlier `critic-report.json` remains in the project because it is still useful pre-render editorial evidence and revision input.

## Portable review

`final-critic-report.json` is included in `.monter.zip`.

Studio imports it as typed evidence and rejects it if its `projectId` does not match the project manifest.

## Intentional limits

v0.24 does not yet:

- automatically run a second edit revision after rendering,
- claim that render warnings are edit-fixable,
- map renderer failures to code patches,
- measure semantic continuity,
- judge logo/text readability,
- or infer a single aesthetic score.

The next safe step is a **bounded post-render revision policy** that may act only on `automatic_candidate` editorial findings and must re-render/re-analyze before accepting the revision.
