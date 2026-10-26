# MONTER v0.25 — Bounded Post-Render Revision

v0.25 closes the first safe revision loop after MONTER has actually rendered and re-watched its output.

The rule is deliberately narrow:

```text
BASELINE FINAL CRITIC
  -> eligible automatic editorial finding?
  -> one candidate edit
  -> full compile / selective analysis / sound / render
  -> re-analyze encoded candidate
  -> candidate Final Critic
  -> PASS: snapshot baseline, promote candidate
  -> otherwise: reject candidate, keep baseline canonical
```

There is no open-ended retry loop.

## Eligibility

A post-render edit attempt is allowed only when all of these are true:

1. `final-critic-report.json` status is `needs_revision`.
2. The Final Critic exposes at least one `automatic_candidate`.
3. No `render_integrity` or `audio_integrity` error is present.
4. A final render and render re-analysis exist.
5. The feature has not been disabled with `--no-post-render-revision`.

The automatic candidate must also map to a finding code already supported by the deterministic revision engine:

```text
energy_mismatch
low_confidence_selection
immediate_repetition
```

Everything else remains manual-only.

## Why integrity failures block edit mutation

If the MP4 has the wrong duration, is catastrophically blank, or has unsafe audio headroom, changing shot selection is not a valid repair strategy.

MONTER therefore refuses a post-render edit mutation whenever the Final Critic contains an integrity error.

This prevents a broken renderer or mix from being hidden behind arbitrary editorial changes.

## Transaction directory

The single candidate is built in:

```text
.monter/post-render-candidate-01/
```

The candidate recomputes the parts of the pipeline that depend on the changed edit:

```text
edit-plan.json
transition-opportunities.json
advanced-analysis-plan.json
advanced-analysis-results.json       # when advanced pass is enabled
transition-refinement.json            # when advanced pass is enabled
ctl.json
critic-report.json
sound-director.json                   # when sound pass is enabled
audio-edit-plan.json                  # when sound pass is enabled
edit.otio
rough-cut.mp4
audio-mix-audit.json                  # when candidate contains audio
render-analysis.json
final-critic-report.json
```

It reuses the canonical analysis proxies and VIR. Expensive evidence is not recomputed globally.

## Acceptance rule

The candidate is accepted only when:

```text
candidate final-critic-report.json status == pass
```

A lower error number, fewer warnings, or a better energy metric is not enough by itself.

This is intentionally conservative: MONTER must prove the revised candidate is physically valid and editorially passing before it becomes canonical.

## Baseline preservation

Before an accepted candidate overwrites canonical outputs, MONTER snapshots the current promotable artifacts into:

```text
.monter/post-render-baseline/
```

Only after that snapshot are the accepted candidate artifacts copied into the canonical `.monter/` paths.

If the candidate is rejected:

- canonical baseline files are untouched,
- `post-render-candidate-01/` remains available for inspection,
- no baseline snapshot is required because nothing was promoted.

## Decision artifact

Every production run writes:

```text
post-render-revision-report.json
```

Schema:

```text
post-render-revision-0.1
```

It records:

- `eligible`
- `attempted`
- `changed`
- `accepted`
- reason
- baseline and candidate Final Critic statuses
- automatic-candidate counts before/after
- changed segment IDs
- local candidate/baseline directory labels
- promoted artifact names

The report is included in `.monter.zip`.

Candidate and baseline media directories are **not** embedded in the portable bundle, so a rejected candidate does not silently double bundle size.

Studio imports the transaction report with a project identity guard.

## Production report

`production-report.json` now exposes:

```text
postRenderRevisionAttempted
postRenderRevisionAccepted
postRenderRevisionCount
```

`postRenderRevisionCount` is bounded to `0` or `1` in v0.25.

## CLI

The post-render candidate is enabled by default when rendering and render re-analysis are enabled.

Disable it for diagnostics with:

```bash
monter produce RAW --no-post-render-revision
```

## Intentional limits

v0.25 does not:

- perform more than one post-render attempt,
- revise render/audio integrity failures,
- learn new revision actions from arbitrary Final Critic findings,
- accept a candidate merely because one metric improved,
- automatically tune transition shaders or renderer code,
- compare semantic identity continuity between baseline and candidate,
- or keep retrying until a score improves.

The next safe expansion is to improve the deterministic revision vocabulary itself, then explicitly whitelist those new actions for post-render use.
