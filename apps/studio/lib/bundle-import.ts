import { strFromU8, unzipSync } from "fflate";
import type { ArtifactBundle } from "./artifacts";
import { mergeArtifacts } from "./artifacts";

export const MAX_COMPRESSED_BUNDLE_BYTES = 512 * 1024 * 1024;
export const MAX_UNCOMPRESSED_BUNDLE_BYTES = 768 * 1024 * 1024;
export const MAX_ENTRY_BYTES = 512 * 1024 * 1024;

const JSON_ARTIFACTS = [
  "project.monter.json", "vir.monter.json", "director-plan.json", "edit-plan.json", "ctl.json",
  "critic-report.json", "transition-opportunities.json", "advanced-analysis-plan.json",
  "advanced-analysis-results.json", "transition-refinement.json", "human-corrections.json",
  "decision-reviews.json", "decision-review-summary.json", "production-report.json", "audio-analysis.json",
] as const;

const ALLOWED_ENTRIES = new Set<string>([
  "bundle-manifest.json", ...JSON_ARTIFACTS, "render-analysis.json", "final-critic-report.json",
  "post-render-revision-report.json", "edit.otio", "rough-cut.mp4", "rough-cut.audio.mp4",
]);

export type MonterBundleManifest = {
  schemaVersion: "monter-bundle-0.1";
  createdAt: string;
  includedArtifacts: string[];
  rawMediaIncluded: false;
  proxiesIncluded: false;
  notes?: string[];
};

export type RenderAnalysisReport = {
  schemaVersion: "render-analysis-0.1";
  projectId: string;
  pathLabel: string;
  status: "pass" | "needs_review";
  durationSeconds: number;
  expectedDurationSeconds: number;
  durationDriftSeconds: number;
  hasAudio: boolean;
  sampledFrames: number;
  meanMotion: number;
  peakMotion: number;
  blackFrameFraction: number;
  freezePairFraction: number;
  longestFreezeSeconds: number;
  energyAlignment: number;
  energyBins: Array<{
    index: number; startSeconds: number; endSeconds: number; meanMotion: number; meanLuma: number;
    blackFraction: number; freezeFraction: number; targetEnergy: number;
  }>;
  findings: Array<{ code: string; severity: "info" | "warning" | "error"; message: string }>;
  notes: string[];
};

export type FinalCriticReport = {
  schemaVersion: "final-critic-0.1";
  projectId: string;
  status: "pass" | "needs_revision" | "needs_review";
  automaticRevisionCandidates: number;
  manualReviewFindings: number;
  metrics: Array<{
    name: string;
    domain: "editorial" | "render_integrity" | "audio_integrity";
    value: number;
    target: string;
    passed: boolean;
  }>;
  findings: Array<{
    code: string;
    domain: "editorial" | "render_integrity" | "audio_integrity";
    severity: "info" | "warning" | "error";
    reviseability: "automatic_candidate" | "manual_only" | "not_applicable";
    message: string;
    sourceArtifact: string;
    segmentId?: string | null;
    boundaryIndex?: number | null;
    suggestedShiftSeconds?: number | null;
  }>;
  notes: string[];
};

export type PostRenderRevisionReport = {
  schemaVersion: "post-render-revision-0.1";
  projectId: string;
  eligible: boolean;
  attempted: boolean;
  changed: boolean;
  accepted: boolean;
  reason: string;
  baselineFinalStatus: string;
  candidateFinalStatus?: string | null;
  baselineAutomaticCandidates: number;
  candidateAutomaticCandidates?: number | null;
  changedSegments: string[];
  changedBoundaries?: number[];
  candidateDir?: string | null;
  baselineSnapshotDir?: string | null;
  promotedArtifacts: string[];
  notes: string[];
};

export type ImportedMonterBundle = {
  artifacts: ArtifactBundle;
  renderAnalysis?: RenderAnalysisReport;
  finalCritic?: FinalCriticReport;
  postRenderRevision?: PostRenderRevisionReport;
  manifest: MonterBundleManifest;
  preview?: Blob;
  ignoredEntries: string[];
};

function isUnsafeArchivePath(name: string) {
  if (!name || name.startsWith("/") || name.startsWith("\\")) return true;
  if (/^[A-Za-z]:[\\/]/.test(name)) return true;
  const segments = name.replaceAll("\\", "/").split("/");
  return segments.some((segment) => segment === ".." || segment === ".");
}

function parseManifest(bytes: Uint8Array): MonterBundleManifest {
  const value = JSON.parse(strFromU8(bytes)) as Partial<MonterBundleManifest>;
  if (value.schemaVersion !== "monter-bundle-0.1") throw new Error("Unsupported MONTER bundle schema version.");
  if (value.rawMediaIncluded !== false || value.proxiesIncluded !== false) throw new Error("Unsafe MONTER bundle: RAW media and proxies must not be embedded.");
  if (!Array.isArray(value.includedArtifacts) || typeof value.createdAt !== "string") throw new Error("Invalid MONTER bundle manifest.");
  return value as MonterBundleManifest;
}

