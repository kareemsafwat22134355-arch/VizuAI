# Selective advanced analysis — v0.16

MONTER must not run expensive computer-vision models over every frame of every source file.

v0.16 introduces a **compute scheduling layer** that decides which edit boundaries justify more analysis after the cheap VIR and `CutSignature` passes are already available.

## Artifact

`advanced-analysis-plan.json` uses schema `advanced-analysis-plan-0.1` and contains:

- `projectId`
- `maxBoundaries` — the current expensive-analysis budget
- `requests` — selected boundary windows, sorted by priority
- `skippedBoundaries` — boundaries intentionally left cheap, including the reason
- `notes` — execution limitations and current policy

Each selected request stores:

- the edit `boundaryIndex`
- priority from 0–1
- requested features: `dense_flow`, `depth`, or later `segmentation`
- exact outgoing and incoming source windows
- asset, shot, and segment identity for both windows
- the reason expensive analysis is justified
- the cheap evidence that caused the request

## Current scheduling policy

### Feasible zoom relation

A feasible `zoom_bridge` can request:

- `dense_flow`
- `depth`

Depth is not scheduled globally. It is only requested where a scale relation already exists and verified source handles make a deeper spatial analysis useful.

### Borderline directional relation

A feasible `directional_bridge` requests `dense_flow` only when cheap global-motion evidence is plausible but not already strong enough. Strong directional matches stay cheap.

### Ambiguous cut-on-action

A plausible `action_cut` requests `dense_flow` only when the phase score is supportive but not decisive.

### Adjacent timewarp

If an adjacent event-driven timewarp already owns the temporal transformation, extra transition analysis is skipped rather than stacking expensive operations blindly.

## Source-window safety

Advanced requests may inspect:

- the selected source range, and
- source handles already verified by transition-opportunity synthesis.

They must not invent source time outside those ranges. Tests explicitly guard the outgoing source-in boundary and incoming verified handle window.

## Compute budget

The production pipeline emits a plan with a default budget of four boundaries. A plan can be regenerated without re-running ingest or VIR:

```bash
monter-analysis-plan \
  --ctl .monter/ctl.json \
  --opportunities .monter/transition-opportunities.json \
  --max-boundaries 2 \
  --out .monter/advanced-analysis-plan.json
```

This lets an 8 GB machine lower the expensive-analysis budget independently from the edit itself.

## Important: scheduler, not executor

v0.16 **does not execute** RAFT, SAM2, Video Depth Anything, RIFE, or any other heavyweight model.

The artifact is a deterministic work order for future backends. Keeping scheduling separate from execution lets MONTER prove *why* a costly pass is needed before spending GPU/RAM time.

A later milestone may execute only the selected windows and cache the resulting dense-flow/depth/mask artifacts by input/model/parameter fingerprint.
