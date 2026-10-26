import { describe, expect, it } from "vitest";
import { sampleProject } from "./sample-project";
import { validateProject } from "./project-validation";

const clone = () => structuredClone(sampleProject);

describe("validateProject", () => {
  it("accepts the sample MONTER project", () => {
    expect(validateProject(sampleProject)).toEqual({ ok: true });
  });

  it("rejects an edit segment that references a missing asset", () => {
    const project = clone();
    project.editPlan[0].assetId = "missing";
    const result = validateProject(project);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.errors.join(" ")).toContain("missing asset");
  });

  it("rejects backwards source ranges", () => {
    const project = clone();
    project.editPlan[0].sourceOutSeconds = project.editPlan[0].sourceInSeconds;
    const result = validateProject(project);
    expect(result.ok).toBe(false);
  });
});
