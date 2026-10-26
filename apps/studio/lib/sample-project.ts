import type { MonterProject } from "./contracts";

export const sampleProject: MonterProject = {
  schemaVersion: "monter-project-0.1",
  projectId: "proof-001",
  projectName: "MONTER Proof 001",
  createdAt: "2026-10-26T12:00:00Z",
  sourceRootLabel: "RAW",
  sourceBytes: 10_737_418_240,
  proxyBytes: 448_790_528,
  assets: [
    { id: "a001", filename: "A001.mp4", sourceRelPath: "A001.mp4", durationSeconds: 14.4, width: 3840, height: 2160, fps: 50, codec: "h264", hasAudio: true, sourceSizeBytes: 811_200_000, motionLevel: "low" },
    { id: "a014", filename: "A014.mp4", sourceRelPath: "camera-a/A014.mp4", durationSeconds: 8.7, width: 3840, height: 2160, fps: 50, codec: "h264", hasAudio: true, sourceSizeBytes: 641_100_000, motionLevel: "high" },
    { id: "a031", filename: "A031.mp4", sourceRelPath: "camera-a/A031.mp4", durationSeconds: 22.1, width: 3840, height: 2160, fps: 50, codec: "h264", hasAudio: true, sourceSizeBytes: 1_201_200_000, motionLevel: "medium" },
    { id: "a043", filename: "A043.mp4", sourceRelPath: "camera-b/A043.mp4", durationSeconds: 16.8, width: 3840, height: 2160, fps: 50, codec: "h264", hasAudio: false, sourceSizeBytes: 932_400_000, motionLevel: "high" },
    { id: "a052", filename: "A052.mp4", sourceRelPath: "camera-b/A052.mp4", durationSeconds: 11.3, width: 3840, height: 2160, fps: 50, codec: "h264", hasAudio: true, sourceSizeBytes: 723_300_000, motionLevel: "medium" }
  ],
  director: {
    targetDurationSeconds: 15,
    energyCurve: [16, 18, 22, 25, 31, 38, 47, 60, 74, 89, 96, 82, 66, 48, 35, 22]
  },
  editPlan: [
    { id: "e01", assetId: "a031", sourceInSeconds: 2.1, sourceOutSeconds: 4.4, timelineInSeconds: 0, timelineOutSeconds: 2.3, role: "setup", confidence: 0.81, reason: "Low-information opening with stable subject readability." },
    { id: "e02", assetId: "a014", sourceInSeconds: 4.8, sourceOutSeconds: 6.3, timelineInSeconds: 2.3, timelineOutSeconds: 3.8, role: "build", confidence: 0.88, reason: "Strong motion onset increases energy without spending the peak." },
    { id: "e03", assetId: "a043", sourceInSeconds: 11.2, sourceOutSeconds: 12.1, timelineInSeconds: 3.8, timelineOutSeconds: 4.7, role: "rupture", confidence: 0.93, reason: "Motion apex creates a deliberate discontinuity." },
    { id: "e04", assetId: "a052", sourceInSeconds: 6.1, sourceOutSeconds: 8.4, timelineInSeconds: 4.7, timelineOutSeconds: 7, role: "payoff", confidence: 0.86, reason: "Cleaner composition gives the viewer a readable payoff after the rupture." }
  ]
};
