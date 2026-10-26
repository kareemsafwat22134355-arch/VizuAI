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
