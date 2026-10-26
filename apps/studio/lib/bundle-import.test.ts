import { describe, expect, it } from "vitest";
import { strToU8, zipSync } from "fflate";
import { importMonterBundle } from "./bundle-import";

function projectJson(projectId = "project_test") {
  return JSON.stringify({
    schemaVersion: "monter-project-0.1",
    projectId,
    projectName: "Browser Bundle Test",
    createdAt: "2026-10-26T00:00:00Z",
    sourceRootLabel: "RAW",
    sourceBytes: 1000,
    proxyBytes: 100,
    assets: [],
  });
}

function manifest(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    schemaVersion: "monter-bundle-0.1",
    createdAt: "2026-10-26T00:00:00Z",
    includedArtifacts: ["project.monter.json", "rough-cut.mp4"],
    rawMediaIncluded: false,
    proxiesIncluded: false,
    ...overrides,
  });
}

function opportunitiesJson() {
  return JSON.stringify({
    projectId: "project_test",
    boundaries: [
      {
        boundaryIndex: 1,
        leftSegmentId: "left",
        rightSegmentId: "right",
        outgoingHandleSeconds: 0.2,
        incomingHandleSeconds: 0.2,
        cutSignature: {
          directionCompatibility: 1,
          zoomCompatibility: 0.7,
          phaseCompatibility: 0.6,
          globalMotionConfidence: 0.8,
          relationScore: 0.75,
        },
        recommendedMechanism: "directional_bridge",
        candidates: [
          {
            mechanism: "hard_cut",
            durationSeconds: 0,
            requiredHandleSeconds: 0,
            feasible: true,
            feasibilityScore: 1,
            motivationScore: 0.6,
            relationScore: 0.75,
            parameters: {},
            reason: "fallback",
          },
        ],
      },
    ],
    notes: [],
  });
}

function advancedAnalysisJson(projectId = "project_test") {
  return JSON.stringify({
    schemaVersion: "advanced-analysis-plan-0.1",
    projectId,
    maxBoundaries: 4,
    requests: [
      {
        boundaryIndex: 1,
        priority: 0.82,
        requestedFeatures: ["dense_flow", "depth"],
        leftWindow: { segmentId: "left", assetId: "a", shotId: "sa", sourceStartSeconds: 1.6, sourceEndSeconds: 2.1 },
        rightWindow: { segmentId: "right", assetId: "b", shotId: "sb", sourceStartSeconds: 0.8, sourceEndSeconds: 1.3 },
        reason: "zoom relation needs selective refinement",
        evidence: { recommendedMechanism: "zoom_bridge", relationScore: 0.72 },
      },
    ],
    skippedBoundaries: [{ boundaryIndex: 2, reason: "cheap evidence sufficient" }],
    notes: [],
  });
}

function advancedResultsJson(projectId = "project_test") {
  return JSON.stringify({
    schemaVersion: "advanced-analysis-results-0.1",
    projectId,
    boundaries: [
      {
        boundaryIndex: 1,
        priority: 0.82,
        leftFlow: {
          segmentId: "left", assetId: "a", shotId: "sa",
          sourceStartSeconds: 1.6, sourceEndSeconds: 2.1,
          sampleCount: 5, meanMagnitude: 1.4, p90Magnitude: 2.2,
          meanDx: 0.8, meanDy: 0.1, directionalCoherence: 0.72,
        },
        rightFlow: {
          segmentId: "right", assetId: "b", shotId: "sb",
          sourceStartSeconds: 0.8, sourceEndSeconds: 1.3,
          sampleCount: 5, meanMagnitude: 1.1, p90Magnitude: 1.9,
          meanDx: 0.7, meanDy: 0.08, directionalCoherence: 0.75,
        },
        flowDirectionCompatibility: 0.98,
        features: [
          {
            feature: "dense_flow",
            status: "completed",
            backend: "opencv-farneback",
            reason: "executed selectively",
            metrics: { leftSampleCount: 5, rightSampleCount: 5, directionCompatibility: 0.98 },
          },
          {
            feature: "depth",
            status: "backend_unavailable",
            backend: "unconfigured",
            reason: "no heavyweight backend configured",
            metrics: {},
          },
        ],
      },
    ],
    notes: [],
  });
}

function refinementJson(projectId = "project_test") {
  return JSON.stringify({
    schemaVersion: "transition-refinement-0.1",
    projectId,
    boundaries: [
      {
        boundaryIndex: 1,
        baseMechanism: "directional_bridge",
        refinedMechanism: "hard_cut",
        status: "demoted",
        reason: "selective dense flow contradicts the coarse directional match",
        flowDirectionCompatibility: 0.12,
        leftDirectionalCoherence: 0.74,
        rightDirectionalCoherence: 0.71,
        evidence: { baseRelationScore: 0.75, flowDirectionCompatibility: 0.12 },
      },
    ],
    notes: [],
  });
}