function parseRenderAnalysis(bytes: Uint8Array): RenderAnalysisReport {
  const value = JSON.parse(strFromU8(bytes)) as Partial<RenderAnalysisReport>;
  if (value.schemaVersion !== "render-analysis-0.1" || typeof value.projectId !== "string" || typeof value.status !== "string" || typeof value.sampledFrames !== "number" || !Array.isArray(value.energyBins) || !Array.isArray(value.findings)) {
    throw new Error("render-analysis.json: invalid render re-analysis report");
  }
  return value as RenderAnalysisReport;
}

function parseFinalCritic(bytes: Uint8Array): FinalCriticReport {
  const value = JSON.parse(strFromU8(bytes)) as Partial<FinalCriticReport>;
  if (value.schemaVersion !== "final-critic-0.1" || typeof value.projectId !== "string" || typeof value.status !== "string" || typeof value.automaticRevisionCandidates !== "number" || !Array.isArray(value.metrics) || !Array.isArray(value.findings)) {
    throw new Error("final-critic-report.json: invalid final critic report");
  }
  return value as FinalCriticReport;
}

function parsePostRenderRevision(bytes: Uint8Array): PostRenderRevisionReport {
  const value = JSON.parse(strFromU8(bytes)) as Partial<PostRenderRevisionReport>;
  if (
    value.schemaVersion !== "post-render-revision-0.1"
    || typeof value.projectId !== "string"
    || typeof value.attempted !== "boolean"
    || typeof value.accepted !== "boolean"
    || typeof value.reason !== "string"
    || !Array.isArray(value.changedSegments)
    || !Array.isArray(value.promotedArtifacts)
  ) {
    throw new Error("post-render-revision-report.json: invalid post-render revision report");
  }
  if (value.changedBoundaries !== undefined && !Array.isArray(value.changedBoundaries)) {
    throw new Error("post-render-revision-report.json: invalid changedBoundaries");
  }
  return value as PostRenderRevisionReport;
}

export async function importMonterBundle(file: Blob): Promise<ImportedMonterBundle> {
  if (file.size > MAX_COMPRESSED_BUNDLE_BYTES) throw new Error("MONTER bundle is too large for safe browser-local inspection. Re-export it with --no-preview.");
  const compressed = new Uint8Array(await file.arrayBuffer());
  let totalAcceptedBytes = 0;
  const seenEntries: string[] = [];
  const ignoredEntries: string[] = [];

  const entries = unzipSync(compressed, {
    filter(entry) {
      seenEntries.push(entry.name);
      if (isUnsafeArchivePath(entry.name)) throw new Error(`Unsafe path in MONTER bundle: ${entry.name}`);
      if (!ALLOWED_ENTRIES.has(entry.name)) { ignoredEntries.push(entry.name); return false; }
      if (entry.originalSize > MAX_ENTRY_BYTES) throw new Error(`MONTER bundle entry is too large: ${entry.name}`);
      totalAcceptedBytes += entry.originalSize;
      if (totalAcceptedBytes > MAX_UNCOMPRESSED_BUNDLE_BYTES) throw new Error("MONTER bundle expands beyond the browser safety limit.");
      return true;
    },
  });

  if (seenEntries.length === 0) throw new Error("MONTER bundle is empty.");
  const manifestBytes = entries["bundle-manifest.json"];
  if (!manifestBytes) throw new Error("MONTER bundle is missing bundle-manifest.json.");
  const manifest = parseManifest(manifestBytes);

  let artifacts: ArtifactBundle = {};
  for (const filename of JSON_ARTIFACTS) {
    const bytes = entries[filename];
    if (!bytes) continue;
    artifacts = mergeArtifacts(artifacts, filename, JSON.parse(strFromU8(bytes)));
  }
  if (!artifacts.project) throw new Error("MONTER bundle is missing a valid project.monter.json artifact.");

  const renderAnalysisBytes = entries["render-analysis.json"];
  const renderAnalysis = renderAnalysisBytes ? parseRenderAnalysis(renderAnalysisBytes) : undefined;
  if (renderAnalysis && renderAnalysis.projectId !== artifacts.project.projectId) throw new Error("render-analysis.json: projectId does not match the currently loaded bundle");

  const finalCriticBytes = entries["final-critic-report.json"];
  const finalCritic = finalCriticBytes ? parseFinalCritic(finalCriticBytes) : undefined;
  if (finalCritic && finalCritic.projectId !== artifacts.project.projectId) throw new Error("final-critic-report.json: projectId does not match the currently loaded bundle");

  const postRenderRevisionBytes = entries["post-render-revision-report.json"];
  const postRenderRevision = postRenderRevisionBytes ? parsePostRenderRevision(postRenderRevisionBytes) : undefined;
  if (postRenderRevision && postRenderRevision.projectId !== artifacts.project.projectId) throw new Error("post-render-revision-report.json: projectId does not match the currently loaded bundle");

  const previewBytes = entries["rough-cut.audio.mp4"] ?? entries["rough-cut.mp4"];
  const preview = previewBytes ? new Blob([previewBytes], { type: "video/mp4" }) : undefined;
  return { artifacts, renderAnalysis, finalCritic, postRenderRevision, manifest, preview, ignoredEntries };
}
