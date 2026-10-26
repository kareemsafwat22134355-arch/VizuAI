import { describe, expect, it } from "vitest";
import { strToU8, zipSync } from "fflate";
import { importMonterBundle } from "./bundle-import";

function projectJson() {
  return JSON.stringify({
    schemaVersion: "monter-project-0.1",
    projectId: "audio_preview",
    projectName: "Audio Preview",
    createdAt: "2026-10-26T00:00:00Z",
    sourceRootLabel: "RAW",
    sourceBytes: 1,
    proxyBytes: 1,
    assets: [],
  });
}

function manifest() {
  return JSON.stringify({
    schemaVersion: "monter-bundle-0.1",
    createdAt: "2026-10-26T00:00:00Z",
    includedArtifacts: ["project.monter.json", "rough-cut.mp4", "rough-cut.audio.mp4"],
    rawMediaIncluded: false,
    proxiesIncluded: false,
  });
}

describe("audio-aware bundle preview", () => {
  it("prefers rough-cut.audio.mp4 over the older silent/music-only rough cut", async () => {
    const file = new Blob([
      zipSync({
        "bundle-manifest.json": strToU8(manifest()),
        "project.monter.json": strToU8(projectJson()),
        "rough-cut.mp4": new Uint8Array([1, 2]),
        "rough-cut.audio.mp4": new Uint8Array([9, 8, 7, 6]),
      }),
    ], { type: "application/zip" });

    const result = await importMonterBundle(file);
    expect(result.preview?.size).toBe(4);
    expect(new Uint8Array(await result.preview!.arrayBuffer())).toEqual(new Uint8Array([9, 8, 7, 6]));
  });
});
