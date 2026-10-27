# MONTER v0.32 — Segmentation Backend Contract + Mask Artifact Cache

v0.31 decides **where segmentation is worth paying for**. v0.32 defines how a real segmentation backend may execute inside those scheduler-selected windows without taking control of orchestration, caching, or the filesystem.

This milestone still does **not** install SAM2 automatically and does not compile an occlusion transition. It establishes the deterministic contract that an optional SAM2-compatible adapter can plug into later.

## Design rule

The segmentation model is a backend, not the architecture.

MONTER owns:

- which boundaries are eligible;
- source windows;
- sampling rate;
- analysis resolution;
- cache identity;
- artifact paths;
- validation;
- execution status;
- provenance.

A backend owns only one operation:

```python
segment(frame_bgr, *, time_seconds) -> 2D mask
```

The returned mask must align exactly with the supplied frame.

## Backend descriptor

Every configured backend exposes a typed descriptor:

- `backendId`
- `backendVersion`
- `modelId`
- `parameters`

`parameters` is part of provenance and cache identity. Different prompt strategies, thresholds, checkpoint modes, or other behavior-changing options must therefore produce different cache keys even when the model ID is the same.

## Mask artifacts

The executor stores pixels outside the JSON manifest.

Each sampled frame produces a PNG mask plus compact metadata:

- source time;
- mask path;
- width / height;
- foreground fraction;
- normalized foreground bounding box when non-empty.

A `SegmentationWindowArtifact` records:

- segment / asset / shot identity;
- left/right side of the boundary;
- source window;
- sample FPS;
- analysis width;
- backend descriptor;
- proxy input digest;
- cache key;
- cache-hit state;
- frame artifacts.

`advanced-analysis-results.json` may attach independent left/right segmentation artifacts to a boundary.

## Content-addressed cache

The cache key includes:

- streaming BLAKE2s digest of proxy bytes;
- proxy size;
- asset / shot / segment identity;
- boundary side;
- exact source window;
- segmentation sample FPS;
- analysis width;
- backend ID/version/model ID;
- backend parameters.

The content digest is also persisted explicitly as `inputDigest` so provenance can be audited without reverse-engineering the opaque cache key.

The proxy digest is computed in bounded 1 MiB chunks, so cache identity does not require loading the media file into RAM.

## Atomic writes

A cache entry is written to a temporary directory first.

Only after all sampled masks and `manifest.json` have been written successfully is the temporary directory renamed into the final cache-key directory.

A backend error or invalid mask therefore cannot leave a completed cache entry that appears trustworthy.

## Cache validation

A cache hit is accepted only when:

- the manifest parses against the typed artifact schema;
- the stored cache key matches the requested key;
- backend descriptor matches exactly;
- input digest matches;
- every mask path resolves inside the configured cache root;
- every referenced PNG exists.

Otherwise the entry is treated as a miss.

## Mask validation

Backend output must be:

- a 2D array;
- numeric or boolean;
- exactly the sampled frame height/width.

The executor normalizes any positive value to foreground and writes binary `0/255` PNGs.

A wrong-sized or malformed mask fails the segmentation feature explicitly.

## Advanced executor integration

`execute_advanced_analysis(...)` gains additive optional arguments:

- `segmentation_backend`
- `segmentation_cache_dir`
- `segmentation_sample_fps`
- `segmentation_analysis_width`

If `segmentation_backend` is `None`, behavior remains the v0.31 contract:

- status `backend_unavailable`
- backend `unconfigured`
- no model download
- no fake mask.

If a backend is supplied, MONTER executes it only inside scheduler-selected left/right windows and attaches the typed mask artifacts to that boundary result.

The default mask cache lives beside the proxy workspace as `segmentation-cache`, but callers may provide another explicit path.

## 8GB-RAM policy

v0.32 remains proxy-first and window-local:

- no full-video segmentation pass;
- no full-resolution frame batch kept in memory;
- frames are sampled only inside selected boundary windows;
- frames are downscaled to the configured analysis width before inference;
- mask pixels live in PNG artifacts rather than being embedded in large JSON structures.

## Testing contract

CI uses deterministic lightweight fake backends only. The tests validate the orchestration contract without downloading a neural model.

Encoded H.264 tests prove:

- real sampled frames reach the backend;
- binary PNG mask artifacts are written;
- normalized bounding boxes and foreground fractions are correct;
- the second identical run is a cache hit and does not call the backend again;
- sampling/backend-parameter changes produce a different cache key;
- invalid mask shape fails without leaving a completed cache;
- the advanced executor attaches left/right segmentation artifacts and reports cache hits.

## Intentional limits

v0.32 does not:

- install or download SAM2;
- select a checkpoint automatically;
- expose a production CLI flag for a specific ML backend;
- run segmentation when the scheduler did not request it;
- infer semantic identity from masks;
- infer depth;
- compile an occlusion transition;
- promote segmentation results directly into CTL.

A later adapter milestone can bind a concrete SAM2-compatible implementation to this contract without changing the scheduler, artifact schema, cache semantics, or orchestration ownership.
