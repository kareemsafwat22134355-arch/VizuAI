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
