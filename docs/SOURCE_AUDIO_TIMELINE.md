# Source-audio timeline and J/L cuts — v0.19

MONTER previously rendered picture plus an optional music bed and discarded source audio. v0.19 introduces an independent source-audio timeline so sound can cross picture edits without moving the visual cut.

## Artifact

`audio-edit-plan.json` uses schema `audio-edit-plan-0.1`.

Each `SourceAudioEvent` contains:

- segment and asset identity
- source-audio in/out time
- audio timeline in/out time
- gain
- short fade-in/fade-out values
- explicit editorial reason

Source and timeline durations must match in v0.19; source audio is 1x playback only.

## J-cut semantics

A J-cut lets incoming audio start before the incoming picture.

For a visual boundary at 2.00s with a 250ms J-cut:

```text
incoming picture: 2.00s
incoming audio:   1.75s
```

The audio event borrows 250ms from the incoming source-audio handle. The video edit remains exactly where CTL placed it.

## L-cut semantics

An L-cut lets outgoing audio continue after the outgoing picture has cut away.

For a visual boundary at 2.00s with a 250ms L-cut:

```text
outgoing picture ends: 2.00s
outgoing audio ends:   2.25s
```

The event borrows 250ms from the outgoing source-audio handle.

## Safety guards

MONTER refuses a J/L intent when:

- the required asset has no audio stream
- the required source-audio handle does not exist
- an L-cut would extend beyond the final timeline duration
- a J-cut would begin before timeline zero
- the target segment is timewarped

Timewarped picture clips intentionally omit source audio in v0.19. Audio retiming is a separate temporal problem and must not be solved with silent drift.

## Rendering

The audio-aware renderer:

- trims each source-audio event independently from picture
- delays it to the requested timeline position
- normalizes the working audio format to 48kHz stereo
- applies explicit gain and short event fades
- mixes overlapping source events with FFmpeg `amix`
- can mix the result with a music bed as another layer
- trims the final audio mix to CTL duration

The final picture duration therefore remains authoritative even when audio crosses the visual boundary.

## Commands

Create an explicit J/L plan:

```bash
monter-audio-plan \
  --manifest .monter/project.monter.json \
  --ctl .monter/ctl.json \
  --j-cut 2:0.25 \
  --l-cut 5:0.30 \
  --out .monter/audio-edit-plan.json
```

Only one audio intent may target a visual boundary in v0.19.

Render it:

```bash
monter-audio-render \
  --manifest .monter/project.monter.json \
  --ctl .monter/ctl.json \
  --audio-plan .monter/audio-edit-plan.json \
  --proxy-dir .monter/proxies \
  --music music.wav \
  --out .monter/rough-cut.audio.mp4
```

When a portable `.monter.zip` contains both `rough-cut.audio.mp4` and the earlier `rough-cut.mp4`, Studio prefers the audio-aware preview.

## What v0.19 does not claim

v0.19 is the **temporal/rendering foundation**, not the autonomous Sound Director.

It does not yet decide where a J-cut or L-cut is motivated. The editor supplies explicit boundary intents.

The next Sound Director milestone should inspect source-audio evidence near selected boundaries—activity, silence, transients, speech/voice confidence, and continuity—and then propose a small number of motivated J/L cuts. It should still preserve deliberate silence and allow no source audio at all when that is the stronger editorial choice.
