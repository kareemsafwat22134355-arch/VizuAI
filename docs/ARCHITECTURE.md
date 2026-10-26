# MONTER architecture v0.5

## Local Bridge

The Local Bridge owns large media. RAW footage never needs to be uploaded to the Studio.

Current responsibilities:

- enumerate source media recursively
- inspect media with `ffprobe`
- preserve source identity, timebase and technical metadata
- generate low-resolution analysis proxies with FFmpeg
- detect shot/scene boundaries with PySceneDetect
- sample local optical flow and global camera motion from one decode pass per shot
- derive motion-phase edit anchors
- cache per-asset analysis using proxy + analyzer fingerprints
- emit portable project, VIR, director, edit, CTL, critic, transition-opportunity, human-correction, OTIO and production artifacts
- compile selected feasible transition opportunities into typed deterministic CTL primitives
- render deterministic proxy drafts with FFmpeg
- create share bundles that exclude RAW media, proxies and analysis caches

The Bridge is designed for 8 GB RAM machines. Work is streamed through FFmpeg and sampled analysis rather than loading whole video files into Python memory. Expensive analysis is intended to stay progressive and selective.

## MONTER Studio

The Studio is a Next.js application designed for Vercel. It displays lightweight editorial intelligence rather than RAW media.

Current responsibilities:

- project overview and pipeline state
- local `.monter.zip` import in the browser
- rough-cut preview without backend upload
- source/shot intelligence
- director energy curve
- edit-plan reasoning
- CTL transition rationale
- transition-opportunity feasibility and blocked/accepted candidates
- read-only human correction history
- critic dimensions/findings

Studio accepts both CTL v0.1 and v0.2 bundles. Later responsibilities include direct correction authoring, richer waveform regions and benchmark comparisons.

## Boundary

```text
RAW media (local)
    -> Local Bridge
    -> proxies + cached VIR analysis
    -> Director / Planner
    -> transition opportunity synthesis
    -> CTL compiler
    -> deterministic transition/timewarp renderer
    -> Critic / portable .monter.zip
    -> MONTER Studio (browser-local inspection)
    -> human correction ledger
    -> future evaluation / policy-learning layer
```

## Transition opportunity stage

Transition invention is separated from transition rendering. Every edit boundary receives a feasibility report before a non-zero bridge can be considered.

Inputs include:

- outgoing and incoming shot ranges
- actual edit in/out points
- available source handles on both sides
- `CutSignature` direction, zoom, phase and relation evidence
- global-motion confidence

Current candidates are `hard_cut`, `action_cut`, `directional_bridge`, and `zoom_bridge`. `hard_cut` is always valid. Non-zero bridges require both sufficient physical motivation and verified source handles; a motivated idea is rejected if the source media cannot support it safely.

## CTL v0.2 deterministic transition compiler

v0.13 compiles the first non-zero opportunity: `directional_bridge`.

A directional bridge is emitted only when:

- the transition opportunity is feasible and recommended
- both shots share confident cardinal screen direction
- verified source handles exist on both sides
- neither adjacent segment owns an event-driven timewarp

For bridge duration `d`, the renderer expands the outgoing source by `d/2` after the nominal out point and the incoming source by `d/2` before the nominal in point. Those expanded clips overlap for exactly `d`, so total timeline duration remains unchanged. The nominal cut sits at the center of the overlap.

The measured screen direction maps to one deterministic FFmpeg primitive: `slideleft`, `slideright`, `slideup`, or `slidedown`. Inputs are normalized to matching size, frame rate, timebase and pixel format before composition. The renderer checks computed duration against CTL before encoding.

Non-zero transitions adjacent to a timewarp are deliberately deferred and fall back to a zero-duration motion-aware cut. `zoom_bridge` remains a scored feasibility candidate only; it is not yet a compiled renderer primitive.

## Human correction evidence layer

v0.14 records human overrides as supervised evidence without silently changing future policy.

Each `human-corrections.json` event preserves:

- correction kind and explicit target
- original AI decision
- human replacement decision
- compact context/evidence snapshot
- human reason
- source and timestamp

Ledgers are scoped to one `projectId`, use atomic writes, and reject events where the human decision is identical to the AI decision. Portable bundles can include the ledger because it contains editorial metadata rather than RAW media.

This layer is intentionally separated from both `StyleProfile` and automatic planning. A later evaluator must decide whether repeated corrections represent a stable preference, a dramatic-context rule, a project-specific exception, or an analyzer/compiler failure. No correction becomes a global rule merely because it was recorded.

## Video Microscope research track

The Video Microscope analyzes **finished human edits** rather than source footage. It reuses the same shot detection, motion analysis and `CutSignature` logic so MONTER can measure editorial patterns from real work.

Microscope v0.1 outputs:

- shot-duration distribution and cutting rhythm
- normalized motion-energy arc
- screen-direction distribution
- per-cut physical `CutSignature`
- direction-continuity rate
- action-phase cut rate
- deliberate-discontinuity rate
- motion-match opportunity rate

Multiple reports can be aggregated into a `StyleProfile`. The profile is a conditional research prior and regression target, not a preset. The rough-cut planner can use it as a confidence-weighted cadence prior while keeping the Director's dramatic energy arc authoritative. v0.1 explicitly does not claim semantic, gaze, composition, color, narrative or sound-design understanding.

## Progressive analysis

1. Cheap pass over all media: ffprobe, scene boundaries, low-resolution motion and waveform/audio features.
2. Better analysis only for candidate shots and edit windows.
3. Dense flow/masks/depth only near selected boundaries.
4. Expensive interpolation/generative processing only for final selected operations.

## Pull request policy

Every PR must run the same core checks locally and in GitHub Actions:

- Studio unit tests
- Studio production build
- Bridge pytest suite
- real encoded-media smoke coverage for media paths that must work outside mocks
