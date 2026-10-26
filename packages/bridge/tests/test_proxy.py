from pathlib import Path

from monter_bridge.proxy import proxy_command


def test_proxy_command_is_analysis_friendly():
    command = proxy_command(Path("raw.mov"), Path("proxy.mp4"), width=960, fps=24)
    joined = " ".join(command)
    assert "ffmpeg" in command[0]
    assert "min(960,iw)" in joined
    assert "fps=24" in joined
    assert "-crf 28" in joined
    assert "-preset veryfast" in joined
