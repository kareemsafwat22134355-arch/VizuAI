export type MotionLevel = "low" | "medium" | "high";

export type MediaAsset = {
  id: string;
  filename: string;
  durationSeconds: number;
  width: number | null;
  height: number | null;
  fps: number | null;
  codec: string | null;
  hasAudio: boolean;
  sourceSizeBytes: number;
  motionLevel?: MotionLevel;
};

export type EditRole = "setup" | "promise" | "build" | "rupture" | "reveal" | "barrage" | "vacuum" | "payoff";

export type EditSegment = {
  id: string;
  assetId: string;
  sourceInSeconds: number;
  sourceOutSeconds: number;
  timelineInSeconds: number;
  timelineOutSeconds: number;
  role: EditRole;
  confidence: number;
  reason: string;
};

export type MonterProject = {
  schemaVersion: "monter-project-0.1";
  projectId: string;
  projectName: string;
  createdAt: string;
  sourceRootLabel: string;
  sourceBytes: number;
  proxyBytes: number;
  assets: MediaAsset[];
  director: {
    targetDurationSeconds: number;
    energyCurve: number[];
  };
  editPlan: EditSegment[];
};