function correctionsJson() {
  return JSON.stringify({
    schemaVersion: "human-corrections-0.1",
    projectId: "project_test",
    createdAt: "2026-10-26T00:00:00Z",
    updatedAt: "2026-10-26T00:01:00Z",
    corrections: [
      {
        id: "correction_1",
        kind: "transition",
        targetType: "boundary",
        targetRef: "1",
        aiDecision: { mechanism: "directional_bridge" },
        humanDecision: { mechanism: "hard_cut" },
        context: { directorRole: "rupture", relationScore: 0.78 },
        reason: "The rupture should feel abrupt.",
        source: "cli",
        createdAt: "2026-10-26T00:01:00Z",
      },
    ],
    notes: [],
  });
}

function reviewsJson() {
  return JSON.stringify({
    schemaVersion: "decision-reviews-0.1",
    projectId: "project_test",
    createdAt: "2026-10-26T00:00:00Z",
    updatedAt: "2026-10-26T00:03:00Z",
    reviews: [
      {
        id: "review_1",
        kind: "transition",
        targetType: "boundary",
        targetRef: "1",
        aiDecision: { mechanism: "directional_bridge" },
        outcome: "corrected",
        correctionId: "correction_1",
        context: { directorRole: "rupture" },
        reason: "The rupture should stay abrupt.",
        source: "cli",
        createdAt: "2026-10-26T00:01:00Z",
      },
      {
        id: "review_2",
        kind: "transition",
        targetType: "boundary",
        targetRef: "2",
        aiDecision: { mechanism: "hard_cut" },
        outcome: "accepted",
        correctionId: null,
        context: { directorRole: "rupture" },
        reason: "Accepted as-is.",
        source: "cli",
        createdAt: "2026-10-26T00:03:00Z",
      },
    ],
    notes: [],
  });
}

function reviewSummaryJson() {
  return JSON.stringify({
    schemaVersion: "decision-review-summary-0.1",
    projectId: "project_test",
    generatedAt: "2026-10-26T00:04:00Z",
    reviewed: 2,
    accepted: 1,
    corrected: 1,
    acceptanceRate: 0.5,
    byKind: { transition: { reviewed: 2, accepted: 1, corrected: 1, acceptanceRate: 0.5 } },
    byDirectorRole: { rupture: { reviewed: 2, accepted: 1, corrected: 1, acceptanceRate: 0.5 } },
    byTransitionMechanism: {
      directional_bridge: { reviewed: 1, accepted: 0, corrected: 1, acceptanceRate: 0 },
      hard_cut: { reviewed: 1, accepted: 1, corrected: 0, acceptanceRate: 1 },
    },
    notes: [],
  });
}

function bundleFile(entries: Record<string, Uint8Array>) {
  return new Blob([zipSync(entries)], { type: "application/zip" });
}

