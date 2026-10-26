from pathlib import Path

from monter_bridge.proxy import (
    proxy_command,
    proxy_fingerprint,
    proxy_is_fresh,
    proxy_metadata_path,
)


def test_proxy_command_is_analysis_friendly():
    command = proxy_command(Path("raw.mov"), Path("proxy.mp4"), width=960, fps=24)
    joined = " ".join(command)
    assert "ffmpeg" in command[0]
    assert "min(960,iw)" in joined
    assert "fps=24" in joined
    assert "-crf 28" in joined
    assert "-preset veryfast" in joined
    assert "-map 0:v:0" in joined
    assert "-map 0:a?" in joined
    assert "-sn -dn" in joined


def test_proxy_fingerprint_tracks_source_and_parameters(tmp_path: Path):
    source = tmp_path / "raw.mov"
    source.write_bytes(b"source")

    first = proxy_fingerprint(source, width=960, fps=24)
    assert first["sourceSizeBytes"] == 6
    assert first["width"] == 960
    assert first["fps"] == 24

    second = proxy_fingerprint(source, width=540, fps=12)
    assert second != first


def test_proxy_cache_requires_matching_sidecar(tmp_path: Path):
    import json

    source = tmp_path / "raw.mov"
    destination = tmp_path / "proxy.mp4"
    source.write_bytes(b"source")
    destination.write_bytes(b"proxy")

    assert proxy_is_fresh(source, destination, width=960, fps=24) is False

    metadata = proxy_fingerprint(source, width=960, fps=24)
    proxy_metadata_path(destination).write_text(json.dumps(metadata), encoding="utf-8")
    assert proxy_is_fresh(source, destination, width=960, fps=24) is True
    assert proxy_is_fresh(source, destination, width=540, fps=24) is False
