# MONTER v0.23 — Final Render Re-analysis

The CINEMA-0 loop requires MONTER to inspect the media it actually rendered, not only the plan that was supposed to produce it.

v0.23 adds the first cheap `DRAFT RENDER -> RE-ANALYZE RENDER` pass.

This milestone is deliberately a **physical/integrity quality gate**, not a semantic or aesthetic critic. It answers questions such as:

- Did the encoded output keep the intended duration?
- Can the final MP4 actually be decoded into frames?
- Did the render accidentally become almost entirely black?
- Does it contain a suspiciously long near-identical-frame span?
- Does cheap motion energy roughly resemble the Director energy curve?

It does **not** automatically revise the edit from these heuristics yet.

## Automatic production order

`monter produce` now ends with:

```text
FINAL CTL
  -> SOUND DIRECTOR
  -> FINAL RENDER
  -> AUDIO MIX AUDIT (when audio exists)
  -> FINAL RENDER RE-ANALYSIS
  -> PRODUCTION REPORT
```

The re-analysis reads the encoded `rough-cut.mp4`, so renderer/codec failures cannot be hidden by a correct pre-render plan.

## Standalone command

```bash
monter-render-analyze \
  --manifest .monter/project.monter.json \
  --director-plan .monter/director-plan.json \
  --render .monter/rough-cut.mp4 \
  --out .monter/render-analysis.json
```

Defaults are intentionally laptop-friendly:

```text
sample rate: 4 fps
analysis width: 320 px
```

## Artifact

The report schema is:

```text
render-analysis-0.1
```

It records:

- encoded duration and expected duration,
- duration drift,
- whether an audio stream is present,
- number of sampled frames,
- normalized mean/peak frame-difference motion,
- near-black frame fraction,
- near-identical frame-pair fraction,
- longest sampled freeze span,
- Director-curve motion alignment,
- time-binned motion/luma/black/freeze evidence,
- findings and notes.

The artifact is included in `.monter.zip` and imported by Studio with a project identity guard.

## Hard quality gates in v0.23

The report becomes `needs_review` only for high-confidence physical failures:

### Duration drift

The encoded duration may not drift beyond:

```text
max(120 ms, 2 output frames)
```

from the expected edit duration.

### Decode failure

A render that produces zero sampled frames is invalid.

### Catastrophic near-black output

If at least 98% of sampled frames are near-black, the report fails.

The current near-black detector requires both very low mean luma and very low luma variance so ordinary dark photography is less likely to be mistaken for a blank render.

## Warning-only evidence

These findings do **not** fail the render in v0.23:

### Long near-identical span

A near-identical-frame run longer than:

```text
max(1.5 s, 50% of the render)
```

is reported for review.

A held product shot, freeze-frame, logo card, or deliberate vacuum can be artistically correct, so the system must not automatically delete or revise it.

### Energy-curve mismatch

Frame-difference motion is normalized within the rendered video and compared with the Director energy curve in several time bins.

Low alignment is only diagnostic evidence because:

```text
motion magnitude != narrative energy
```

A high-energy reveal may be visually static, and a moving camera may occur during a deliberate low-energy beat.

Automatic revision from this signal would be premature.

## Production report

`production-report.json` gains:

- `renderReanalysisExecuted`
- `renderIntegritySafe`
- `renderEnergyAlignment`

A physical render failure marks the overall production `needs_review`.

Warnings remain visible without changing production status.

## Why this is before depth/segmentation

A stronger depth model does not help if the actual encoded output is the wrong duration, blank, frozen, or otherwise broken.

This pass is cheap, deterministic, and validates the output boundary of the system before MONTER spends more compute on richer visual understanding.

## Intentional limits

v0.23 does not yet perform:

- semantic scene understanding on the final render,
- identity/subject continuity checking,
- text/logo readability measurement,
- transition artifact detection,
- optical-flow artifact detection,
- audio-picture semantic synchronization scoring,
- automatic second edit revision from render evidence,
- learned aesthetic quality prediction.

Those should be added as separate evidence layers after the physical re-watch contract is stable.
