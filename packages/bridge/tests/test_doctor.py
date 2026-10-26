from pathlib import Path

import monter_bridge.doctor as doctor


def test_doctor_reports_missing_binary(monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    report = doctor.doctor_report()
    assert report["ok"] is False
    assert all(item["ok"] is False for item in report["binaries"])
    assert report["profile"]["targetRamGb"] == 8


def test_doctor_checks_work_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: f"/usr/bin/{name}")

    class Completed:
        stdout = "ffmpeg version test\n"
        stderr = ""

    monkeypatch.setattr(doctor.subprocess, "run", lambda *args, **kwargs: Completed())
    report = doctor.doctor_report(tmp_path / "work")

    assert report["ok"] is True
    assert report["workDirWritable"] is True
    assert all(item["ok"] is True for item in report["binaries"])
