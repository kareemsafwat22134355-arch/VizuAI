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
  transition-opportunities.json
  human-corrections.json    # after human feedback is recorded
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

The share bundle can contain the manifest, VIR, director/edit/CTL/critic artifacts, transition-opportunity reasoning, human correction history, OTIO timeline, and optional rough-cut preview. It **never includes RAW media, analysis proxies, or the analysis cache**. Source references in the project manifest are relative paths, so another MONTER instance can reason about the project without learning the absolute path on your computer.

Use `--no-preview` when you want the smallest possible bundle:

```bash
monter-bundle .monter --out trailer-analysis-only.monter.zip --no-preview
```

## Video Microscope: learn from finished edits

The production pipeline answers “what should MONTER cut?” The Video Microscope answers a different question: “what editorial patterns are visible in a finished human edit?”

```bash
monter-microscope "D:/Finished/edit-01.mp4" \
  --label "KAREEM-01" \
  --out "microscope-01.json"
```

Microscope v0.1 measures shot-duration rhythm, normalized motion-energy arcs, screen-direction continuity, action-phase cuts, deliberate physical discontinuity, and per-boundary `CutSignature` evidence. It deliberately does **not** claim semantic, gaze, composition, color, narrative, or sound-design understanding yet.

Several finished edits can be aggregated into a conditional motion/rhythm style prior:

```bash
monter-style-profile microscope-01.json microscope-02.json microscope-03.json \
  --name "KAREEM-SET-001" \
  --out "kareem-style-profile.json"
```

The style profile is a research prior, not a preset. It should influence decisions proportionally to its confidence rather than forcing every future edit to imitate one fixed rhythm.

## Feed the style prior back into planning

`plan`, `prepare`, and `produce` can accept a StyleProfile as a **soft cadence prior**:

```bash
monter produce "D:/Project/RAW" \
  --name "Trailer" \
  --music "D:/Project/music.wav" \
  --duration 15 \
  --style-profile "kareem-style-profile.json" \
  --work-dir ".monter"
```

In v0.11 the style prior changes cutting density only. MONTER blends the default segment count toward the profile's observed median shot duration according to profile confidence, with a bounded 4–12 segment safety range. The Director's dramatic energy curve is left untouched. This is intentional: taste data can influence cadence without overriding the video's narrative arc.

The resulting `edit-plan.json` records the baseline segment count, style-adjusted count, profile confidence, and observed median shot duration in `strategyNotes`, so the influence is inspectable rather than hidden.

## Transition opportunities before effects

MONTER does not turn every cut into an effect. Before a non-zero transition can exist, the system creates a separate feasibility report for every edit boundary:

```bash
monter-transition-opportunities \
  --edit-plan ".monter/edit-plan.json" \
  --vir ".monter/vir.monter.json" \
  --out ".monter/transition-opportunities.json"
```

The report always keeps `hard_cut` as a valid first-class candidate. It can also identify `action_cut`, `directional_bridge`, and `zoom_bridge` opportunities. Non-zero bridge candidates must satisfy **both** physical motivation and actual source-handle availability on the outgoing and incoming shots. A visually attractive idea is rejected when the edit has no safe source media to build it from.

For every boundary the report stores the `CutSignature`, available handles, candidate duration/handle requirements, motivation score, feasibility score, parameters, and the reason each candidate is accepted or blocked. `monter produce` emits this report automatically, and `monter-bundle` includes it in the portable project package.

The Studio reads the same artifact from `.monter.zip` and exposes the recommendation plus all feasible/blocked candidates boundary-by-boundary. This makes transition reasoning inspectable before expensive effects are compiled.

## Deterministic directional bridge compiler

v0.13 promotes one non-zero opportunity into a reproducible render primitive: `directional_bridge`.

When two adjacent shots share a confident cardinal screen-motion direction and the opportunity report verifies enough source handles, CTL v0.2 compiles a short directional bridge. The renderer borrows half of the bridge duration from the outgoing source handle and half from the incoming source handle, then overlaps those expanded clips for exactly the bridge duration. The added source time and the overlap cancel each other, so the final movie keeps the exact EditPlan duration instead of shrinking the timeline.

The renderer maps the measured screen direction to a deterministic FFmpeg slide transition (`slideleft`, `slideright`, `slideup`, or `slidedown`). It normalizes frame size, fps, pixel format, and timebase before composition and checks for duration drift before launching the final encode.

A non-zero bridge is **not** compiled when either adjacent segment has an event-driven timewarp. In that case CTL records the deferral reason and falls back to the existing zero-duration `motion_match_cut`, `motion_peak_cut`, or `hard_cut`. This avoids combining two temporal transformations until their joint timing semantics are explicitly supported.

`zoom_bridge` remains a scored opportunity only in v0.13; it is not yet a renderer primitive. Older `ctl-0.1` bundles remain readable in Studio while new renders emit `ctl-0.2`.

## Human correction ledger

v0.14 starts preserving the most valuable supervision MONTER can receive: a human editor changing a concrete AI decision in context.

Record a correction against the current project manifest:

```bash
monter-correction \
  --project-manifest ".monter/project.monter.json" \
  --ledger ".monter/human-corrections.json" \
  --kind transition \
  --target-type boundary \
  --target-ref 3 \
  --ai-json '{"mechanism":"directional_bridge","durationSeconds":0.12}' \
  --human-json '{"mechanism":"hard_cut","durationSeconds":0}' \
  --context-json '{"directorRole":"rupture","relationScore":0.74}' \
  --reason "The rupture reads stronger without a smoothing bridge."
```

Each correction stores the AI decision, human replacement, explicit target, flat evidence/context snapshot, reason, source, and timestamp. Supported correction categories are `shot_selection`, `trim`, `transition`, `timewarp`, `role`, and `other`. Segment/boundary corrections require a target reference; project-level corrections do not.

Writes are atomic and a ledger cannot be reused across different `projectId` values. MONTER also rejects a “correction” whose human decision is identical to the AI decision.

`human-corrections.json` is included in portable `.monter.zip` bundles when present, and Studio displays the correction history as AI → HUMAN decisions with context and reasons.

**Important:** v0.14 captures supervised evidence only. Corrections are not silently applied to future projects and are not converted into global style rules automatically. A later learning/evaluation layer must decide when a repeated correction is a general preference, a project-specific exception, or a dramatic-context rule.

The current baseline uses PySceneDetect, low-resolution streaming OpenCV optical flow, librosa audio analysis, typed CTL, FFmpeg draft rendering and OpenTimelineIO export. The critic keeps quality dimensions separate and can run a bounded targeted revision loop instead of endlessly regenerating the edit.

## Testing rule

Every pull request must pass Studio tests/build plus Bridge unit tests and real-media smoke coverage before it is considered merge-ready. The Bridge smoke test generates actual video clips with FFmpeg and runs the CINEMA-0 pipeline through proxying, analysis, planning, CTL, critique, transition-opportunity synthesis, OTIO export, rendering, and portable bundle creation. The directional bridge has its own encoded-media test that renders a real FFmpeg transition and verifies with `ffprobe` that the final duration does not shrink. Correction-ledger tests verify project isolation, atomic persistence, target validation, and AI-vs-human decision preservation. The Video Microscope also has a real-media smoke test that generates a finished edit with hard cuts and verifies that its shot/cut analysis runs on actual encoded video.

See `docs/ARCHITECTURE.md` and `docs/OPEN_SOURCE.md`.
