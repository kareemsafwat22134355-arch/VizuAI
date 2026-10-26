from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from .planning_models import AudioAnalysis


def summarize_audio(y: np.ndarray, sr: int) -> AudioAnalysis:
    if sr <= 0:
        raise ValueError("sample rate must be > 0")
    if y.size == 0:
        return AudioAnalysis(
            duration_seconds=0.0,
            tempo_bpm=0.0,
            beats_seconds=[],
            onsets_seconds=[],
            rms_mean=0.0,
            rms_peak=0.0,
        )

    onset_envelope = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_envelope)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    onset_times = librosa.onset.onset_detect(
        y=y,
        sr=sr,
        onset_envelope=onset_envelope,
        units="time",
        backtrack=False,
    )
    rms = librosa.feature.rms(y=y)[0]
    tempo_value = float(np.ravel(np.asarray(tempo))[0]) if np.size(tempo) else 0.0

    return AudioAnalysis(
        duration_seconds=float(len(y) / sr),
        tempo_bpm=max(0.0, tempo_value),
        beats_seconds=[float(value) for value in beat_times],
        onsets_seconds=[float(value) for value in onset_times],
        rms_mean=float(np.mean(rms)) if rms.size else 0.0,
        rms_peak=float(np.max(rms)) if rms.size else 0.0,
    )


def analyze_audio(path: Path, sample_rate: int = 22_050) -> AudioAnalysis:
    y, sr = librosa.load(str(path), sr=sample_rate, mono=True, dtype=np.float32)
    return summarize_audio(y, sr)
