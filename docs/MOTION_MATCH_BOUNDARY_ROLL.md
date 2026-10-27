# MONTER v0.27 — Motion-Match Boundary Roll

v0.27 adds a second typed timing revision primitive: a bounded **roll edit** on an existing `motion_match_cut`.

It complements v0.26 source-trim realignment:

```text
SLIP
  timeline boundary stays fixed
  source windows move together

ROLL
  timeline boundary moves
  outgoing clip gets longer/shorter
  incoming clip changes by the opposite amount
  total sequence duration stays fixed
```

## Why this exists

Sometimes the selected shots are correct and the desired motion anchors agree on where the cut should happen, but a slip edit cannot reach them because moving the entire incoming/outgoing source window would exceed source handles.

In that case, moving the shared boundary is the correct NLE primitive.

## Eligibility

Boundary roll is considered only when:

1. CTL already labels the boundary `motion_match_cut`.
2. Neither adjacent segment has a timewarp.
3. v0.26 slip realignment is **not** feasible.
4. Current phase compatibility is below `0.60`.
5. Outgoing motion peak and incoming onset/peak anchors have confidence at least `0.80`.
6. Both anchors ask for nearly the same boundary movement (difference <= `0.10s`).
7. Absolute boundary shift is <= `0.45s`.
8. Both resulting segment durations remain at least `0.60s`.
9. Shifted source boundaries stay inside shot ranges.
10. Resulting phase compatibility is at least `0.90` and gains at least `0.40`.

If any condition fails, MONTER leaves the boundary unchanged.

## Edit semantics

For a positive roll delta `d`:

```text
left.timelineOut += d
left.sourceOut   += d
right.timelineIn += d
right.sourceIn   += d
```

Sequence start, sequence end, and `actualDurationSeconds` remain unchanged.

The machine-readable revision action is:

```text
roll_boundary
```

with:

```text
boundaryIndex
boundaryShiftSeconds
```

## Protected cases

MONTER will not use this primitive on:

- deliberate `hard_cut` boundaries,
- boundaries next to timewarps,
- boundaries where v0.26 slip already provides a safe solution,
- boundaries whose adjacent segment is being replaced in the same revision pass,
- rolls that would create a sub-600ms segment,
- or rolls outside the physical anchor window.

## Critic evidence

The new finding is:

```text
motion_match_boundary_roll_needed
```

and the core metric is:

```text
recoverable_motion_match_roll_count
```

The finding is emitted only after MONTER proves the deterministic roll is feasible.

## Final Critic and post-render revision

`motion_match_boundary_roll_needed` is explicitly whitelisted as an `automatic_candidate` because the deterministic `roll_boundary` action exists.

The post-render transaction may use it under the same v0.25 safeguards:

- one candidate attempt,
- no render/audio integrity error,
- full recompile/render/re-analysis,
- candidate accepted only when Final Critic status becomes `pass`,
- baseline snapshot before promotion.

## Intentional limits

v0.27 does not:

- move arbitrary hard cuts,
- retime clips,
- co-edit a timewarp,
- create or change transition effects,
- infer semantic action completion,
- or perform unbounded ripple edits across multiple downstream clips.

It is a local two-clip roll edit driven only by measured motion-phase evidence.
