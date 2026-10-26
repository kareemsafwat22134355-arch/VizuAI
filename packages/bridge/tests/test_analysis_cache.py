from pathlib import Path

import monter_bridge.analysis as analysis_module
from monter_bridge.analysis import analyze_project
from monter_bridge.analysis_cache import cache_path_for
from monter_bridge.analysis_models import ShotAnalysis, TimeRange
from monter_bridge.models import MediaAsset, MonterProject


def _project() -> MonterProject:
    return MonterProject(
        project_id="project_cache",
        project_name="Cache Test",
        created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW",
        source_bytes=100,
        proxy_bytes=10,
        assets=[
            MediaAsset(
                id="asset_a",
                filename="A.mp4",
                source_rel_path="A.mp4",
                source_size_bytes=100,
                duration_seconds=3.0,
                width=1920,
                height=1080,
                fps=25.0,
                codec="h264",
                has_audio=False,
            )
        ],
    )


def _shot() -> ShotAnalysis:
    return ShotAnalysis(
        id="shot_asset_a_0000",
        asset_id="asset_a",
        range=TimeRange(start_seconds=0.0, end_seconds=3.0),
        mean_motion=1.0,
        peak_motion=2.0,
        motion_samples=[],
        edit_anchors=[],
    )


def test_analysis_cache_reuses_unchanged_proxy_and_invalidates_changed_proxy(tmp_path: Path, monkeypatch):
    project = _project()
    proxy_dir = tmp_path / "proxies"
    cache_dir = tmp_path / "analysis-cache"
    proxy_dir.mkdir()
    proxy = proxy_dir / "asset_a.mp4"
    proxy.write_bytes(b"proxy-v1")

    calls = 0

    def fake_analyze_asset(asset, proxy_path):
        nonlocal calls
        calls += 1
        return [_shot()]

    monkeypatch.setattr(analysis_module, "analyze_asset", fake_analyze_asset)

    first = analyze_project(project, proxy_dir, cache_dir=cache_dir)
    assert calls == 1
    assert len(first.shots) == 1
    assert cache_path_for(project.assets[0], cache_dir).exists()

    def should_not_run(asset, proxy_path):
        raise AssertionError("unchanged proxy should load from analysis cache")

    monkeypatch.setattr(analysis_module, "analyze_asset", should_not_run)
    second = analyze_project(project, proxy_dir, cache_dir=cache_dir)
    assert len(second.shots) == 1
    assert second.shots[0].id == first.shots[0].id

    proxy.write_bytes(b"proxy-v2-with-different-size")
    monkeypatch.setattr(analysis_module, "analyze_asset", fake_analyze_asset)
    third = analyze_project(project, proxy_dir, cache_dir=cache_dir)
    assert calls == 2
    assert len(third.shots) == 1
