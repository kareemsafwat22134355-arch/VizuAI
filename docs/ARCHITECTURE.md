# MONTER architecture v0.2

## Local Bridge

The Local Bridge owns large media. RAW footage never needs to be uploaded to the Studio.

Current responsibilities:

- enumerate source media recursively
- inspect media with `ffprobe`
- preserve source identity, timebase and technical metadata
- generate low-resolution analysis proxies with FFmpeg
- detect shot/scene boundaries with PySceneDetect
- sample local optical flow and global camera motion from one decode pass per shot
- derive motion-phase edit anchors
- cache per-asset analysis using proxy + analyzer fingerprints
- emit portable project, VIR, director, edit, CTL, critic, OTIO and production artifacts
- render deterministic proxy drafts with FFmpeg
- create share bundles that exclude RAW media, proxies and analysis caches

The Bridge is designed for 8 GB RAM machines. Work is streamed through FFmpeg and sampled analysis rather than loading whole video files into Python memory. Expensive analysis is intended to stay progressive and selective.

## MONTER Studio

The Studio is a Next.js application designed for Vercel. It displays lightweight editorial intelligence rather than RAW media.

Current responsibilities:

- project overview and pipeline state
- local `.monter.zip` import in the browser
- rough-cut preview without backend upload
- source/shot intelligence
- director energy curve
- edit-plan reasoning
- CTL transition rationale
- critic dimensions/findings

Later Studio responsibilities include human correction capture, richer waveform regions, transition opportunity inspection and benchmark comparisons.

## Boundary

```text
RAW media (local)
    -> Local Bridge
    -> proxies + cached VIR analysis
    -> Director / Planner / CTL / Critic
    -> portable .monter.zip
    -> MONTER Studio (browser-local inspection)
    -> local RAW relink / final-quality renderer later
```

## Video Microscope research track

The Video Microscope analyzes **finished human edits** rather than source footage. It reuses the same shot detection, motion analysis and `CutSignature` logic so MONTER can measure editorial patterns from real work.

Microscope v0.1 outputs:

- shot-duration distribution and cutting rhythm
- normalized motion-energy arc
- screen-direction distribution
- per-cut physical `CutSignature`
- direction-continuity rate
- action-phase cut rate
- deliberate-discontinuity rate
- motion-match opportunity rate

Multiple reports can be aggregated into a `StyleProfile`. The profile is a conditional research prior and regression target, not a preset. v0.1 explicitly does not claim semantic, gaze, composition, color, narrative or sound-design understanding.

## Progressive analysis

1. Cheap pass over all media: ffprobe, scene boundaries, low-resolution motion and waveform/audio features.
2. Better analysis only for candidate shots and edit windows.
3. Dense flow/masks/depth only near selected boundaries.
4. Expensive interpolation/generative processing only for final selected operations.

## Pull request policy

Every PR must run the same core checks locally and in GitHub Actions:

- Studio unit tests
- Studio production build
- Bridge pytest suite
- real encoded-media smoke coverage for media paths that must work outside mocks
