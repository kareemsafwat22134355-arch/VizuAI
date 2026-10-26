# MONTER v0.26 — Motion-Match Source-Trim Realignment

v0.26 adds the first deterministic revision action that fixes **cut timing without replacing the shot**.

The target is intentionally narrow: an existing `motion_match_cut` whose screen-motion relation is strong enough to justify the mechanism, but whose selected source trims miss strong motion-phase anchors by a small amount.

MONTER may slide the source windows while keeping the timeline edit duration unchanged.

## Why this action exists

Before v0.26, the revision engine mainly responded to editorial problems by replacing a whole segment.

That is too destructive when the shot choice is good but the cut is simply late or early relative to the action.

A better edit operation is:

```text
keep shot A
keep shot B
keep timeline cut position
shift source window A toward outgoing motion peak
shift source window B toward incoming motion onset/peak
recompile and re-criticize
```

This expands revision vocabulary instead of adding another transition preset.

## Eligibility

A boundary is considered only when:

1. CTL already compiled it as `motion_match_cut`.
2. Current motion-phase compatibility is below `0.60`.
3. The outgoing shot has a `motion_peak` anchor with confidence at least `0.75`.
4. The incoming shot has a `motion_onset` or `motion_peak` anchor with confidence at least `0.75`.
5. Each required source-window shift is at most `0.45s`.
6. Shifted source ranges remain inside the detected shot ranges.
7. Neither adjacent segment has a timewarp.
8. The proposed edit raises phase compatibility to at least `0.90`.
9. Phase compatibility improves by at least `0.40`.

If any condition fails, no automatic timing revision is proposed.

## Deliberate hard cuts are protected

`hard_cut` boundaries are never candidates for this action.

MONTER does not infer that every strong motion anchor should become a cut-on-action. A hard cut can intentionally create rupture, contrast, or discontinuity.

The new critic finding exists only when a boundary was already classified as `motion_match_cut` from physical direction evidence.

## Timewarp guard

A boundary adjacent to a CTL timewarp is excluded.

Shifting the source window would invalidate the current retiming slices and anchor assumptions. v0.26 does not attempt to co-revise trim timing and timewarp geometry in one action.

## Finding and metric

The editorial critic adds:

```text
motion_match_timing_weak
```

and metric:

```text
recoverable_motion_match_timing_count
```

The metric is a core revision metric because the finding is emitted only after MONTER proves a bounded deterministic fix exists.

The finding keeps the `boundaryIndex` so revision and post-render filtering do not lose boundary identity.

## Revision action

The machine-readable action is:

```text
realign_boundary
```

It records:

- boundary index,
- left source-window shift,
- right source-window shift,
- reason.

The operation changes:

```text
sourceInSeconds
sourceOutSeconds
```

and preserves:

```text
timelineInSeconds
timelineOutSeconds
actualDurationSeconds
```

## Same-pass conflict rule

If either adjacent segment is already scheduled for whole-shot replacement in the same revision pass, boundary realignment is skipped.

Replacement invalidates the original motion-anchor evidence, so MONTER must not apply stale trim shifts to a different shot.

## Final Critic and post-render loop

`motion_match_timing_weak` is explicitly added to the automatic-candidate whitelist.

The bounded post-render transaction may therefore use this action, but all v0.25 safety rules remain:

- at most one candidate,
- no render/audio integrity errors,
- full candidate compile/render/re-analysis,
- promotion only if candidate Final Critic status is exactly `pass`,
- baseline snapshot before accepted promotion.

`post-render-revision-report.json` also gains additive `changedBoundaries` evidence so trim-only revisions remain auditable even when no whole segment was replaced.

## Intentional limits

v0.26 does not:

- move the timeline cut position,
- alter clip duration,
- change deliberate hard cuts,
- repair a boundary next to a timewarp,
- use pose/gaze/subject semantics,
- synthesize a new transition,
- or move trims farther than the bounded physical-anchor window.

Later revisions may add other typed operations, but each must have its own evidence, feasibility contract, and explicit Final Critic whitelist entry.