describe("importMonterBundle", () => {
  it("loads project artifacts and a local rough-cut preview", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "rough-cut.mp4": new Uint8Array([0, 1, 2, 3]),
    });

    const result = await importMonterBundle(file);
    expect(result.artifacts.project?.projectName).toBe("Browser Bundle Test");
    expect(result.manifest.rawMediaIncluded).toBe(false);
    expect(result.preview?.type).toBe("video/mp4");
    expect(result.preview?.size).toBe(4);
  });

  it("loads transition opportunity reasoning from the bundle", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest({ includedArtifacts: ["project.monter.json", "transition-opportunities.json"] })),
      "project.monter.json": strToU8(projectJson()),
      "transition-opportunities.json": strToU8(opportunitiesJson()),
    });

    const result = await importMonterBundle(file);
    expect(result.artifacts.transitionOpportunities?.boundaries).toHaveLength(1);
    expect(result.artifacts.transitionOpportunities?.boundaries[0].recommendedMechanism).toBe("directional_bridge");
  });

  it("loads selective advanced-analysis requests from the bundle", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest({ includedArtifacts: ["project.monter.json", "advanced-analysis-plan.json"] })),
      "project.monter.json": strToU8(projectJson()),
      "advanced-analysis-plan.json": strToU8(advancedAnalysisJson()),
    });

    const result = await importMonterBundle(file);
    expect(result.artifacts.advancedAnalysis?.requests).toHaveLength(1);
    expect(result.artifacts.advancedAnalysis?.requests[0].requestedFeatures).toEqual(["dense_flow", "depth"]);
    expect(result.artifacts.advancedAnalysis?.requests[0].priority).toBe(0.82);
  });

  it("loads advanced-analysis execution results without pretending unavailable depth completed", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest({ includedArtifacts: ["project.monter.json", "advanced-analysis-results.json"] })),
      "project.monter.json": strToU8(projectJson()),
      "advanced-analysis-results.json": strToU8(advancedResultsJson()),
    });

    const result = await importMonterBundle(file);
    const boundary = result.artifacts.advancedResults?.boundaries[0];
    expect(boundary?.flowDirectionCompatibility).toBe(0.98);
    expect(boundary?.features.find((feature) => feature.feature === "dense_flow")?.status).toBe("completed");
    expect(boundary?.features.find((feature) => feature.feature === "depth")?.status).toBe("backend_unavailable");
  });

  it("loads transition refinement changes from executed flow evidence", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest({ includedArtifacts: ["project.monter.json", "transition-refinement.json"] })),
      "project.monter.json": strToU8(projectJson()),
      "transition-refinement.json": strToU8(refinementJson()),
    });

    const result = await importMonterBundle(file);
    const refinement = result.artifacts.transitionRefinement?.boundaries[0];
    expect(refinement?.status).toBe("demoted");
    expect(refinement?.baseMechanism).toBe("directional_bridge");
    expect(refinement?.refinedMechanism).toBe("hard_cut");
    expect(refinement?.flowDirectionCompatibility).toBe(0.12);
  });

  it("loads human correction decisions from the bundle", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest({ includedArtifacts: ["project.monter.json", "human-corrections.json"] })),
      "project.monter.json": strToU8(projectJson()),
      "human-corrections.json": strToU8(correctionsJson()),
    });

    const result = await importMonterBundle(file);
    const correction = result.artifacts.corrections?.corrections[0];
    expect(correction?.aiDecision.mechanism).toBe("directional_bridge");
    expect(correction?.humanDecision.mechanism).toBe("hard_cut");
    expect(correction?.context.directorRole).toBe("rupture");
  });

  it("loads decision review denominators and summary rates", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest({ includedArtifacts: ["project.monter.json", "human-corrections.json", "decision-reviews.json", "decision-review-summary.json"] })),
      "project.monter.json": strToU8(projectJson()),
      "human-corrections.json": strToU8(correctionsJson()),
      "decision-reviews.json": strToU8(reviewsJson()),
      "decision-review-summary.json": strToU8(reviewSummaryJson()),
    });

    const result = await importMonterBundle(file);
    expect(result.artifacts.reviews?.reviews).toHaveLength(2);
    expect(result.artifacts.reviewSummary?.reviewed).toBe(2);
    expect(result.artifacts.reviewSummary?.acceptanceRate).toBe(0.5);
    expect(result.artifacts.reviewSummary?.byTransitionMechanism.directional_bridge.acceptanceRate).toBe(0);
  });

  it("rejects a correction ledger from a different project", async () => {
    const mismatched = JSON.parse(correctionsJson());
    mismatched.projectId = "another_project";
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "human-corrections.json": strToU8(JSON.stringify(mismatched)),
    });

    await expect(importMonterBundle(file)).rejects.toThrow(/projectId does not match/i);
  });

  it("rejects advanced-analysis plans from another project", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "advanced-analysis-plan.json": strToU8(advancedAnalysisJson("another_project")),
    });
    await expect(importMonterBundle(file)).rejects.toThrow(/projectId does not match/i);
  });

  it("rejects advanced-analysis results from another project", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "advanced-analysis-results.json": strToU8(advancedResultsJson("another_project")),
    });
    await expect(importMonterBundle(file)).rejects.toThrow(/projectId does not match/i);
  });

  it("rejects transition refinement from another project", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "transition-refinement.json": strToU8(refinementJson("another_project")),
    });
    await expect(importMonterBundle(file)).rejects.toThrow(/projectId does not match/i);
  });

  it("rejects review evidence from a different project", async () => {
    const mismatched = JSON.parse(reviewSummaryJson());
    mismatched.projectId = "another_project";
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "decision-review-summary.json": strToU8(JSON.stringify(mismatched)),
    });
    await expect(importMonterBundle(file)).rejects.toThrow(/projectId does not match/i);
  });

  it("ignores unknown root entries instead of decompressing them", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "notes.txt": strToU8("not needed by Studio"),
    });

    const result = await importMonterBundle(file);
    expect(result.ignoredEntries).toContain("notes.txt");
  });

  it("rejects bundles that claim to embed RAW media", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest({ rawMediaIncluded: true })),
      "project.monter.json": strToU8(projectJson()),
    });

    await expect(importMonterBundle(file)).rejects.toThrow(/RAW media and proxies/i);
  });

  it("rejects unsafe archive paths", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
      "project.monter.json": strToU8(projectJson()),
      "../escape.json": strToU8("{}"),
    });

    await expect(importMonterBundle(file)).rejects.toThrow(/unsafe path/i);
  });

  it("rejects bundles without a project manifest", async () => {
    const file = bundleFile({
      "bundle-manifest.json": strToU8(manifest()),
    });

    await expect(importMonterBundle(file)).rejects.toThrow(/project\.monter\.json/i);
  });
});
