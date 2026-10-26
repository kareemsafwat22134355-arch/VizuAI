from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np

from .analysis_models import VirProject
from .ctl_models import CtlProgram
from .models import MonterProject
from .proxy import proxy_path_for
from .sound_director_models import AudioWindowMetrics, BoundaryAudioEvidence

PCM_RATE = 16000
FRAME_SECONDS = 0.020
ACTIVE_FRAME_DBFS = -38.0


def _dbfs(amplitude: float) -> float:
    return 20.0 * math.log10(max(amplitude, 1e-9))


def analyze_audio_window(
    path: Path,
    asset_id: str,
    start_seconds: float,
    end_seconds: float,
    sample_rate: int = PCM_RATE,
) -> AudioWindowMetrics | None:
    duration = end_seconds - start_seconds
    if duration < 0.025:
        return None

    completed = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start_seconds:.6f}",
            "-t", f"{duration:.6f}",
            "-i", str(path),
            "-vn", "-ac", "1", "-ar", str(sample_rate),
            "-f", "f32le", "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    samples = np.frombuffer(completed.stdout, dtype=np.float32)
    if samples.size == 0:
        return AudioWindowMetrics(
            asset_id=asset_id,
            source_start_seconds=start_seconds,
            source_end_seconds=end_seconds,
            duration_seconds=duration,
            rms_dbfs=-120.0,
            peak_dbfs=-120.0,
            active_frame_fraction=0.0,
            activity_score=0.0,
        )

    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    peak = float(np.max(np.abs(samples)))
    rms_dbfs = _dbfs(rms)
    peak_dbfs = _dbfs(peak)

    frame_size = max(1, round(sample_rate * FRAME_SECONDS))
    frame_rms: list[float] = []
    for start in range(0, samples.size, frame_size):
        frame = samples[start:start + frame_size]
        if frame.size == 0:
            continue
        frame_rms.append(float(np.sqrt(np.mean(np.square(frame, dtype=np.float64)))))
    active_fraction = (
        sum(_dbfs(value) >= ACTIVE_FRAME_DBFS for value in frame_rms) / len(frame_rms)
        if frame_rms else 0.0
    )
    level_score = max(0.0, min(1.0, (rms_dbfs + 52.0) / 30.0))
    activity_score = max(0.0, min(1.0, 0.65 * level_score + 0.35 * active_fraction))

    return AudioWindowMetrics(
        asset_id=asset_id,
        source_start_seconds=start_seconds,
        source_end_seconds=end_seconds,
        duration_seconds=duration,
        rms_dbfs=rms_dbfs,
        peak_dbfs=peak_dbfs,
        active_frame_fraction=active_fraction,
        activity_score=activity_score,
    )


def analyze_boundary_audio(
    project: MonterProject,
    ctl: CtlProgram,
    vir: VirProject,
    proxy_dir: Path,
    context_seconds: float = 0.30,
    max_handle_seconds: float = 0.35,
) -> list[BoundaryAudioEvidence]:
    if project.project_id != ctl.project_id or project.project_id != vir.project_id:
        raise ValueError("Project, CTL, and VIR projectId values must match for source-audio analysis")
    if context_seconds <= 0 or max_handle_seconds <= 0:
        raise ValueError("audio analysis windows must be positive")

    assets = {asset.id: asset for asset in project.assets}
    shots = {shot.id: shot for shot in vir.shots}
    warped_segments = {intent.segment_id for intent in ctl.time_warps}
    results: list[BoundaryAudioEvidence] = []

    for boundary_index, (left, right) in enumerate(zip(ctl.clips, ctl.clips[1:]), start=1):
        left_asset = assets.get(left.asset_id)
        right_asset = assets.get(right.asset_id)
        left_shot = shots.get(left.shot_id)
        right_shot = shots.get(right.shot_id)
        if left_asset is None or right_asset is None or left_shot is None or right_shot is None:
            results.append(BoundaryAudioEvidence(
                boundary_index=boundary_index,
                visual_cut_seconds=left.timeline_out_seconds,
                outgoing_handle_seconds=0,
                incoming_handle_seconds=0,
                blocked_reason="Missing asset or shot analysis for this boundary.",
            ))
            continue

        outgoing_handle = max(
            0.0,
            min(max_handle_seconds, left_asset.duration_seconds - left.source_out_seconds, left_shot.range.end_seconds - left.source_out_seconds),
        )
        incoming_handle = max(
            0.0,
            min(max_handle_seconds, right.source_in_seconds, right.source_in_seconds - right_shot.range.start_seconds),
        )

        left_path = proxy_path_for(left_asset, proxy_dir)
        right_path = proxy_path_for(right_asset, proxy_dir)
        outgoing_pre = outgoing_post = incoming_pre = incoming_post = None
        blocked: list[str] = []

        if left.id in warped_segments:
            blocked.append("outgoing segment is timewarped")
        elif left_asset.has_audio and left_path.is_file():
            outgoing_pre = analyze_audio_window(
                left_path,
                left.asset_id,
                max(left.source_in_seconds, left.source_out_seconds - context_seconds),
                left.source_out_seconds,
            )
            if outgoing_handle >= 0.025:
                outgoing_post = analyze_audio_window(
                    left_path,
                    left.asset_id,
                    left.source_out_seconds,
                    left.source_out_seconds + outgoing_handle,
                )
        else:
            blocked.append("outgoing asset has no usable source audio")

        if right.id in warped_segments:
            blocked.append("incoming segment is timewarped")
        elif right_asset.has_audio and right_path.is_file():
            if incoming_handle >= 0.025:
                incoming_pre = analyze_audio_window(
                    right_path,
                    right.asset_id,
                    right.source_in_seconds - incoming_handle,
                    right.source_in_seconds,
                )
            incoming_post = analyze_audio_window(
                right_path,
                right.asset_id,
                right.source_in_seconds,
                min(right.source_out_seconds, right.source_in_seconds + context_seconds),
            )
        else:
            blocked.append("incoming asset has no usable source audio")

        results.append(BoundaryAudioEvidence(
            boundary_index=boundary_index,
            visual_cut_seconds=left.timeline_out_seconds,
            outgoing_pre=outgoing_pre,
            outgoing_post=outgoing_post,
            incoming_pre=incoming_pre,
            incoming_post=incoming_post,
            outgoing_handle_seconds=outgoing_handle,
            incoming_handle_seconds=incoming_handle,
            blocked_reason="; ".join(blocked) if len(blocked) == 2 else None,
        ))

    return results
