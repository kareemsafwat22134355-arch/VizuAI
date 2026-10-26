# Open-source adoption log

MONTER should reuse mature open-source infrastructure when it accelerates development without surrendering the cinematic intelligence layer.

## Adopt now

### PySceneDetect
- Role: first-pass shot/scene boundary detection in the Local Bridge.
- License: BSD-3-Clause.
- Why: mature OpenCV-based cut/fade detection; avoids rebuilding commodity boundary detection.
- MONTER ownership: shot semantics, motion phases, edit anchors and editorial interpretation remain ours.

### librosa
- Role: music tempo, beat, onset and RMS-energy analysis.
- License: ISC.
- Adopted line: 1.x.
- Why: mature music-information-retrieval primitives; MONTER still owns editorial interpretation and does not map beats directly to cuts.

### OpenTimelineIO
- Role: interchange/export layer for editorial timelines and external NLE workflows.
- License: Apache-2.0.
- Adopted line: 0.18.x.
- Why: industry timeline model with external-media references; VIR and CTL remain independent MONTER contracts.

### wavesurfer.js
- Role: local music waveform inspection inside Studio.
- License: BSD-3-Clause.
- Adopted version: 8.0.3.
- Why: waveform rendering is commodity UI infrastructure and can operate against browser-local object URLs without uploading source audio.

### fflate
- Role: browser-local `.monter.zip` inspection and selective decompression.
- License: MIT.
- Adopted version: 0.8.3.
- Why: small pure-JavaScript ZIP implementation with browser support and per-entry filtering. Studio only decompresses MONTER's known artifact names and enforces compressed, per-entry and total expanded-size limits before accepting project data.
- MONTER ownership: bundle schema, artifact validation, privacy rules and project semantics remain ours.

## Re-evaluate later

### Media Chrome
- Role considered: accessible preview-player controls.
- License: MIT.
- Current decision: do not add a dependency yet. Media Chrome currently recommends Video.js for new projects; MONTER uses the native video element behind a small UI boundary until richer player requirements justify a player framework.

## Reference only

### react-video-timeline-editor
- Useful reference for NLE interaction patterns and timeline architecture.
- AGPL-3.0 licensing makes it inappropriate as a foundational dependency for MONTER's product direction.

## Principle

Open-source packages can provide commodity infrastructure. They must not become the source of MONTER's taste, transition invention, viewer-state model, VIR, CTL, critic logic or director policy.
