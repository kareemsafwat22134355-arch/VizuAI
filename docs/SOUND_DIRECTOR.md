# Evidence-based Sound Director — v0.20

v0.19 established a real source-audio timeline and deterministic J/L rendering. v0.20 makes the first J/L decisions automatically from local source-audio evidence.

The director is deliberately conservative: it prefers `sync` when evidence is weak, ambiguous, too short, unavailable, or intentionally quiet.

## Inputs

The Sound Director reads:

- project manifest
- CTL picture timeline
- VIR shot ranges
- local analysis proxies

It does not upload audio and does not load whole source files into memory.

## Boundary windows

For each visual cut MONTER can inspect up to four short audio windows:

```text
outgoing-pre  | CUT | outgoing-post
incoming-pre  | CUT | incoming-post
```

The post/pre handle windows are capped at 350ms and also clamped to:

- the actual asset duration
- the selected CTL source range
- the detected VIR shot range

This prevents a J/L decision from borrowing audio from another detected scene merely because the underlying media file continues.

## Cheap audio evidence

Each window is decoded through FFmpeg to mono 16kHz float PCM and summarized as:

- RMS dBFS
- peak dBFS
- fraction of active 20ms frames
- normalized activity score

The current active-frame reference is `-38 dBFS`. Activity score combines absolute RMS level and active-frame density.

These are **physical audio activity features only**. v0.20 does not claim that an active window contains speech, an important sound effect, or semantically relevant dialogue.

## J-cut proposal

A J-cut can be proposed when:

- incoming pre-roll has at least 120ms of verified shot/audio handle
- incoming pre-roll is clearly active
- that activity continues into the incoming selected range
- incoming continuity is more compelling than the outgoing tail

The next scene's sound therefore leads its picture.

## L-cut proposal

An L-cut can be proposed when:

- outgoing post-roll has at least 120ms of verified shot/audio handle
- outgoing post-roll remains clearly active
- activity is continuous with the selected outgoing audio
- the incoming head is comparatively quieter

The previous scene's sound therefore trails over the next image.

## Sync and silence are first-class

MONTER keeps the visual boundary synchronous when:

- neither source handle is active enough
- both J and L motivations are similarly strong
- the required handle is shorter than 120ms
- source audio is missing
- a relevant picture segment is timewarped
- motivation fails the policy threshold

This is intentional. The Sound Director is not rewarded for creating overlaps.

## Ambiguity rule

If both J and L candidates are valid and their motivation scores are within `0.08`, the decision returns to `sync` instead of making an arbitrary choice.

## Density budget

By default no more than two non-sync J/L boundaries are selected per run. Candidates are ranked by confidence, while all per-boundary decisions remain visible in `sound-director.json`.

This protects the edit from turning every cut into an audio overlap.

## Artifacts

`monter-sound-director` writes:

- `sound-director.json` — evidence + all decisions + selected intents
- `audio-edit-plan.json` — the executable source-audio timeline built from selected intents

Example:

```bash
monter-sound-director \
  --manifest .monter/project.monter.json \
  --ctl .monter/ctl.json \
  --vir .monter/vir.monter.json \
  --proxy-dir .monter/proxies \
  --max-jl-cuts 2 \
  --report-out .monter/sound-director.json \
  --audio-plan-out .monter/audio-edit-plan.json
```

Render the result with:

```bash
monter-audio-render \
  --manifest .monter/project.monter.json \
  --ctl .monter/ctl.json \
  --audio-plan .monter/audio-edit-plan.json \
  --proxy-dir .monter/proxies \
  --music music.wav \
  --out .monter/rough-cut.audio.mp4
```

## Real-media acceptance test

The test fixture creates three encoded A/V clips:

1. silent source audio
2. continuous tone
3. silent source audio

Expected decisions:

- boundary 1: J-cut into the active middle clip
- boundary 2: L-cut out of the active middle clip

The resulting automatic audio plan is rendered and checked with `ffprobe` for both video/audio streams and unchanged 6-second picture duration.

## Current limits

v0.20 does not yet model:

- speech or speaker identity
- semantic dialogue continuity
- source/music ducking based on speech
- transient class or sound-effect identity
- room-tone similarity
- music phrase interaction with source sound
- audio retiming for timewarped picture

Those should be added as separate evidence layers rather than inferred from RMS activity alone.
