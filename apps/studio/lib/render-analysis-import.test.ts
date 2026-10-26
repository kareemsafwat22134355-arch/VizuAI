import { describe, expect, it } from "vitest";
import { strToU8, zipSync } from "fflate";
import { importMonterBundle } from "./bundle-import";

function bundleFile(projectId = "project_render") {
  const project = {
    schemaVersion: "monter-project-0.1",
    projectId,
    projectName: "Render Analysis Test",
    createdAt: "2026-10-26T00:00:00Z",
    sourceRootLabel: "RAW",
    sourceBytes: 100,
    proxyBytes: 10,
    assets: [],
  };
  const renderAnalysis = {
    schemaVersion: "render-analysis-0.1",
    projectId,
    pathLabel: "rough-cut.mp4",
    status: "pass",
    durationSeconds: 4,
    expectedDurationSeconds: 4,
    durationDriftSeconds: 0,
    hasAudio: true,
    sampledFrames: 16,
    meanMotion: 0.4,
    peakMotion: 1,
    blackFrameFraction: 0,
    freezePairFraction: 0.1,
    longestFreezeSeconds: 0.25,
    energyAlignment: 0.73,
    energyBins: [],
    findings: [],
    notes: [],
  };
  const manifest = {
    schemaVersion: "monter-bundle-0.1",
    createdAt: "2026-10-26T00:00:00Z",
    includedArtifacts: ["project.monter.json", "render-analysis.json"],
    rawMediaIncluded: false,
    proxiesIncluded: false,
  };
  return new Blob([
    zipSync({
      "bundle-manifest.json": strToU8(JSON.stringify(manifest)),
      "project.monter.json": strToU8(JSON.stringify(project)),
      "render-analysis.json": strToU8(JSON.stringify(renderAnalysis)),
    }),
  ], { type: "application/zip" });
}

describe("render re-analysis bundle import", () => {
  it("keeps final-render evidence available for Studio review", async () => {
    const result = await importMonterBundle(bundleFile());
    expect(result.renderAnalysis?.status).toBe("pass");
    expect(result.renderAnalysis?.sampledFrames).toBe(16);
    expect(result.renderAnalysis?.energyAlignment).toBe(0.73);
    expect(result.ignoredEntries).not.toContain("render-analysis.json");
  });

  it("rejects render analysis evidence from another project", async () => {
    const projectId = "project_render";
    const file = bundleFile(projectId);
    const bytes = new Uint8Array(await file.arrayBuffer());
    // Rebuild the fixture with a mismatched report so project identity is never silently crossed.
    const manifest = {
      schemaVersion: "monter-bundle-0.1",
      createdAt: "2026-10-26T00:00:00Z",
      includedArtifacts: ["project.monter.json", "render-analysis.json"],
      rawMediaIncluded: false,
      proxiesIncluded: false,
    };
    void bytes;
    const mismatched = new Blob([
      zipSync({
        "bundle-manifest.json": strToU8(JSON.stringify(manifest)),
        "project.monter.json": strToU8(JSON.stringify({
          schemaVersion: "monter-project-0.1",
          projectId,
          projectName: "Render Analysis Test",
          createdAt: "2026-10-26T00:00:00Z",
          sourceRootLabel: "RAW",
          sourceBytes: 100,
          proxyBytes: 10,
          assets: [],
        })),
        "render-analysis.json": strToU8(JSON.stringify({
          schemaVersion: "render-analysis-0.1",
          projectId: "another_project",
          pathLabel: "rough-cut.mp4",
          status: "pass",
          durationSeconds: 4,
          expectedDurationSeconds: 4,
          durationDriftSeconds: 0,
          hasAudio: false,
          sampledFrames: 16,
          meanMotion: 0.2,
          peakMotion: 1,
          blackFrameFraction: 0,
          freezePairFraction: 0,
          longestFreezeSeconds: 0,
          energyAlignment: 0.7,
          energyBins: [],
          findings: [],
          notes: [],
        })),
      }),
    ], { type: "application/zip" });

    await expect(importMonterBundle(mismatched)).rejects.toThrow(/projectId does not match/i);
  });
});
