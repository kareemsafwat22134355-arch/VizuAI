# VizuAI / MONTER

VizuAI is the repository for **MONTER**, a cinematic editorial intelligence system.

MONTER does not upload giant RAW folders to the web. It separates media processing from editorial reasoning:

- `packages/bridge` — local, 8GB-RAM-first ingest/proxy/analysis engine.
- `apps/studio` — Vercel-hosted workspace for assets, director intent, edit plans and later critic/transition reasoning.
- `contracts` — portable data contracts shared between the two sides.

## Local bridge

The fastest path from a RAW folder to the first VIR is:

```bash
cd packages/bridge
python -m pip install -e .
monter prepare "D:/Project/RAW" --name "Trailer" --work-dir ".monter"
```

This keeps the RAW files local and produces:

```text
.monter/
  project.monter.json
  vir.monter.json
  proxies/
    asset_....mp4
```

The current analysis pass uses PySceneDetect plus low-resolution OpenCV optical flow. Frames are streamed from lightweight proxies instead of loading source footage into RAM.

## Development rule

Every pull request must pass Studio and Bridge tests before it is considered merge-ready.

See `docs/ARCHITECTURE.md` and `docs/OPEN_SOURCE.md`.
