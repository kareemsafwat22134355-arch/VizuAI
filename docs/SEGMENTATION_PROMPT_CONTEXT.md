# MONTER v0.34 — Occlusion Prompt Geometry + Stateful Segmentation Window Contract

v0.31 learned where foreground/edge behavior may justify masks. v0.32 defined a replaceable mask backend/cache. v0.33 made heavyweight backends explicit and optional.

v0.34 closes the missing bridge between **cheap physical evidence** and a future video segmentation model:

> MONTER must know what measured foreground region motivated the request before it is allowed to prompt a stateful segmentation backend.

It does **not** install or execute SAM 2 yet.

## 1. Preserve residual-component geometry in VIR

The cheap occlusion cue already identifies the largest connected residual component after global camera-motion compensation. v0.34 preserves that exact component geometry instead of discarding it after scoring.

Each `OcclusionCueSample` can now carry:

- `largestComponentBBoxXywhNorm`
- `largestComponentCentroidXyNorm`

Coordinates are normalized to `[0, 1]`, so the evidence remains portable across proxy widths.

Static or globally explained motion keeps these fields `null` when no usable residual component exists.

The analysis cache algorithm fingerprint changes to:

`motion-global-occlusion-geometry-v4`

so pre-geometry cached analyses are not silently reused.

## 2. Preserve the exact near-cut seed

Transition synthesis already localizes occlusion evidence to ±0.45s around the actual source edit point.

v0.34 now stores the exact strongest near-cut cue on each side:

- `outgoingOcclusionSeed`
- `incomingOcclusionSeed`

This prevents the scheduler from later selecting a different frame or geometry than the evidence that motivated the boundary.

A strong occlusion event far from the edit does not leak into these seed fields.

## 3. Typed SegmentationPromptContext

The advanced-analysis plan schema becomes `advanced-analysis-plan-0.2` and can carry per-side prompts.

`SegmentationPromptContext` stores:

- `side`: `left | right`
- `sourceTimeSeconds`
- normalized positive point
- normalized XYXY box
- confidence
- original occlusion score
- dominant edge
- provenance: `camera_compensated_largest_residual_component`

Prompt coordinates are validated to `[0, 1]` and the box must have positive area.

### Fail-closed scheduling

A high scalar occlusion score is no longer enough to schedule segmentation.

The same side must also provide valid residual-component geometry at or above the segmentation compute threshold (`0.58`). If geometry is missing, MONTER stays on the cheap path instead of inventing a center point or semantic object prompt.

## 4. Side-selective execution

If only outgoing evidence has a valid prompt, only the left analysis window runs segmentation.

If only incoming evidence is valid, only the right window runs.

If both sides are valid, both may run.

This removes the previous v0.32 behavior where a segmentation request could pay for both boundary sides even when physical evidence existed on only one side.

Legacy programmatic requests with no prompt fields preserve both-side frame-backend behavior for backward compatibility.

## 5. Stateful window backend protocol

The original frame-local `SegmentationBackend.segment(...)` remains supported.

v0.34 adds `SegmentationWindowBackend.segment_window(...)` for video/stateful models:

- MONTER samples only the scheduler-selected narrow source window;
- the backend receives the bounded frame list and source timestamps;
- the backend receives one typed prompt context;
- the backend returns exactly one mask per sampled frame;
- MONTER validates shapes, writes mask PNGs, and owns the artifact/cache lifecycle.

A window backend without a typed prompt fails before inference.

This makes session-oriented models replaceable backends rather than owners of MONTER orchestration.

## 6. Prompt-aware cache identity

The segmentation artifact schema becomes `segmentation-artifact-0.2`.

Mask cache identity now includes:

- media content digest
- source window
- boundary side
- sample FPS
- analysis width
- backend/model/version/parameters
- execution mode (`frame | window`)
- complete typed prompt context

Different prompt geometry can therefore never reuse masks generated from another prompt.

Artifacts also record `executionMode` and `promptContext` for provenance.

## 7. Why SAM 2 is still deferred

The concrete SAM 2 video predictor is session-oriented: it initializes video state, accepts a point/box prompt on a chosen frame, then propagates masks through the video state.

v0.34 establishes the model-independent contracts required for that lifecycle first. The next milestone can bind a local-only SAM 2 adapter without changing scheduler, VIR, prompt, cache, or artifact semantics.

No checkpoint download, PyTorch dependency, model initialization, or network fallback is added here.

## Intentional limits

v0.34 does not:

- infer semantic object identity;
- claim the residual component is always the desired subject;
- install or execute SAM 2;
- download model weights;
- run segmentation on full proxies;
- add an occlusion transition primitive;
- compile masks into CTL;
- bypass timewarp ownership or advanced-analysis compute budgets.

## Acceptance gates

The milestone is accepted only if:

- static and globally compensated motion do not produce fake prompt geometry;
- an edge-touching foreground sweep produces normalized bbox + centroid geometry;
- transition synthesis preserves the exact near-cut cue used as the prompt seed;
- distant cues do not leak into the boundary prompt seed;
- high score without valid geometry does not schedule segmentation;
- outgoing-only evidence creates only a left prompt;
- incoming-only evidence creates only a right prompt;
- a stateful window backend receives one typed prompt and one bounded window call;
- window backends fail closed without prompts;
- prompt side must match source-window side;
- changing prompt context changes the cache key;
- outgoing-only execution succeeds even if the unmotivated right proxy is absent;
- legacy frame-backend tests remain green;
- all Studio and Bridge/real-media CI gates remain green.
