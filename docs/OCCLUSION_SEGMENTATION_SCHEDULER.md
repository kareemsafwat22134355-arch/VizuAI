# MONTER v0.31 — Occlusion Candidate Detection + Segmentation Scheduler

v0.31 begins the masks/depth phase without turning segmentation into a global preprocessing tax.

The milestone does **not** install SAM2, does not claim to produce masks, and does not add an occlusion transition primitive. It adds cheap physical evidence that answers a narrower question:

> Is there enough foreground/edge-change evidence near this edit boundary to justify paying for segmentation later?

## Cheap VIR evidence

Each analyzed shot now stores `occlusion` evidence alongside motion and global camera motion.

The signal is extracted during the existing low-resolution visual-analysis decode pass. For each sampled frame pair MONTER:

1. reuses the already-computed global affine camera-motion estimate;
2. warps the previous frame into the current frame coordinate system;
3. measures residual change after camera compensation;
4. extracts the largest connected residual region;
5. measures how strongly that region contacts frame edges;
6. records the dominant contacted edge;
7. combines residual area, component size, edge contact, and compensation confidence into an `occlusion likelihood` score.

This is deliberately a **cue**, not a segmentation mask and not semantic object detection.

### Per-pair fields

`OcclusionCueSample` records:

- `timeSeconds`
- `score`
- `residualChangeFraction`
- `largestComponentFraction`
- `edgeContactFraction`
- `dominantEdge`
- `compensationConfidence`

`ShotAnalysis.occlusion` summarizes:

- peak score
- mean score
- peak time
- dominant edge
- confidence
- all sampled cues

## Camera-motion guard

The cue is computed after affine camera-motion compensation. A whole-frame pan/translation that is explained by the global transform should therefore remain low-scoring, while a large foreground object sweeping in from an edge should leave a localized residual.

This distinction is covered by deterministic tests.

## Cache invalidation

The analysis algorithm fingerprint changes from `motion-global-v2` to `motion-global-occlusion-v3`.

Existing cached VIR analyses are intentionally invalidated so old shots cannot silently appear to have valid occlusion evidence.

## Video Microscope compatibility

The finished-video Video Microscope uses the same combined motion sampler as source-footage analysis. It now carries the third occlusion signal into each observed `ShotAnalysis` instead of discarding it or maintaining a separate perception path.

This keeps source analysis and finished-edit research on the same physical-evidence contract: motion, camera motion, and occlusion likelihood are derived consistently from the same sampled frame pairs.

## Boundary evidence

Transition-opportunity synthesis does not invent a new mechanism. It only localizes occlusion cues around the current source cut (within ±0.45s) and records:

- `occlusionCandidateScore`
- `occlusionSide`: `none | outgoing | incoming | both`
- `occlusionEdge`: `none | left | right | top | bottom | mixed`

A strong cue far away from the chosen edit point does not motivate segmentation at that boundary.

The boundary-side meaningful threshold is `0.52` so the report can preserve a plausible candidate before the scheduler applies the stricter compute gate.

## Selective segmentation scheduling

The advanced-analysis scheduler requests segmentation only when:

- `occlusionSide != none`, and
- `occlusionCandidateScore >= 0.58`.

If no other expensive feature is needed, the request contains only:

`[segmentation]`

If the same boundary already needs another advanced pass, segmentation is merged into that one request:

- ambiguous action cut: `[dense_flow, segmentation]`
- zoom candidate: `[dense_flow, depth, segmentation]`
- borderline directional candidate: `[dense_flow, segmentation]`

This avoids duplicate windows and duplicate scheduling.

## Ownership and budget guards

Existing safety rules remain intact:

- a boundary owned by an adjacent event-driven timewarp does not receive extra segmentation analysis;
- normal advanced-analysis compute budgeting still applies;
- mandatory v0.30 action-timing verification retains priority over optional occlusion-driven requests.

## Backend behavior

v0.31 schedules segmentation but does not auto-install a heavyweight segmentation backend.

When a segmentation request reaches the current executor it returns:

- `status = backend_unavailable`
- `backend = unconfigured`

No model is downloaded automatically and no fake mask is produced.

A later milestone can bind this typed request to an optional SAM2-compatible backend while preserving the same scheduler contract.

## Why this order

The Bible calls for progressive passes:

- cheap metadata/motion first;
- expensive masks/depth only at selected boundaries.

v0.31 implements the missing bridge between those layers. MONTER can now decide *where segmentation is worth running* before paying the RAM/latency cost.

## Intentional limits

v0.31 does not:

- identify object identity;
- produce masks;
- infer depth;
- compile an occlusion transition;
- treat residual change as proof of a foreground subject;
- run segmentation on every shot;
- bypass timewarp ownership;
- automatically download SAM2 or any other heavyweight model.

## Acceptance gates

The milestone is accepted only if:

- static frames score near zero;
- globally compensated camera translation scores near zero;
- a large edge-touching foreground sweep crosses the occlusion threshold;
- boundary evidence ignores cues far from the edit;
- strong boundary evidence schedules segmentation;
- sub-threshold evidence stays cheap;
- segmentation merges into existing dense-flow/depth requests instead of duplicating them;
- timewarp ownership still blocks extra analysis;
- missing segmentation backend reports `backend_unavailable` explicitly;
- analysis cache invalidates the pre-occlusion algorithm version;
- Video Microscope real-media analysis consumes the same occlusion-aware sampler contract;
- all existing Studio and Bridge/real-media CI gates remain green.
