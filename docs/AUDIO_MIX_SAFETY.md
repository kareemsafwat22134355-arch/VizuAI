# Audio mix safety — v0.21

Once MONTER can overlap source audio and music, mix safety becomes a hard requirement rather than a cosmetic finishing step.

v0.21 adds two separate protections:

1. a final lookahead limiter in the render graph
2. a post-encode audit of the decoded AAC result

## Render limiter

Every rendered audio bus now ends with FFmpeg `alimiter` before final trim/encode.

Current settings:

- linear limit: `0.80` (about `-1.94 dBFS` before AAC)
- attack: `5 ms`
- release: `50 ms`
- `level=0` so FFmpeg does not automatically raise the output back toward full scale
- `latency=1` so lookahead delay is compensated

The limiter applies to:

- music-only drafts
- source-audio-only drafts
- source + music mixes
- overlapping J/L source-audio events

It is intentionally a safety ceiling, not a loudness-normalization target.

## Post-encode audit

`monter-audio-render` automatically decodes the rendered file through FFmpeg `volumedetect` and writes:

```text
.monter/audio-mix-audit.json
```

The report contains:

- mean decoded level in dBFS
- max decoded sample level in dBFS
- the configured safety threshold
- pass/fail state

The default acceptance threshold is `-0.5 dBFS`. If the decoded AAC result exceeds it, `monter-audio-render` exits as a failed quality gate instead of silently accepting a hot mix.

A standalone audit is also available:

```bash
monter-mix-audit .monter/rough-cut.audio.mp4 \
  --safe-threshold-dbfs -0.5 \
  --out .monter/audio-mix-audit.json
```

## Important metering limit

FFmpeg `volumedetect` measures decoded sample peak. It is **not** an inter-sample true-peak or broadcast loudness meter.

v0.21 therefore claims only sample-headroom safety after AAC decode. A later mastering/export layer may add true-peak and LUFS measurement without changing editorial mix decisions.

## Real-media acceptance test

The test fixture intentionally creates a dangerously hot mix:

- high-amplitude encoded source audio
- high-amplitude music
- +12 dB source gain
- +12 dB music gain
- `amix normalize=0`

Without a final safety stage this combination can clip. The test renders real AAC, audits the decoded file, and requires the measured peak to remain below the safety threshold.

## Why loudness normalization is not included yet

MONTER edits trailers, social promos, dialogue pieces, events, and other formats with different loudness goals. v0.21 does not force one LUFS target across all of them.

The current contract is simpler:

> Preserve editorial dynamics, but do not allow the rendered mix to clip.
