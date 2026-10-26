# Open-source adoption log

MONTER should reuse mature open-source infrastructure when it accelerates development without surrendering the cinematic intelligence layer.

## Adopt now

### PySceneDetect
- Role: first-pass shot/scene boundary detection in the Local Bridge.
- License: BSD-3-Clause.
- Why: mature OpenCV-based cut/fade detection; avoids rebuilding commodity boundary detection.
- MONTER ownership: shot semantics, motion phases, edit anchors and editorial interpretation remain ours.

## Planned

### OpenTimelineIO
- Role: interchange/export layer for editorial timelines and external NLE workflows.
- License: Apache-2.0.
- Why: mature industry timeline model with external-media references and adapters.
- Status: adopt when the first real edit plan export lands; do not force VIR/CTL to become OTIO.

### wavesurfer.js
- Role: waveform, timeline marks and editorial audio regions inside Studio.
- License: BSD-3-Clause.
- Status: use when the audio inspection view is introduced.

### Media Chrome
- Role: accessible, framework-compatible preview-player controls.
- License: MIT.
- Status: use when Studio gains synchronized media preview.

## Reference only

### react-video-timeline-editor
- Useful reference for NLE interaction patterns and timeline architecture.
- AGPL-3.0 licensing makes it inappropriate as a foundational dependency for MONTER's product direction.

## Principle

Open-source packages can provide commodity infrastructure. They must not become the source of MONTER's taste, transition invention, viewer-state model, VIR, CTL, critic logic or director policy.
