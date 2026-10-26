# Evidence-driven transition refinement — v0.18

MONTER should not spend compute unless the result can change an editorial decision.

v0.18 closes the first feedback loop between selective advanced analysis and CTL compilation:

```text
transition-opportunities.json
        ↓
advanced-analysis-plan.json
        ↓
advanced-analysis-results.json
        ↓
transition-refinement.json
        ↓
refined CTL
```

## Current scope

The first refinement policy is deliberately narrow: executed dense flow may **confirm or demote a `directional_bridge`**.

It does not claim to infer semantics, attention, depth, subject identity, or action timing from a flow summary.

## Confirmation

A directional bridge can be confirmed only when:

- dense-flow execution completed
- both outgoing and incoming windows have usable directional coherence
- flow-direction compatibility is at least `0.72`

The base bridge remains deterministic and still requires the original source-handle and CTL feasibility guards.

## Demotion

A directional bridge can be demoted when:

- dense-flow execution completed
- both windows have usable directional coherence
- flow-direction compatibility is at most `0.35`

The refined mechanism becomes:

- `action_cut` when the existing cheap phase evidence already supports cut-on-action
- otherwise `hard_cut`

The refined CTL maps `action_cut` to the existing zero-duration `motion_peak_cut` primitive.

## Unresolved evidence

Dense flow does **not** overrule the base recommendation when:

- the advanced result is missing
- dense-flow execution failed
- one side lacks usable frame-pair samples
- directional coherence is below the refinement threshold

This prevents weak expensive evidence from being treated as automatically superior to cheap evidence.

## Stale-refinement guard

The refined compiler recomputes the deterministic transition opportunity from the current edit/VIR. If the refinement report says its base mechanism was different from the current recommendation, compilation stops with a stale-refinement error.

A refinement generated for an older edit therefore cannot silently modify a newer timeline.

## Commands

Generate the refinement report:

```bash
monter-transition-refine \
  --opportunities .monter/transition-opportunities.json \
  --results .monter/advanced-analysis-results.json \
  --out .monter/transition-refinement.json
```

Compile a CTL variant that consumes it:

```bash
monter-refined-compile \
  --edit-plan .monter/edit-plan.json \
  --vir .monter/vir.monter.json \
  --refinement .monter/transition-refinement.json \
  --out .monter/ctl.refined.json
```

Render that CTL explicitly:

```bash
monter render \
  --manifest .monter/project.monter.json \
  --ctl .monter/ctl.refined.json \
  --proxy-dir .monter/proxies \
  --out .monter/rough-cut.refined.mp4
```

## Studio

Studio exposes refinement separately from opportunity synthesis and advanced execution. A boundary shows:

- base mechanism
- refined mechanism
- `confirmed`, `demoted`, `unchanged`, or `unresolved`
- flow-direction compatibility
- left/right directional coherence
- refinement reason and evidence

This keeps the reasoning chain inspectable instead of hiding a post-analysis override inside CTL.

## Next limits

v0.18 does not yet use dense flow to infer better action timing. It also does not refine zoom bridges until a real depth backend exists. Those should remain separate milestones with evidence appropriate to each decision type.
