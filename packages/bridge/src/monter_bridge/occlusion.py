from __future__ import annotations

import math

import cv2
import numpy as np

from .analysis_models import OcclusionCueSample, OcclusionCueSummary, OcclusionEdge

GlobalEstimate = tuple[float, float, float, float, float]


def _affine_matrix(tx: float, ty: float, rotation_degrees: float, scale: float) -> np.ndarray:
    theta = math.radians(rotation_degrees)
    cosine = math.cos(theta) * scale
    sine = math.sin(theta) * scale
    return np.array(
        [[cosine, -sine, tx], [sine, cosine, ty]],
        dtype=np.float32,
    )


def _dominant_edge(mask: np.ndarray, band_ratio: float = 0.14) -> tuple[OcclusionEdge, float]:
    height, width = mask.shape
    band_x = max(1, round(width * band_ratio))
    band_y = max(1, round(height * band_ratio))
    changed = int(np.count_nonzero(mask))
    if changed == 0:
        return "none", 0.0

    counts = {
        "left": int(np.count_nonzero(mask[:, :band_x])),
        "right": int(np.count_nonzero(mask[:, width - band_x :])),
        "top": int(np.count_nonzero(mask[:band_y, :])),
        "bottom": int(np.count_nonzero(mask[height - band_y :, :])),
    }
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    best_edge, best_count = ranked[0]
    edge_contact = min(1.0, sum(counts.values()) / max(changed, 1))
    if best_count <= 0:
        return "none", edge_contact
    if len(ranked) > 1 and ranked[1][1] >= best_count * 0.82:
        return "mixed", edge_contact
    return best_edge, edge_contact  # type: ignore[return-value]


def _largest_component_geometry(
    mask: np.ndarray,
) -> tuple[float, list[float] | None, list[float] | None]:
    if not np.count_nonzero(mask):
        return 0.0, None, None

    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return 0.0, None, None

    component_index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    frame_height, frame_width = mask.shape
    frame_area = float(frame_height * frame_width)
    area = float(stats[component_index, cv2.CC_STAT_AREA])
    x = float(stats[component_index, cv2.CC_STAT_LEFT])
    y = float(stats[component_index, cv2.CC_STAT_TOP])
    width = float(stats[component_index, cv2.CC_STAT_WIDTH])
    height = float(stats[component_index, cv2.CC_STAT_HEIGHT])
    centroid_x, centroid_y = centroids[component_index]

    bbox = [
        max(0.0, min(1.0, x / frame_width)),
        max(0.0, min(1.0, y / frame_height)),
        max(0.0, min(1.0, width / frame_width)),
        max(0.0, min(1.0, height / frame_height)),
    ]
    centroid = [
        max(0.0, min(1.0, float(centroid_x) / frame_width)),
        max(0.0, min(1.0, float(centroid_y) / frame_height)),
    ]
    return max(0.0, min(1.0, area / frame_area)), bbox, centroid


def measure_occlusion_cue(
    previous_gray: np.ndarray,
    current_gray: np.ndarray,
    time_seconds: float,
    global_estimate: GlobalEstimate | None,
) -> OcclusionCueSample:
    if previous_gray.shape != current_gray.shape:
        raise ValueError("occlusion cue frames must have matching shapes")

    compensation_confidence = 0.0
    aligned_previous = previous_gray
    if global_estimate is not None:
        tx, ty, rotation, scale, inlier_ratio = global_estimate
        matrix = _affine_matrix(tx, ty, rotation, scale)
        aligned_previous = cv2.warpAffine(
            previous_gray,
            matrix,
            (previous_gray.shape[1], previous_gray.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        compensation_confidence = max(0.0, min(1.0, inlier_ratio))

    residual = cv2.absdiff(aligned_previous, current_gray)
    adaptive = float(np.percentile(residual, 82))
    threshold = max(14.0, adaptive)
    mask = (residual >= threshold).astype(np.uint8) * 255
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    frame_area = float(mask.size)
    changed_pixels = float(np.count_nonzero(mask))
    residual_fraction = max(0.0, min(1.0, changed_pixels / max(frame_area, 1.0)))
    largest_component_fraction, component_bbox, component_centroid = _largest_component_geometry(mask)
    dominant_edge, edge_contact_fraction = _dominant_edge(mask)

    residual_signal = max(0.0, min(1.0, (residual_fraction - 0.025) / 0.30))
    component_signal = max(0.0, min(1.0, largest_component_fraction / 0.18))
    edge_signal = max(0.0, min(1.0, (edge_contact_fraction - 0.12) / 0.58))
    broad_change_penalty = 1.0 - max(0.0, min(0.65, (residual_fraction - 0.62) / 0.38))
    compensation_weight = 0.55 + 0.45 * compensation_confidence
    score = (
        0.30 * residual_signal
        + 0.40 * component_signal
        + 0.30 * edge_signal
    ) * broad_change_penalty * compensation_weight

    if residual_fraction < 0.02 or largest_component_fraction < 0.012:
        score *= 0.25

    return OcclusionCueSample(
        time_seconds=time_seconds,
        score=max(0.0, min(1.0, float(score))),
        residual_change_fraction=residual_fraction,
        largest_component_fraction=largest_component_fraction,
        largest_component_bbox_xywh_norm=component_bbox,
        largest_component_centroid_xy_norm=component_centroid,
        edge_contact_fraction=edge_contact_fraction,
        dominant_edge=dominant_edge,
        compensation_confidence=compensation_confidence,
    )


def summarize_occlusion(samples: list[OcclusionCueSample]) -> OcclusionCueSummary:
    if not samples:
        return OcclusionCueSummary()
    peak = max(samples, key=lambda sample: sample.score)
    mean_score = float(np.mean([sample.score for sample in samples]))
    reliable = [sample for sample in samples if sample.score >= 0.35]
    confidence = float(np.mean([
        0.5 + 0.5 * sample.compensation_confidence
        for sample in reliable
    ])) if reliable else 0.0
    return OcclusionCueSummary(
        peak_score=peak.score,
        mean_score=mean_score,
        peak_time_seconds=peak.time_seconds,
        dominant_edge=peak.dominant_edge,
        confidence=max(0.0, min(1.0, confidence)),
        samples=samples,
    )
