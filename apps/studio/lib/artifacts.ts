export type MediaAsset = {
  id: string;
  filename: string;
  sourceRelPath: string;
  sourceSizeBytes: number;
  durationSeconds: number;
  width: number | null;
  height: number | null;
  fps: number | null;
  codec: string | null;
  hasAudio: boolean;
};

export type ProjectManifest = {
  schemaVersion: "monter-project-0.1";
  projectId: string;
  projectName: string;
  createdAt: string;
  sourceRootLabel: string;
  sourceBytes: number;
  proxyBytes: number;
  assets: MediaAsset[];
};

export type MotionSample = { timeSeconds: number; magnitude: number };
export type EditAnchor = { type: string; timeSeconds: number; confidence: number; reason: string };
export type ShotAnalysis = {
  id: string;
  assetId: string;
  range: { startSeconds: number; endSeconds: number };
  meanMotion: number;
  peakMotion: number;
  motionSamples: MotionSample[];
  editAnchors: EditAnchor[];
};
export type VirProject = {
  schemaVersion: "vir-0.1";
  projectId: string;
  createdAt: string;
  shots: ShotAnalysis[];
  warnings: string[];
};

export type EditRole = "setup" | "promise" | "build" | "escalate" | "rupture" | "reveal" | "barrage" | "vacuum" | "payoff";
export type EditSegment = {
  id: string;
  assetId: string;
  shotId: string;
  sourceInSeconds: number;
  sourceOutSeconds: number;
  timelineInSeconds: number;
  timelineOutSeconds: number;
  role: EditRole;
  targetEnergy: number;
  shotEnergy: number;
  confidence: number;
  reason: string;
};
export type EditPlan = {
  projectId: string;
  targetDurationSeconds: number;
  actualDurationSeconds: number;
  segments: EditSegment[];
  strategyNotes: string[];
};

export type DirectorPlan = {
  targetDurationSeconds: number;
  energyCurve: number[];
  sections: Array<{ role: EditRole; startNormalized: number; endNormalized: number }>;
  restrictions: string[];
};

export type CtlProgram = {
  schemaVersion: "ctl-0.1";
  projectId: string;
  durationSeconds: number;
  clips: Array<{ id: string; assetId: string; shotId: string }>;
  transitions: Array<{ boundaryIndex: number; mechanism: string; durationSeconds: number; reason: string }>;
  renderFps: number;
  renderWidth: number;
};

export type TransitionCandidate = {
  mechanism: "hard_cut" | "action_cut" | "directional_bridge" | "zoom_bridge";
  durationSeconds: number;
  requiredHandleSeconds: number;
  feasible: boolean;
  feasibilityScore: number;
  motivationScore: number;
  relationScore: number;
  parameters: Record<string, string | number | boolean>;
  reason: string;
};

export type BoundaryTransitionOpportunity = {
  boundaryIndex: number;
  leftSegmentId: string;
  rightSegmentId: string;
  outgoingHandleSeconds: number;
  incomingHandleSeconds: number;
  cutSignature: {
    directionCompatibility: number;
    zoomCompatibility: number;
    phaseCompatibility: number;
    globalMotionConfidence: number;
    relationScore: number;
  };
  recommendedMechanism: TransitionCandidate["mechanism"];
  candidates: TransitionCandidate[];
};

export type TransitionOpportunityReport = {
  projectId: string;
  boundaries: BoundaryTransitionOpportunity[];
  notes: string[];
};

export type CriticReport = {
  projectId: string;
  status: "pass" | "needs_revision";
  metrics: Array<{ name: string; value: number; target: string; passed: boolean }>;
  findings: Array<{ code: string; severity: "info" | "warning" | "error"; message: string; segmentId?: string | null; boundaryIndex?: number | null }>;
  notes: string[];
};

export type ProductionReport = {
  projectId: string;
  status: "pass" | "needs_review";
  revisionIterations: number;
  assetsIngested: number;
  shotsAnalyzed: number;
  editSegments: number;
  targetDurationSeconds: number;
  actualDurationSeconds: number;
  artifacts: string[];
  warnings: string[];
};

export type ArtifactBundle = {
  project?: ProjectManifest;
  vir?: VirProject;
  director?: DirectorPlan;
  edit?: EditPlan;
  ctl?: CtlProgram;
  transitionOpportunities?: TransitionOpportunityReport;
  critic?: CriticReport;
  production?: ProductionReport;
};

type JsonObject = Record<string, unknown>;
const isObject = (value: unknown): value is JsonObject => typeof value === "object" && value !== null && !Array.isArray(value);
const isNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

export function parseArtifact(filename: string, value: unknown): Partial<ArtifactBundle> {
  if (!isObject(value)) throw new Error(`${filename}: expected a JSON object`);

  if (filename.endsWith("project.monter.json") || value.schemaVersion === "monter-project-0.1") {
    if (value.schemaVersion !== "monter-project-0.1" || !Array.isArray(value.assets) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid project manifest`);
    return { project: value as ProjectManifest };
  }
  if (filename.endsWith("vir.monter.json") || value.schemaVersion === "vir-0.1") {
    if (value.schemaVersion !== "vir-0.1" || !Array.isArray(value.shots) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid VIR`);
    return { vir: value as VirProject };
  }
  if (filename.endsWith("director-plan.json")) {
    if (!Array.isArray(value.energyCurve) || !isNumber(value.targetDurationSeconds)) throw new Error(`${filename}: invalid director plan`);
    return { director: value as DirectorPlan };
  }
  if (filename.endsWith("edit-plan.json")) {
    if (!Array.isArray(value.segments) || !isNumber(value.actualDurationSeconds)) throw new Error(`${filename}: invalid edit plan`);
    return { edit: value as EditPlan };
  }
  if (filename.endsWith("ctl.json") || value.schemaVersion === "ctl-0.1") {
    if (value.schemaVersion !== "ctl-0.1" || !Array.isArray(value.transitions)) throw new Error(`${filename}: invalid CTL`);
    return { ctl: value as CtlProgram };
  }
  if (filename.endsWith("transition-opportunities.json")) {
    if (!Array.isArray(value.boundaries) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid transition opportunity report`);
    return { transitionOpportunities: value as TransitionOpportunityReport };
  }
  if (filename.endsWith("critic-report.json")) {
    if (!Array.isArray(value.metrics) || !Array.isArray(value.findings)) throw new Error(`${filename}: invalid critic report`);
    return { critic: value as CriticReport };
  }
  if (filename.endsWith("production-report.json")) {
    if (!Array.isArray(value.artifacts) || typeof value.status !== "string") throw new Error(`${filename}: invalid production report`);
    return { production: value as ProductionReport };
  }
  return {};
}

export function mergeArtifacts(current: ArtifactBundle, filename: string, value: unknown): ArtifactBundle {
  const patch = parseArtifact(filename, value);
  const next = { ...current, ...patch };
  const ids = [
    next.project?.projectId,
    next.vir?.projectId,
    next.edit?.projectId,
    next.ctl?.projectId,
    next.transitionOpportunities?.projectId,
    next.critic?.projectId,
    next.production?.projectId,
  ].filter(Boolean);
  if (new Set(ids).size > 1) throw new Error(`${filename}: projectId does not match the currently loaded bundle`);
  return next;
}
