# MONTER v0.33 — Segmentation Backend Discovery + Explicit Opt-In Configuration

v0.32 defined how a segmentation backend may execute inside scheduler-selected windows. v0.33 adds a safe way to discover optional runtimes and validate local backend configuration before any inference is attempted.

## Design rule

Optional ML capability must never become a hidden prerequisite for the deterministic MONTER core.

MONTER therefore treats segmentation backends as **optional capabilities**:

- core doctor health does not fail because SAM 2 is absent;
- discovery does not import or initialize the model;
- discovery does not install packages;
- validation does not download weights;
- arbitrary Python module paths are not accepted;
- network-backed model loading is rejected by schema validation.

## Allowlisted backends

v0.33 recognizes exactly:

- `none` — segmentation intentionally disabled;
- `sam2` — Meta SAM 2 runtime, if explicitly installed and configured locally.

This is an allowlist, not a plugin string that can import arbitrary code.

## Configuration schema

`SegmentationBackendConfig` stores:

- `backendId`
- `device`: `auto | cpu | cuda`
- optional `modelId`
- `checkpointPath`
- `modelConfigPath`
- `allowNetwork` (must remain `false`)
- behavior-changing `parameters`

For `sam2`, both local checkpoint and local model-config paths are required.

Example:

```json
{
  "backendId": "sam2",
  "device": "cpu",
  "checkpointPath": "D:/models/sam2/model.pt",
  "modelConfigPath": "D:/models/sam2/model.yaml",
  "allowNetwork": false,
  "parameters": {
    "offloadVideoToCpu": true,
    "offloadStateToCpu": true
  }
}
```

The paths are local execution configuration. They are not written into portable VIR/edit artifacts by this milestone.

## Discovery

`discover_segmentation_backends()` checks package/module presence without importing the heavyweight runtime.

For SAM 2 it reports:

- whether `torch` and `sam2` modules are discoverable;
- package versions when distribution metadata is available;
- `installed`, `configured`, `ready`, and `optional` states;
- a human-readable reason.

## Readiness

A SAM 2 config is `ready=true` only when:

1. the optional Python runtime is discoverable;
2. the explicit checkpoint exists;
3. the explicit model config exists;
4. network loading remains disabled.

`ready=true` in v0.33 means the machine/config contract is satisfied. It does **not** yet mean the concrete SAM 2 adapter has been bound into advanced execution.

## Doctor integration

`monter-doctor` now includes:

```json
{
  "optionalCapabilities": {
    "segmentationBackends": []
  }
}
```

Missing SAM 2 remains informational. The doctor's top-level `ok` still reflects required local bridge capabilities such as Python, FFmpeg/ffprobe, and work-directory writability.

## CLI

List allowlisted backends:

```bash
monter-segmentation-backends list
```

Validate explicit config:

```bash
monter-segmentation-backends validate --config sam2.local.json
```

Exit behavior:

- `0` when the selected backend is ready;
- `2` when config is valid but the optional backend is not ready;
- schema/IO errors fail explicitly rather than silently falling back.

## Why there is still no automatic SAM 2 execution

The v0.32 backend protocol is frame-local, while a production SAM 2 video adapter needs an explicit prompting/tracking policy and lifecycle management. Guessing a center point or inventing a foreground prompt would create fake intelligence.

The next adapter milestone should therefore add **prompt context and video-state ownership** deliberately, then bind SAM 2 behind the existing scheduler/cache contracts.

## Acceptance gates

v0.33 is accepted only if:

- `backendId=none` works without any ML runtime;
- unknown backend IDs are rejected by the typed schema;
- `allowNetwork=true` is rejected;
- SAM 2 config requires explicit local checkpoint/config files;
- missing optional SAM 2 runtime does not fail `monter-doctor`;
- installed runtime plus existing local files produces `ready=true`;
- CLI output is machine-readable;
- no model import, package install, or model download occurs during discovery/validation;
- all existing Studio and Bridge/real-media gates remain green.
