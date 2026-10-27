from monter_bridge.advanced_analysis_models import (
    AdvancedAnalysisPlan,
    BoundaryAnalysisRequest,
    SourceAnalysisWindow,
)
from monter_bridge.advanced_executor import execute_advanced_analysis
from monter_bridge.models import MonterProject


def test_segmentation_request_reports_backend_unavailable_without_auto_download(tmp_path):
    project = MonterProject(
        project_id="p",
        project_name="Segmentation Scheduler Fixture",
        created_at="2026-10-27T00:00:00Z",
        source_root_label="RAW",
        source_bytes=0,
        proxy_bytes=0,
        assets=[],
    )
    plan = AdvancedAnalysisPlan(
        project_id="p",
        max_boundaries=1,
        requests=[BoundaryAnalysisRequest(
            boundary_index=1,
            priority=.85,
            requested_features=["segmentation"],
            left_window=SourceAnalysisWindow(
                segment_id="left", asset_id="left_asset", shot_id="left_shot",
                source_start_seconds=.5, source_end_seconds=1.0,
            ),
            right_window=SourceAnalysisWindow(
                segment_id="right", asset_id="right_asset", shot_id="right_shot",
                source_start_seconds=.5, source_end_seconds=1.0,
            ),
            reason="cheap occlusion evidence requested segmentation",
            evidence={"occlusionCandidateScore": .8},
        )],
    )

    results = execute_advanced_analysis(project, plan, tmp_path)

    assert len(results.boundaries) == 1
    feature = results.boundaries[0].features[0]
    assert feature.feature == "segmentation"
    assert feature.status == "backend_unavailable"
    assert feature.backend == "unconfigured"
    assert "no heavyweight backend" in feature.reason.lower()
