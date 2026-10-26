# MONTER v0.22 — Autonomous Production Pass

`monter produce` is now the bounded North Star entrypoint for the deterministic CINEMA-0 pipeline.

The purpose of this milestone is orchestration, not a new effect or model. The system already had rough planning, selective advanced analysis, transition refinement, source-audio J/L editing, a Sound Director, rendering, and audio headroom validation. v0.22 connects those stages into one ordered production pass so the final render is driven by the same evidence that the project artifacts describe.

## Default flow

```text
INGEST
  -> PROXY
  -> VIR
  -> DIRECTOR PLAN
  -> ROUGH EDIT
  -> CRITIC / BOUNDED REVISIONS
  -> TRANSITION OPPORTUNITIES
  -> ADVANCED ANALYSIS SCHEDULER
  -> SELECTIVE DENSE FLOW EXECUTION
  -> TRANSITION REFINEMENT
  -> FINAL CTL
  -> SOUND DIRECTOR
  -> SOURCE-AUDIO EDIT PLAN
  -> FINAL RENDER
  -> AUDIO MIX AUDIT
  -> PRODUCTION REPORT
```

Advanced analysis is deliberately scheduled **after** the rough edit and bounded revision loop have stabilized. This prevents dense-flow windows from being computed for trims or boundaries that are subsequently moved by a revision.

The Sound Director then analyzes the **final** CTL, not a stale pre-refinement version.

## Command

```bash
monter produce RAW \
  --name "MONTER Project" \
  --work-dir .monter \
  --duration 15 \
  --music music.wav
```

The advanced pass and Sound Director are enabled by default.

Useful bounded controls:

```bash
--max-revisions 2
--max-advanced-boundaries 4
--advanced-sample-fps 12
--advanced-analysis-width 320
--max-jl-cuts 2
--audio-safe-threshold-dbfs -0.5
```

Diagnostic opt-outs:

```bash
--no-advanced-pass
--no-sound-pass
--no-render
```

`--no-advanced-pass` still emits `advanced-analysis-plan.json`; it only skips the execution/refinement stage.

## Artifacts

A default full run can now emit:

```text
project.monter.json
vir.monter.json
director-plan.json
edit-plan.json
ctl.json
critic-report.json
transition-opportunities.json
advanced-analysis-plan.json
advanced-analysis-results.json
transition-refinement.json
sound-director.json
audio-edit-plan.json
audio-mix-audit.json   # when rendered output contains audio
edit.otio
rough-cut.mp4
production-report.json
```

`ctl.json` is the final refined CTL that is actually rendered.

## Production report observability

`production-report.json` records whether each optional pass actually ran and includes:

- `advancedPassExecuted`
- `advancedBoundariesExecuted`
- `transitionRefinementsApplied`
- `soundPassExecuted`
- `soundNonSyncSelected`
- `audioMixAudited`
- `audioMixSafe`

This keeps the report truthful when a pass is disabled, no advanced boundaries are scheduled, no J/L cut is selected, or a render contains no audio.

## Safety and compute rules

### Selective CV remains bounded

The default advanced budget is four boundaries. Dense flow runs only inside scheduler-selected source windows using the existing OpenCV Farneback CPU baseline.

Depth and segmentation requests remain explicit `backend_unavailable` results until real optional backends are configured. v0.22 does not download SAM2, Video Depth Anything, RAFT, RIFE, or another heavyweight model automatically.

### Advanced evidence cannot bypass feasibility guards

Transition refinement can confirm or demote the existing directional-bridge proposal, but final CTL compilation still enforces source handles, timewarp adjacency, and deterministic renderer constraints.

### Sound remains sparse by design

The Sound Director still selects at most two non-sync J/L boundaries by default. Silence and synchronous cuts remain first-class outcomes.

### Mix safety is a gate, not mastering

If the rendered output contains source audio or music, MONTER runs the existing decoded-sample peak audit after AAC encoding. An unsafe mix marks the production `needs_review` and records the reason in warnings.

This is not LUFS mastering and is not a true-peak meter.

## Intentional limits

v0.22 does **not** add:

- semantic dialogue understanding,
- speaker identity,
- room-tone classification,
- automatic music ducking,
- real depth/segmentation backends,
- a generative-video bridge,
- a cloud execution layer,
- or an NLE-style timeline UI.

The milestone closes an orchestration gap: existing intelligence now affects the final one-command render in the correct temporal order.
