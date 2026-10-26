# VizuAI / MONTER

VizuAI is the repository for **MONTER**, a cinematic editorial intelligence system.

MONTER does not upload giant RAW folders to the web. It separates media processing from editorial reasoning:

- `packages/bridge` — local, 8GB-RAM-first ingest/proxy/analysis/planning/render engine.
- `apps/studio` — Vercel-hosted workspace for inspecting VIR, director intent, edit plans, CTL and critic decisions.
- `contracts` — portable data contracts shared between the two sides.

## One-command CINEMA-0 production

```bash
cd packages/bridge
python -m pip install -e .
monter produce "D:/Project/RAW" \
  --name "Trailer" \
  --music "D:/Project/music.wav" \
  --duration 15 \
  --work-dir ".monter"
```

The RAW footage stays local. The run produces a transparent working bundle:

```text
.monter/
  project.monter.json
  vir.monter.json
  director-plan.json
  audio-analysis.json       # when music is supplied
  edit-plan.json
  ctl.json
  critic-report.json
  production-report.json
  edit.otio
  rough-cut.mp4
  proxies/
```

The current baseline uses PySceneDetect, low-resolution streaming OpenCV optical flow, librosa audio analysis, typed CTL, FFmpeg draft rendering and OpenTimelineIO export. The critic keeps quality dimensions separate and can run a bounded targeted revision loop instead of endlessly regenerating the edit.

## Development rule

Every pull request must pass Studio and Bridge tests before it is considered merge-ready.

See `docs/ARCHITECTURE.md` and `docs/OPEN_SOURCE.md`.
