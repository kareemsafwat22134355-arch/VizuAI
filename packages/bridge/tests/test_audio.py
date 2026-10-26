import numpy as np

from monter_bridge.audio import summarize_audio


def test_audio_summary_reports_duration_and_energy():
    sr = 8_000
    seconds = 2
    t = np.arange(sr * seconds, dtype=np.float32) / sr
    signal = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    signal[::4000] += 0.8

    analysis = summarize_audio(signal, sr)

    assert abs(analysis.duration_seconds - seconds) < 1e-6
    assert analysis.rms_mean > 0
    assert analysis.rms_peak >= analysis.rms_mean
    assert analysis.tempo_bpm >= 0
