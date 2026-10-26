from monter_bridge.ffprobe import parse_fraction, parse_probe_payload


def test_parse_fraction():
    assert parse_fraction("30000/1001") == 30000 / 1001
    assert parse_fraction("0/0") is None
    assert parse_fraction(None) is None


def test_parse_probe_payload():
    technical = parse_probe_payload({
        "format": {"duration": "5.25"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "25/1"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    })
    assert technical.duration_seconds == 5.25
    assert technical.width == 1920
    assert technical.height == 1080
    assert technical.fps == 25
    assert technical.codec == "h264"
    assert technical.has_audio is True
