from pathlib import Path

import monter_bridge.shots as shots


class FakeTimecode:
    def __init__(self, seconds: float):
        self.seconds = seconds

    def get_seconds(self) -> float:
        return self.seconds


class FakeVideo:
    duration = FakeTimecode(5.0)


class FakeSceneManager:
    def __init__(self):
        self.detector = None

    def add_detector(self, detector):
        self.detector = detector

    def detect_scenes(self, video):
        assert isinstance(video, FakeVideo)

    def get_scene_list(self, start_in_scene=True):
        assert start_in_scene is True
        return [
            (FakeTimecode(0.0), FakeTimecode(2.0)),
            (FakeTimecode(2.0), FakeTimecode(5.0)),
        ]


def test_detect_shots_returns_portable_ranges(monkeypatch):
    monkeypatch.setattr(shots, "open_video", lambda _: FakeVideo())
    monkeypatch.setattr(shots, "SceneManager", FakeSceneManager)
    monkeypatch.setattr(shots, "AdaptiveDetector", lambda **_: object())

    result = shots.detect_shots(Path("proxy.mp4"))

    assert [(item.start_seconds, item.end_seconds) for item in result] == [(0.0, 2.0), (2.0, 5.0)]
