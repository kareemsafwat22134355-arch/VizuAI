# MONTER v0.28 — Temporal Dense-Flow Action Timing

v0.28 upgrades selective dense-flow analysis from a mostly directional signal into temporal evidence that can validate **where an action cut lands**.

The goal is not to run optical flow across the whole project. MONTER still spends dense-flow compute only on scheduler-selected boundary windows.

## Why this exists

Before v0.28, MONTER could use cheap VIR motion anchors to recognize plausible action timing and could use dense flow to validate borderline directional bridges.

But the dense-flow executor collapsed each analysis window into averages such as:

- mean magnitude,
- p90 magnitude,
- mean `dx/dy`,
- directional coherence.

Those statistics can answer “are these shots moving in compatible directions?” but they cannot answer:

> Where, inside this boundary window, did the motion actually rise and peak?

v0.28 preserves that temporal information.

## Selective execution remains bounded

The scheduler already requests `dense_flow` for an `action_cut` only when cheap phase evidence is plausible but not decisive:

```text
0.60 <= phaseCompatibility < 0.90
```

The expensive pass still runs only inside narrow source windows around the selected boundary and remains capped by `max_advanced_boundaries`.

No heavyweight model is downloaded automatically.

The current backend remains:

```text
OpenCV Farneback
```

This is an 8GB-RAM-first deterministic CPU baseline, not RAFT.

## Temporal evidence

`DenseFlowWindowSummary` now preserves additive temporal fields:

```text
peakMagnitude
peakTimeSeconds
onsetTimeSeconds
temporalContrast
```

The fields are additive/defaulted, so existing `advanced-analysis-results-0.1` artifacts remain readable.

For every sampled flow pair, the executor keeps its source time and mean flow magnitude.

### Peak

`peakTimeSeconds` is the source time of the largest sampled mean flow magnitude inside the analysis window.

### Onset

`onsetTimeSeconds` is the first sampled pair, before or at the peak, whose mean magnitude reaches at least 35% of the peak.

### Temporal contrast

```text
temporalContrast = peakMagnitude / meanMagnitude
```

Flat motion windows therefore remain weak evidence even if they contain non-zero motion.

## Source-cut identity

Advanced-analysis requests now preserve the source cut positions used when the request was created:

```text
leftSourceOutSeconds
rightSourceInSeconds
```

The executor copies request evidence into each boundary result. This allows the refinement layer to express localized motion events as offsets from the actual edit point rather than as isolated timestamps.

## Action-cut refinement

For an ambiguous `action_cut`, the refinement layer uses:

```text
outgoing event = left peak
incoming event = right onset, falling back to right peak
```

It computes:

```text
leftActionOffsetSeconds
rightActionOffsetSeconds
actionOffsetDisagreementSeconds
suggestedBoundaryShiftSeconds
```

where the suggested shift is the mean of the two event offsets.

## Reliability gate

Temporal dense flow is allowed to overrule cheap evidence only when both sides satisfy:

```text
sampleCount >= 2
temporalContrast >= 1.05
peakMagnitude > 0
```

Missing, failed, undersampled, or temporally flat evidence remains `unresolved` and preserves the cheaper decision.

## Confirming the current cut

If both localized events already land close to the current source cut:

```text
max(abs(leftOffset), abs(rightOffset)) <= 0.16s
```

then the refinement becomes:

```text
status = confirmed
refinedMechanism = action_cut
```

CTL keeps the zero-duration `motion_peak_cut` and carries the advanced evidence for downstream inspection.

## Contradictory timing

If the localized outgoing and incoming events disagree strongly on where a shared cut should land:

```text
abs(leftOffset - rightOffset) >= 0.28s
```

then the refinement becomes:

```text
status = demoted
refinedMechanism = hard_cut
```

MONTER prefers an intentional discontinuity over false cut-on-action continuity.

## Repairable common shift

If both events suggest roughly the same local shift, but the current cut is not already aligned, and the shift remains inside the bounded timing window:

```text
max(abs(offsets)) <= 0.45s
```

then v0.28 does **not** mutate the edit.

Instead it preserves the action-cut intent and exposes:

```text
suggestedBoundaryShiftSeconds
```

inside transition-refinement evidence. The CTL compiler copies it into transition evidence as:

```text
advancedSuggestedBoundaryShiftSeconds
```

This separation is deliberate:

```text
REFINEMENT = evidence / decision
REVISION   = mutation
```

A later deterministic revision layer may consume this evidence under the same rollback-safe transaction rules already used by MONTER.

## CTL behavior

Refinement evidence is copied into typed CTL transition evidence with an `advanced...` prefix.

Examples:

```text
advancedLeftPeakTimeSeconds
advancedRightOnsetTimeSeconds
advancedLeftActionOffsetSeconds
advancedRightActionOffsetSeconds
advancedSuggestedBoundaryShiftSeconds
```

When action timing is demoted, CTL emits a deliberate zero-duration `hard_cut`.

When action timing is confirmed or remains repairable-but-unmutated, CTL preserves `motion_peak_cut` and carries the evidence.

## Real encoded-media gate

The Bridge test suite now generates real H.264 fixture videos with FFmpeg and executes OpenCV dense flow over them.

The gate requires both windows to produce:

- samples,
- a peak timestamp,
- an onset timestamp,
- timestamps inside the requested source range,
- temporal magnitude evidence,
- and preserved request/source-cut evidence.

This prevents the timing contract from existing only in synthetic Python objects.

## Intentional limits

v0.28 does not:

- run dense flow across all shots,
- download RAFT automatically,
- infer pose, gaze, semantic action completion, or object identity,
- mutate timeline timing from the refinement layer,
- treat flat motion as reliable action evidence,
- or collapse directional and temporal evidence into one opaque score.

The next safe step is to let the revision layer consume a reliable `advancedSuggestedBoundaryShiftSeconds` as a typed bounded action-cut timing revision, while retaining the existing one-candidate post-render rollback transaction.
