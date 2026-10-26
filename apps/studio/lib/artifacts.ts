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
  schemaVersion: "ctl-0.1" | "ctl-0.2";
  projectId: string;
  durationSeconds: number;
  clips: Array<{ id: string; assetId: string; shotId: string }>;
  transitions: Array<{
    boundaryIndex: number;
    mechanism: string;
    durationSeconds: number;
    relationScore?: number | null;
    evidence?: Record<string, string | number | boolean>;
    parameters?: Record<string, string | number | boolean>;
    reason: string;
  }>;
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

export type AdvancedFeature = "dense_flow" | "depth" | "segmentation";
export type SourceAnalysisWindow = {
  segmentId: string;
  assetId: string;
  shotId: string;
  sourceStartSeconds: number;
  sourceEndSeconds: number;
};
export type BoundaryAnalysisRequest = {
  boundaryIndex: number;
  priority: number;
  requestedFeatures: AdvancedFeature[];
  leftWindow: SourceAnalysisWindow;
  rightWindow: SourceAnalysisWindow;
  reason: string;
  evidence: Record<string, string | number | boolean>;
};
export type AdvancedAnalysisPlan = {
  schemaVersion: "advanced-analysis-plan-0.1";
  projectId: string;
  maxBoundaries: number;
  requests: BoundaryAnalysisRequest[];
  skippedBoundaries: Array<{ boundaryIndex: number; reason: string }>;
  notes: string[];
};

export type DenseFlowWindowSummary = {
  segmentId: string;
  assetId: string;
  shotId: string;
  sourceStartSeconds: number;
  sourceEndSeconds: number;
  sampleCount: number;
  meanMagnitude: number;
  p90Magnitude: number;
  meanDx: number;
  meanDy: number;
  directionalCoherence: number;
};
export type FeatureExecutionResult = {
  feature: AdvancedFeature;
  status: "completed" | "backend_unavailable" | "failed" | "skipped";
  backend: string;
  reason: string;
  metrics: Record<string, string | number | boolean>;
};
export type BoundaryExecutionResult = {
  boundaryIndex: number;
  priority: number;
  leftFlow?: DenseFlowWindowSummary | null;
  rightFlow?: DenseFlowWindowSummary | null;
  flowDirectionCompatibility?: number | null;
  features: FeatureExecutionResult[];
};
export type AdvancedAnalysisResults = {
  schemaVersion: "advanced-analysis-results-0.1";
  projectId: string;
  boundaries: BoundaryExecutionResult[];
  notes: string[];
};

export type DecisionScalar = string | number | boolean | null;
export type DecisionKind = "shot_selection" | "trim" | "transition" | "timewarp" | "role" | "other";
export type DecisionTargetType = "project" | "segment" | "boundary";

export type HumanCorrection = {
  id: string;
  kind: DecisionKind;
  targetType: DecisionTargetType;
  targetRef?: string | null;
  aiDecision: Record<string, DecisionScalar>;
  humanDecision: Record<string, DecisionScalar>;
  context: Record<string, DecisionScalar>;
  reason: string;
  source: "cli" | "studio" | "import" | "manual";
  createdAt: string;
};

export type CorrectionLedger = {
  schemaVersion: "human-corrections-0.1";
  projectId: string;
  createdAt: string;
  updatedAt: string;
  corrections: HumanCorrection[];
  notes: string[];
};

export type DecisionReview = {
  id: string;
  kind: DecisionKind;
  targetType: DecisionTargetType;
  targetRef?: string | null;
  aiDecision: Record<string, DecisionScalar>;
  outcome: "accepted" | "corrected";
  correctionId?: string | null;
  context: Record<string, DecisionScalar>;
  reason: string;
  source: "cli" | "studio" | "import" | "manual";
  createdAt: string;
};

export type DecisionReviewLedger = {
  schemaVersion: "decision-reviews-0.1";
  projectId: string;
  createdAt: string;
  updatedAt: string;
  reviews: DecisionReview[];
  notes: string[];
};

