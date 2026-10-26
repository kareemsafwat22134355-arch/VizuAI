# MONTER architecture v0.1

## Local Bridge

The Local Bridge owns large media. RAW footage never needs to be uploaded to the Studio.

Responsibilities:

- enumerate source media recursively
- inspect media with `ffprobe`
- preserve source identity, timebase and technical metadata
- generate low-resolution analysis proxies with FFmpeg
- emit a portable `project.monter.json` manifest
- later: shot detection, motion/audio passes, thumbnails, embeddings and selective expensive analysis

The Bridge is designed for 8 GB RAM machines. Work is streamed through FFmpeg and sampled analysis rather than loading whole video files into Python memory.

## MONTER Studio

The Studio is a Next.js application designed for Vercel. It displays lightweight editorial intelligence rather than RAW media.

Responsibilities:

- project overview and pipeline state
- source/shot intelligence
- director energy curve
- edit-plan reasoning
- later: critic reports, transition rationale, waveform regions and human corrections

## Boundary

```text
RAW media (local)
    -> Local Bridge
    -> proxies + project.monter.json
    -> MONTER Studio / cinematic brain
    -> edit plan / CTL
    -> local RAW relink
    -> final render
```

## Progressive analysis

1. Cheap pass over all media: ffprobe, scene boundaries, thumbnails, waveform, simple motion.
2. Better analysis only for candidate shots.
3. Dense flow/masks/depth only near selected edit boundaries.
4. Expensive interpolation/generative processing only for final selected operations.

## Pull request policy

Every PR must run the same core checks locally and in GitHub Actions:

- Studio unit tests
- Studio production build
- Bridge pytest suite
