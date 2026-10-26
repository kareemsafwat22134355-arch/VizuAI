import { describe, expect, it } from "vitest";
import { strToU8, zipSync } from "fflate";
import { importMonterBundle } from "./bundle-import";

function makeBundle(finalProjectId = "p") {
  const manifest = {
    schemaVersion: "monter-bundle-0.1",
    createdAt: "2026-10-26T00:00:00Z",
    includedArtifacts: ["project.monter.json", "final-critic-report.json"],
    rawMediaIncluded: false,
    proxiesIncluded: false,
  };
  const project = {
    schemaVersion: "monter-project-0.1",
    projectId: "p",
    projectName: "Final Critic Test",
    createdAt: "2026-10-26T00:00:00Z",
    sourceRootLabel: "RAW",
    sourceBytes: 1,
    proxyBytes: 1,
    assets: [],
  };
  const finalCritic = {
    schemaVersion: "final-critic-0.1",
    projectId: finalProjectId,
    status: "needs_review",
    automaticRevisionCandidates: 1,
    manualReviewFindings: 1,
    metrics: [],
    findings: [{
      code: "duration_drift",
      domain: "render_integrity",
      severity: "error",
      reviseability: "manual_only",
      message: "encoded duration drifted",
      sourceArtifact: "render-analysis.json",
    }],
    notes: [],
  };
  return new Blob([zipSync({
    "bundle-manifest.json": strToU8(JSON.stringify(manifest)),
    "project.monter.json": strToU8(JSON.stringify(project)),
    "final-critic-report.json": strToU8(JSON.stringify(finalCritic)),
  })], { type: "application/zip" });
}

describe("final critic bundle import", () => {
  it("keeps consolidated quality evidence available to Studio", async () => {
    const result = await importMonterBundle(makeBundle());
    expect(result.finalCritic?.status).toBe("needs_review");
    expect(result.finalCritic?.automaticRevisionCandidates).toBe(1);
    expect(result.finalCritic?.findings[0].domain).toBe("render_integrity");
    expect(result.ignoredEntries).not.toContain("final-critic-report.json");
  });

  it("rejects a final critic from another project", async () => {
    await expect(importMonterBundle(makeBundle("another"))).rejects.toThrow(/projectId does not match/i);
  });
});
