import { describe, expect, it } from "vitest";
import { strToU8, zipSync } from "fflate";
import { importMonterBundle } from "./bundle-import";

function bundle(reportProjectId = "p") {
  const manifest = {
    schemaVersion: "monter-bundle-0.1",
    createdAt: "2026-10-26T00:00:00Z",
    includedArtifacts: ["project.monter.json", "post-render-revision-report.json"],
    rawMediaIncluded: false,
    proxiesIncluded: false,
  };
  const project = {
    schemaVersion: "monter-project-0.1",
    projectId: "p",
    projectName: "Post Render Revision Test",
    createdAt: "2026-10-26T00:00:00Z",
    sourceRootLabel: "RAW",
    sourceBytes: 1,
    proxyBytes: 1,
    assets: [],
  };
  const report = {
    schemaVersion: "post-render-revision-0.1",
    projectId: reportProjectId,
    eligible: true,
    attempted: true,
    changed: true,
    accepted: false,
    reason: "candidate did not pass",
    baselineFinalStatus: "needs_revision",
    candidateFinalStatus: "needs_revision",
    baselineAutomaticCandidates: 1,
    candidateAutomaticCandidates: 1,
    changedSegments: ["s1"],
    changedBoundaries: [2],
    candidateDir: "post-render-candidate-01",
    baselineSnapshotDir: null,
    promotedArtifacts: [],
    notes: [],
  };
  return new Blob([zipSync({
    "bundle-manifest.json": strToU8(JSON.stringify(manifest)),
    "project.monter.json": strToU8(JSON.stringify(project)),
    "post-render-revision-report.json": strToU8(JSON.stringify(report)),
  })], { type: "application/zip" });
}

describe("post-render revision bundle import", () => {
  it("keeps acceptance/rejection and changed-boundary evidence without candidate media", async () => {
    const result = await importMonterBundle(bundle());
    expect(result.postRenderRevision?.attempted).toBe(true);
    expect(result.postRenderRevision?.accepted).toBe(false);
    expect(result.postRenderRevision?.changedSegments).toEqual(["s1"]);
    expect(result.postRenderRevision?.changedBoundaries).toEqual([2]);
    expect(result.ignoredEntries).not.toContain("post-render-revision-report.json");
  });

  it("rejects a transaction report from another project", async () => {
    await expect(importMonterBundle(bundle("other"))).rejects.toThrow(/projectId does not match/i);
  });
});
