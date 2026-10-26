from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from monter_bridge.analysis_models import ShotAnalysis, TimeRange, VirProject
from monter_bridge.critic_models import CriticFinding, CriticMetric, CriticReport
from monter_bridge.director import default_director_plan
from monter_bridge.final_critic_models import FinalCriticFinding, FinalCriticReport
from monter_bridge.manifest_io import write_model
from monter_bridge.models import MediaAsset, MonterProject
from monter_bridge.planning_models import EditPlan, EditSegment
from monter_bridge.post_render_revision import attempt_post_render_revision
from monter_bridge.proxy import proxy_path_for


FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _asset(asset_id: str) -> MediaAsset:
    return MediaAsset(
        id=asset_id,
        filename=f"{asset_id}.mp4",
        source_rel_path=f"{asset_id}.mp4",
        source_size_bytes=1,
        duration_seconds=2.0,
        width=320,
        height=180,
        fps=12,
        codec="h264",
        has_audio=False,
    )


def _encode_proxy(path: Path, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:size=320x180:rate=12",
            "-t", "2.0",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(path),
        ],
        check=True,
    )


def _shot(shot_id: str, asset_id: str, energy: float) -> ShotAnalysis:
    return ShotAnalysis(
        id=shot_id,
        asset_id=asset_id,
        range=TimeRange(start_seconds=0, end_seconds=2),
        mean_motion=energy,
        peak_motion=energy,
        motion_samples=[],
        edit_anchors=[],
    )


def _segment(segment_id: str, asset_id: str, shot_id: str, index: int, target: float, actual: float) -> EditSegment:
    return EditSegment(
        id=segment_id,
        asset_id=asset_id,
        shot_id=shot_id,
        source_in_seconds=.25,
        source_out_seconds=1.25,
        timeline_in_seconds=float(index),
        timeline_out_seconds=float(index + 1),
        role="build",
        target_energy=target,
        shot_energy=actual,
        confidence=.9,
        reason="fixture",
    )


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="FFmpeg/ffprobe required for transactional media test")
def test_post_render_candidate_passes_then_snapshots_and_promotes(tmp_path: Path):
    assets = [_asset(name) for name in ["low", "mid1", "mid2", "low2", "high"]]
    project = MonterProject(
        project_id="p",
        project_name="Post Render Transaction",
        created_at="2026-10-26T00:00:00Z",
        source_root_label="RAW",
        source_bytes=5,
        proxy_bytes=0,
        assets=assets,
    )
    vir = VirProject.new("p", [
        _shot("shot_low", "low", 0),
        _shot("shot_mid1", "mid1", 5),
        _shot("shot_mid2", "mid2", 5),
        _shot("shot_low2", "low2", 0),
        _shot("shot_high", "high", 10),
    ])
    edit = EditPlan(
        project_id="p",
        target_duration_seconds=4,
        actual_duration_seconds=4,
        segments=[
            _segment("s1", "low", "shot_low", 0, 1.0, 0.0),
            _segment("s2", "mid1", "shot_mid1", 1, .5, .5),
            _segment("s3", "mid2", "shot_mid2", 2, .5, .5),
            _segment("s4", "low2", "shot_low2", 3, 0.0, 0.0),
        ],
        strategy_notes=[],
    )
    editorial = CriticReport(
        project_id="p",
        status="needs_revision",
        metrics=[CriticMetric(name="mean_energy_error", value=.4, target="<= .3", passed=False)],
        findings=[CriticFinding(
            code="energy_mismatch",
            severity="warning",
            segment_id="s1",
            message="fixture mismatch",
        )],
        notes=[],
    )
    final = FinalCriticReport(
        project_id="p",
        status="needs_revision",
        automatic_revision_candidates=1,
        manual_review_findings=0,
        metrics=[],
        findings=[FinalCriticFinding(
            code="energy_mismatch",
            domain="editorial",
            severity="warning",
            reviseability="automatic_candidate",
            message="fixture mismatch",
            source_artifact="critic-report.json",
            segment_id="s1",
        )],
        notes=[],
    )

    work = tmp_path / ".monter"
    proxies = work / "proxies"
    colors = {"low": "0x304050", "mid1": "0x405030", "mid2": "0x503040", "low2": "0x305050", "high": "0x705020"}
    for asset in assets:
        _encode_proxy(proxy_path_for(asset, proxies), colors[asset.id])

    # Canonical baseline evidence exists before the transaction and must survive in the snapshot.
    write_model(work / "edit-plan.json", edit)
    (work / "rough-cut.mp4").write_bytes(b"baseline-placeholder")

    report, accepted = attempt_post_render_revision(
        project=project,
        vir=vir,
        director=default_director_plan(4),
        baseline_edit=edit,
        baseline_editorial_critic=editorial,
        baseline_final_critic=final,
        work_dir=work,
        proxy_dir=proxies,
        music=None,
        width=320,
        fps=12,
        run_advanced_pass=False,
        max_advanced_boundaries=4,
        advanced_sample_fps=8,
        advanced_analysis_width=160,
        run_sound_pass=False,
        max_jl_cuts=0,
        audio_safety_threshold_dbfs=-.5,
        render_analysis_sample_fps=4,
        render_analysis_width=160,
    )

    assert report.attempted is True
    assert report.changed is True
    assert report.accepted is True
    assert report.candidate_final_status == "pass"
    assert report.changed_segments == ["s1"]
    assert accepted is not None
    assert accepted.edit.segments[0].shot_id == "shot_high"
    assert accepted.final_critic.status == "pass"

    baseline = work / "post-render-baseline"
    candidate = work / "post-render-candidate-01"
    assert baseline.is_dir()
    assert candidate.is_dir()
    assert (baseline / "edit-plan.json").is_file()
    assert (baseline / "rough-cut.mp4").read_bytes() == b"baseline-placeholder"
    assert (candidate / "rough-cut.mp4").stat().st_size > 100
    assert (work / "rough-cut.mp4").stat().st_size == (candidate / "rough-cut.mp4").stat().st_size
    assert (work / "final-critic-report.json").is_file()
    assert "rough-cut.mp4" in report.promoted_artifacts
