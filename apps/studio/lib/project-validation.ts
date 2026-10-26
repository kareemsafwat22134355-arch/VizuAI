import type { MonterProject } from "./contracts";

export type ValidationResult = { ok: true } | { ok: false; errors: string[] };

export function validateProject(project: MonterProject): ValidationResult {
  const errors: string[] = [];
  const assetIds = new Set(project.assets.map((asset) => asset.id));

  if (project.schemaVersion !== "monter-project-0.1") errors.push("unsupported schema version");
  if (!project.projectId.trim()) errors.push("projectId is required");
  if (!project.projectName.trim()) errors.push("projectName is required");
  if (project.sourceBytes < 0 || project.proxyBytes < 0) errors.push("byte counts cannot be negative");

  for (const segment of project.editPlan) {
    if (!assetIds.has(segment.assetId)) errors.push(`segment ${segment.id} references missing asset ${segment.assetId}`);
    if (segment.sourceOutSeconds <= segment.sourceInSeconds) errors.push(`segment ${segment.id} has invalid source range`);
    if (segment.timelineOutSeconds <= segment.timelineInSeconds) errors.push(`segment ${segment.id} has invalid timeline range`);
    if (segment.confidence < 0 || segment.confidence > 1) errors.push(`segment ${segment.id} confidence must be 0..1`);
  }

  return errors.length === 0 ? { ok: true } : { ok: false, errors };
}
