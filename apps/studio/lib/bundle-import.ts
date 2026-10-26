import { strFromU8, unzipSync } from "fflate";
import type { ArtifactBundle } from "./artifacts";
import { mergeArtifacts } from "./artifacts";

export const MAX_COMPRESSED_BUNDLE_BYTES = 512 * 1024 * 1024;
export const MAX_UNCOMPRESSED_BUNDLE_BYTES = 768 * 1024 * 1024;
export const MAX_ENTRY_BYTES = 512 * 1024 * 1024;

const JSON_ARTIFACTS = [
  "project.monter.json",
  "vir.monter.json",
  "director-plan.json",
  "edit-plan.json",
  "ctl.json",
  "critic-report.json",
  "transition-opportunities.json",
  "advanced-analysis-plan.json",
  "human-corrections.json",
  "decision-reviews.json",
  "decision-review-summary.json",
  "production-report.json",
  "audio-analysis.json",
] as const;

const ALLOWED_ENTRIES = new Set<string>([
  "bundle-manifest.json",
  ...JSON_ARTIFACTS,
  "edit.otio",
  "rough-cut.mp4",
]);

export type MonterBundleManifest = {
  schemaVersion: "monter-bundle-0.1";
  createdAt: string;
  includedArtifacts: string[];
  rawMediaIncluded: false;
  proxiesIncluded: false;
  notes?: string[];
};

export type ImportedMonterBundle = {
  artifacts: ArtifactBundle;
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
  if (value.schemaVersion !== "monter-bundle-0.1") {
    throw new Error("Unsupported MONTER bundle schema version.");
  }
  if (value.rawMediaIncluded !== false || value.proxiesIncluded !== false) {
    throw new Error("Unsafe MONTER bundle: RAW media and proxies must not be embedded.");
  }
  if (!Array.isArray(value.includedArtifacts) || typeof value.createdAt !== "string") {
    throw new Error("Invalid MONTER bundle manifest.");
  }
  return value as MonterBundleManifest;
}

export async function importMonterBundle(file: Blob): Promise<ImportedMonterBundle> {
  if (file.size > MAX_COMPRESSED_BUNDLE_BYTES) {
    throw new Error("MONTER bundle is too large for safe browser-local inspection. Re-export it with --no-preview.");
  }

  const compressed = new Uint8Array(await file.arrayBuffer());
  let totalAcceptedBytes = 0;
  const seenEntries: string[] = [];
  const ignoredEntries: string[] = [];

  const entries = unzipSync(compressed, {
    filter(entry) {
      seenEntries.push(entry.name);
      if (isUnsafeArchivePath(entry.name)) {
        throw new Error(`Unsafe path in MONTER bundle: ${entry.name}`);
      }
      if (!ALLOWED_ENTRIES.has(entry.name)) {
        ignoredEntries.push(entry.name);
        return false;
      }
      if (entry.originalSize > MAX_ENTRY_BYTES) {
        throw new Error(`MONTER bundle entry is too large: ${entry.name}`);
      }
      totalAcceptedBytes += entry.originalSize;
      if (totalAcceptedBytes > MAX_UNCOMPRESSED_BUNDLE_BYTES) {
        throw new Error("MONTER bundle expands beyond the browser safety limit.");
      }
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

  if (!artifacts.project) {
    throw new Error("MONTER bundle is missing a valid project.monter.json artifact.");
  }

  const previewBytes = entries["rough-cut.mp4"];
  const preview = previewBytes ? new Blob([previewBytes], { type: "video/mp4" }) : undefined;

  return { artifacts, manifest, preview, ignoredEntries };
}
