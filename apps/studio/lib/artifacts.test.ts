import { describe, expect, it } from "vitest";
import { mergeArtifacts, parseArtifact } from "./artifacts";

const project = {
  schemaVersion: "monter-project-0.1",
  projectId: "p1",
  projectName: "Trailer",
  createdAt: "2026-10-26T00:00:00Z",
  sourceRootLabel: "RAW",
  sourceBytes: 100,
  proxyBytes: 10,
  assets: [],
};

const vir = {
  schemaVersion: "vir-0.1",
  projectId: "p1",
  createdAt: "2026-10-26T00:00:00Z",
  shots: [],
  warnings: [],
};

describe("MONTER artifact parser", () => {
  it("identifies project and VIR by schema", () => {
    expect(parseArtifact("random.json", project).project?.projectId).toBe("p1");
    expect(parseArtifact("random.json", vir).vir?.schemaVersion).toBe("vir-0.1");
  });

  it("merges artifacts from one project", () => {
    const bundle = mergeArtifacts(mergeArtifacts({}, "project.monter.json", project), "vir.monter.json", vir);
    expect(bundle.project?.projectName).toBe("Trailer");
    expect(bundle.vir?.projectId).toBe("p1");
  });

  it("accepts CTL v0.2 while keeping v0.1 backward compatibility", () => {
    const ctlV2 = {
      schemaVersion: "ctl-0.2",
      projectId: "p1",
      durationSeconds: 4,
      clips: [],
      transitions: [
        {
          boundaryIndex: 1,
          mechanism: "directional_bridge",
          durationSeconds: 0.12,
          parameters: { screenDirection: "right" },
          reason: "fixture",
        },
      ],
      renderFps: 24,
      renderWidth: 960,
    };
    const ctlV1 = { ...ctlV2, schemaVersion: "ctl-0.1", transitions: [] };

    expect(parseArtifact("ctl.json", ctlV2).ctl?.schemaVersion).toBe("ctl-0.2");
    expect(parseArtifact("ctl.json", ctlV1).ctl?.schemaVersion).toBe("ctl-0.1");
  });

  it("merges CTL v0.2 into the same project bundle", () => {
    const ctl = {
      schemaVersion: "ctl-0.2",
      projectId: "p1",
      durationSeconds: 4,
      clips: [],
      transitions: [],
      renderFps: 24,
      renderWidth: 960,
    };
    const bundle = mergeArtifacts(mergeArtifacts({}, "project.monter.json", project), "ctl.json", ctl);
    expect(bundle.ctl?.projectId).toBe("p1");
  });

  it("rejects cross-project artifact bundles", () => {
    const otherVir = { ...vir, projectId: "p2" };
    const bundle = mergeArtifacts({}, "project.monter.json", project);
    expect(() => mergeArtifacts(bundle, "vir.monter.json", otherVir)).toThrow("projectId does not match");
  });

  it("rejects malformed named edit plans", () => {
    expect(() => parseArtifact("edit-plan.json", { segments: [] })).toThrow("invalid edit plan");
  });
});
