# VizuAI / MONTER

VizuAI is the repository for **MONTER**, a cinematic editorial intelligence system.

MONTER does not upload giant RAW folders to the web. It separates media processing from editorial reasoning:

- `packages/bridge` — local, 8GB-RAM-first ingest/proxy/analysis/planning/render engine.
- `apps/studio` — Vercel-hosted workspace for inspecting VIR, director intent, edit plans, CTL and critic decisions.
- `contracts` — portable data contracts shared between the two sides.

## Local machine preflight

Install the bridge, then verify that the machine has the two native media tools MONTER requires:

```bash
cd packages/bridge
python -m pip install -e .
monter-doctor --work-dir ".monter"
```

The doctor checks Python, `ffmpeg`, `ffprobe`, and write access. The bridge is deliberately proxy-first: RAW files remain untouched and are never loaded wholesale into RAM.

## One-command CINEMA-0 production

```bash
monter produce "D:/Project/RAW" \
  --name "Trailer" \
  --music "D:/Project/music.wav" \
  --duration 15 \
  --work-dir ".monter"
```

The RAW footage stays local. The run produces a transparent working directory:

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
  analysis-cache/
```

Proxy reuse is parameter-aware. MONTER only reuses a proxy when the source file fingerprint and the requested analysis `width`/`fps` still match; changing proxy settings automatically invalidates the cached proxy.

Shot/motion analysis is incremental too. Each asset's analysis cache is keyed by the proxy fingerprint plus MONTER's analysis algorithm version and sampling parameters. Re-running a 10GB project therefore reuses unchanged shot/motion intelligence instead of decoding every proxy again. When a proxy changes or the analyzer version changes, only the affected cache entries are rebuilt. Local optical flow and global camera motion are extracted from the same sampled decode pass for each shot.

## Share a project without sending the RAW footage

After a run, create a portable analysis package:

```bash
monter-bundle .monter --out trailer.monter.zip
```

The share bundle can contain the manifest, VIR, director/edit/CTL/critic artifacts, OTIO timeline, and optional rough-cut preview. It **never includes RAW media, analysis proxies, or the analysis cache**. Source references in the project manifest are relative paths, so another MONTER instance can reason about the project without learning the absolute path on your computer.

Use `--no-preview` when you want the smallest possible bundle:

```bash
monter-bundle .monter --out trailer-analysis-only.monter.zip --no-preview
```

The current baseline uses PySceneDetect, low-resolution streaming OpenCV optical flow, librosa audio analysis, typed CTL, FFmpeg draft rendering and OpenTimelineIO export. The critic keeps quality dimensions separate and can run a bounded targeted revision loop instead of endlessly regenerating the edit.

## Testing rule

Every pull request must pass Studio tests/build plus Bridge unit tests and a real-media smoke test before it is considered merge-ready. The Bridge smoke test generates actual video clips with FFmpeg and runs the CINEMA-0 pipeline through proxying, analysis, planning, CTL, critique, OTIO export, rendering, and portable bundle creation.

See `docs/ARCHITECTURE.md` and `docs/OPEN_SOURCE.md`.
