# Selective advanced execution — v0.17

v0.16 decides **where** expensive analysis is justified. v0.17 adds the first real executor for one of those requests.

The rule stays strict: an analysis request is not evidence that a feature actually ran. Execution produces a separate `advanced-analysis-results.json` artifact.

## Dense flow backend

The first executable backend is a deterministic CPU baseline using OpenCV Farneback optical flow.

It runs only on source windows already selected by `advanced-analysis-plan.json`; it does not scan the project globally.

For each selected outgoing/incoming window, MONTER records:

- sampled frame-pair count
- mean optical-flow magnitude
- p90 flow magnitude
- mean horizontal and vertical motion vector
- directional coherence
- outgoing/incoming flow-direction compatibility

This is a refinement signal for later transition decisions. It is **not** presented as RAFT or as a learned optical-flow model.

## Explicit unsupported backends

If the scheduler requests `depth` or `segmentation`, v0.17 records:

```text
status = backend_unavailable
backend = unconfigured
```

MONTER does not fabricate a result, silently fall back to a different semantic model, or automatically download a heavyweight dependency.

An optional depth/segmentation backend can be added later behind an explicit interface and cache contract.

## Run it

After a normal production/planning pass:

```bash
monter-analysis-execute \
  --manifest .monter/project.monter.json \
  --plan .monter/advanced-analysis-plan.json \
  --proxy-dir .monter/proxies \
  --sample-fps 12 \
  --analysis-width 320 \
  --out .monter/advanced-analysis-results.json
```

The executor is intentionally separate from `monter produce`. On an 8 GB machine, generating the cheap scheduling plan should not force extra compute automatically.

## Artifact truthfulness

The Studio shows PLAN and EXECUTION separately:

- requested feature = scheduler intent
- `completed` = backend actually produced evidence
- `backend_unavailable` = requested but no configured backend exists
- `failed` = execution was attempted but could not produce valid evidence

A plan alone must never be rendered in the UI as completed analysis.

## Portability

`advanced-analysis-results.json` contains compact metrics only, so it may be included in `.monter.zip`. RAW media and analysis proxies remain excluded.

## Current limit

v0.17 produces refined physical evidence but does not yet feed that evidence back into transition recommendation or CTL compilation. The next milestone should use these results to re-score borderline transition decisions before adding more heavyweight models.