export type ReviewBucket = {
  reviewed: number;
  accepted: number;
  corrected: number;
  acceptanceRate: number;
};

export type DecisionReviewSummary = {
  schemaVersion: "decision-review-summary-0.1";
  projectId: string;
  generatedAt: string;
  reviewed: number;
  accepted: number;
  corrected: number;
  acceptanceRate: number;
  byKind: Record<string, ReviewBucket>;
  byDirectorRole: Record<string, ReviewBucket>;
  byTransitionMechanism: Record<string, ReviewBucket>;
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
  advancedAnalysis?: AdvancedAnalysisPlan;
  advancedResults?: AdvancedAnalysisResults;
  corrections?: CorrectionLedger;
  reviews?: DecisionReviewLedger;
  reviewSummary?: DecisionReviewSummary;
  critic?: CriticReport;
  production?: ProductionReport;
};

type JsonObject = Record<string, unknown>;
const isObject = (value: unknown): value is JsonObject => typeof value === "object" && value !== null && !Array.isArray(value);
const isNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const isCtlVersion = (value: unknown): value is CtlProgram["schemaVersion"] => value === "ctl-0.1" || value === "ctl-0.2";

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
  if (filename.endsWith("ctl.json") || isCtlVersion(value.schemaVersion)) {
    if (!isCtlVersion(value.schemaVersion) || !Array.isArray(value.transitions)) throw new Error(`${filename}: invalid CTL`);
    return { ctl: value as CtlProgram };
  }
  if (filename.endsWith("transition-opportunities.json")) {
    if (!Array.isArray(value.boundaries) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid transition opportunity report`);
    return { transitionOpportunities: value as TransitionOpportunityReport };
  }
  if (filename.endsWith("advanced-analysis-plan.json") || value.schemaVersion === "advanced-analysis-plan-0.1") {
    if (value.schemaVersion !== "advanced-analysis-plan-0.1" || !Array.isArray(value.requests) || !Array.isArray(value.skippedBoundaries) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid advanced analysis plan`);
    return { advancedAnalysis: value as AdvancedAnalysisPlan };
  }
  if (filename.endsWith("advanced-analysis-results.json") || value.schemaVersion === "advanced-analysis-results-0.1") {
    if (value.schemaVersion !== "advanced-analysis-results-0.1" || !Array.isArray(value.boundaries) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid advanced analysis results`);
    return { advancedResults: value as AdvancedAnalysisResults };
  }
  if (filename.endsWith("human-corrections.json") || value.schemaVersion === "human-corrections-0.1") {
    if (value.schemaVersion !== "human-corrections-0.1" || !Array.isArray(value.corrections) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid human correction ledger`);
    return { corrections: value as CorrectionLedger };
  }
  if (filename.endsWith("decision-reviews.json") || value.schemaVersion === "decision-reviews-0.1") {
    if (value.schemaVersion !== "decision-reviews-0.1" || !Array.isArray(value.reviews) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid decision review ledger`);
    return { reviews: value as DecisionReviewLedger };
  }
  if (filename.endsWith("decision-review-summary.json") || value.schemaVersion === "decision-review-summary-0.1") {
    if (value.schemaVersion !== "decision-review-summary-0.1" || !isNumber(value.reviewed) || typeof value.projectId !== "string") throw new Error(`${filename}: invalid decision review summary`);
    return { reviewSummary: value as DecisionReviewSummary };
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
    next.advancedAnalysis?.projectId,
    next.advancedResults?.projectId,
    next.corrections?.projectId,
    next.reviews?.projectId,
    next.reviewSummary?.projectId,
    next.critic?.projectId,
    next.production?.projectId,
  ].filter(Boolean);
  if (new Set(ids).size > 1) throw new Error(`${filename}: projectId does not match the currently loaded bundle`);
  return next;
}
