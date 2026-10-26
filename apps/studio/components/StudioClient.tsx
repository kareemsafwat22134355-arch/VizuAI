"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import type { ArtifactBundle, DecisionScalar, ReviewBucket } from "@/lib/artifacts";
import { mergeArtifacts } from "@/lib/artifacts";
import { importMonterBundle } from "@/lib/bundle-import";
import { Waveform } from "./Waveform";

function formatBytes(bytes?: number) {
  if (bytes == null) return "—";
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)} MB`;
  return `${Math.round(bytes / 1_000)} KB`;
}

function metricLabel(name: string) {
  return name.replaceAll("_", " ");
}

function formatDecision(values: Record<string, DecisionScalar>) {
  const entries = Object.entries(values);
  if (entries.length === 0) return "—";
  return entries.map(([key, value]) => `${metricLabel(key)}=${String(value)}`).join(" · ");
}

function formatRate(value: number) {
  return `${Math.round(value * 100)}%`;
}

function ReviewBucketRow({ label, bucket }: { label: string; bucket: ReviewBucket }) {
  return <div className="assetRow">
    <div><strong>{metricLabel(label)}</strong><span>{bucket.reviewed} reviewed</span></div>
    <span>{bucket.accepted} accepted</span>
    <span>{bucket.corrected} corrected</span>
    <span>{formatRate(bucket.acceptanceRate)}</span>
  </div>;
}

export function StudioClient() {
  const [bundle, setBundle] = useState<ArtifactBundle>({});
  const [errors, setErrors] = useState<string[]>([]);
  const [videoUrl, setVideoUrl] = useState<string>();
  const [audioUrl, setAudioUrl] = useState<string>();
  const [sourceLabel, setSourceLabel] = useState("loose artifacts");

  useEffect(() => () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [videoUrl, audioUrl]);

  const assetById = useMemo(() => new Map(bundle.project?.assets.map((asset) => [asset.id, asset]) ?? []), [bundle.project]);
  const loadedCount = Object.values(bundle).filter(Boolean).length;

  function replaceVideo(blob?: Blob) {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoUrl(blob ? URL.createObjectURL(blob) : undefined);
  }

  function replaceAudio(blob?: Blob) {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(blob ? URL.createObjectURL(blob) : undefined);
  }

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    let next = bundle;
    const nextErrors: string[] = [];

    for (const file of files) {
      try {
        if (file.name.endsWith(".monter.zip") || file.name.endsWith(".zip")) {
          const imported = await importMonterBundle(file);
          next = imported.artifacts;
          replaceVideo(imported.preview);
          setSourceLabel(`${file.name} · local bundle`);
          continue;
        }
        if (file.type.startsWith("video/")) {
          replaceVideo(file);
          continue;
        }
        if (file.type.startsWith("audio/")) {
          replaceAudio(file);
          continue;
        }
        if (!file.name.endsWith(".json")) continue;
        next = mergeArtifacts(next, file.name, JSON.parse(await file.text()));
        setSourceLabel("loose local artifacts");
      } catch (error) {
        nextErrors.push(error instanceof Error ? error.message : `${file.name}: failed to load`);
      }
    }

    setBundle(next);
    setErrors(nextErrors);
    event.target.value = "";
  }

  const projectName = bundle.project?.projectName ?? "Load a MONTER project";
  const duration = bundle.edit?.actualDurationSeconds ?? bundle.production?.actualDurationSeconds;

  return <div className="shell">
    <aside className="sidebar">
      <div><div className="brand">MONTER</div><div className="brandSub">cinematic intelligence</div></div>
      <nav className="nav" aria-label="Workspace sections">
        <a className="navItem navActive" href="#project">Project</a>
        <a className="navItem" href="#preview">Preview</a>
        <a className="navItem" href="#director">Director</a>
        <a className="navItem" href="#timeline">Timeline</a>
        <a className="navItem" href="#transitions">Transitions</a>
        <a className="navItem" href="#compute">Compute</a>
        <a className="navItem" href="#corrections">Corrections</a>
        <a className="navItem" href="#reviews">Reviews</a>
        <a className="navItem" href="#critic">Critic</a>
      </nav>
      <div className="sidebarFooter"><span className="tinyLabel">PRIVACY</span><strong>Local files stay local</strong><p>`.monter.zip`, JSON, video and audio are decoded through browser File APIs. Studio does not upload the project to a server.</p></div>
    </aside>

    <main className="main" id="project">
      <header className="topbar">
        <div><p className="eyebrow">LOCAL PROJECT INSPECTOR</p><h1>{projectName}</h1><p className="subtitle">Open one `.monter.zip` from the Local Bridge, or load loose artifacts manually.</p></div>
        <label className="importButton">Load project<input type="file" multiple accept=".zip,.json,application/zip,application/json,video/*,audio/*" onChange={handleFiles} /></label>
      </header>

      {errors.length > 0 && <div className="errorBox">{errors.map((error) => <div key={error}>{error}</div>)}</div>}

      <section className="statsGrid" aria-label="Project metrics">
        <article className="card statCard"><p className="label">RAW FOOTAGE</p><strong className="statValue">{formatBytes(bundle.project?.sourceBytes)}</strong><span className="statNote">never uploaded</span></article>
        <article className="card statCard"><p className="label">PROXIES</p><strong className="statValue">{formatBytes(bundle.project?.proxyBytes)}</strong><span className="statNote">local bridge</span></article>
        <article className="card statCard"><p className="label">SHOTS</p><strong className="statValue">{bundle.vir?.shots.length ?? "—"}</strong><span className="statNote">VIR analysis</span></article>
        <article className="card statCard"><p className="label">CUT</p><strong className="statValue">{duration != null ? `${duration.toFixed(2)}s` : "—"}</strong><span className="statNote">{loadedCount} types · {sourceLabel}</span></article>
      </section>

      <section className="contentGrid">
        <article className="card previewCard" id="preview">
          <div className="sectionHeading"><div><p className="label">LOCAL PREVIEW</p><h2>Rough cut</h2></div><span className="pill">no upload</span></div>
          {videoUrl ? <video className="previewVideo" src={videoUrl} controls preload="metadata" /> : <div className="emptyState">Load a bundle containing `rough-cut.mp4`, or add the preview manually.</div>}
          {audioUrl && <div className="audioInspect"><p className="label">MUSIC WAVEFORM</p><Waveform url={audioUrl} /></div>}
        </article>

        <article className="card energyCard" id="director">
          <div className="sectionHeading"><div><p className="label">DIRECTOR</p><h2>Energy curve</h2></div><span className="pill">viewer-state target</span></div>
          {bundle.director ? <>
            <div className="energyChart" aria-label="Director energy curve">{bundle.director.energyCurve.map((value, index) => <div className="energySlot" key={`${index}-${value}`}><div className="energyBar" style={{ height: `${Math.max(2, value * 100)}%` }} /></div>)}</div>
            <div className="directorSections">{bundle.director.sections.map((section) => <span className="pill" key={`${section.role}-${section.startNormalized}`}>{section.role}</span>)}</div>
          </> : <div className="emptyState">Load `director-plan.json`.</div>}
        </article>

        <article className="card timelineCard" id="timeline">
          <div className="sectionHeading"><div><p className="label">EDITORIAL PLAN</p><h2>Timeline reasoning</h2></div><span className="pill">{bundle.edit?.segments.length ?? 0} decisions</span></div>
          {bundle.edit ? <div className="timeline">{bundle.edit.segments.map((segment, index) => {
            const asset = assetById.get(segment.assetId);
            const transition = bundle.ctl?.transitions[index];
            return <div className={`timelineClip role-${segment.role}`} key={segment.id}>
              <div className="clipTop"><strong>{asset?.filename ?? segment.assetId}</strong><span>{segment.role}</span></div>
              <div className="clipTimes">source {segment.sourceInSeconds.toFixed(2)} → {segment.sourceOutSeconds.toFixed(2)}s</div>
              <p>{segment.reason}</p>
              <div className="clipSignals"><span>energy {segment.shotEnergy.toFixed(2)} / {segment.targetEnergy.toFixed(2)}</span><span>confidence {Math.round(segment.confidence * 100)}%</span></div>
              {transition && <div className="transitionReason">→ {transition.mechanism}: {transition.reason}</div>}
            </div>;
          })}</div> : <div className="emptyState">Load `edit-plan.json` and optionally `ctl.json`.</div>}
        </article>

        <article className="card timelineCard" id="transitions">
          <div className="sectionHeading"><div><p className="label">TRANSITION SYNTHESIS</p><h2>Boundary opportunities</h2></div><span className="pill">{bundle.transitionOpportunities?.boundaries.length ?? 0} boundaries</span></div>
          {bundle.transitionOpportunities ? <div className="timeline">{bundle.transitionOpportunities.boundaries.map((boundary) => <div className="timelineClip" key={boundary.boundaryIndex}>
            <div className="clipTop"><strong>Boundary {boundary.boundaryIndex}</strong><span>{metricLabel(boundary.recommendedMechanism)}</span></div>
            <div className="clipTimes">handles out {boundary.outgoingHandleSeconds.toFixed(3)}s · in {boundary.incomingHandleSeconds.toFixed(3)}s</div>
            <div className="clipSignals"><span>relation {boundary.cutSignature.relationScore.toFixed(2)}</span><span>phase {boundary.cutSignature.phaseCompatibility.toFixed(2)}</span><span>direction {boundary.cutSignature.directionCompatibility.toFixed(2)}</span></div>
            <div className="findingList">{boundary.candidates.map((candidate) => <div className={`finding finding-${candidate.feasible ? "info" : "warning"}`} key={candidate.mechanism}>
              <strong>{candidate.feasible ? "✓" : "×"} {metricLabel(candidate.mechanism)}</strong>
              <span>{candidate.reason}</span>
              <small>motivation {candidate.motivationScore.toFixed(2)} · feasibility {candidate.feasibilityScore.toFixed(2)} · needs {candidate.requiredHandleSeconds.toFixed(2)}s handles</small>
            </div>)}</div>
          </div>)}</div> : <div className="emptyState">Load `transition-opportunities.json` to inspect candidate feasibility before any non-zero bridge is compiled.</div>}
        </article>

        <article className="card timelineCard" id="compute">
          <div className="sectionHeading"><div><p className="label">ADVANCED ANALYSIS</p><h2>Compute budget & execution</h2></div><span className="pill">{bundle.advancedAnalysis?.requests.length ?? 0} requested · {bundle.advancedResults?.boundaries.length ?? 0} executed</span></div>
          {bundle.advancedAnalysis ? <>
            {bundle.advancedAnalysis.requests.length > 0 ? <div className="timeline">{bundle.advancedAnalysis.requests.map((request) => {
              const execution = bundle.advancedResults?.boundaries.find((item) => item.boundaryIndex === request.boundaryIndex);
              return <div className="timelineClip" key={request.boundaryIndex}>
                <div className="clipTop"><strong>Boundary {request.boundaryIndex}</strong><span>priority {Math.round(request.priority * 100)}%</span></div>
                <p className="label">PLAN</p>
                <div className="directorSections">{request.requestedFeatures.map((feature) => <span className="pill" key={feature}>{metricLabel(feature)}</span>)}</div>
                <div className="clipTimes">LEFT · {request.leftWindow.assetId} / {request.leftWindow.shotId} · {request.leftWindow.sourceStartSeconds.toFixed(3)} → {request.leftWindow.sourceEndSeconds.toFixed(3)}s</div>
                <div className="clipTimes">RIGHT · {request.rightWindow.assetId} / {request.rightWindow.shotId} · {request.rightWindow.sourceStartSeconds.toFixed(3)} → {request.rightWindow.sourceEndSeconds.toFixed(3)}s</div>
                <p>{request.reason}</p>
                <div className="clipSignals"><span>evidence · {formatDecision(request.evidence)}</span></div>
                <p className="label">EXECUTION</p>
                {execution ? <>
                  <div className="findingList">{execution.features.map((feature) => <div className={`finding finding-${feature.status === "completed" ? "info" : "warning"}`} key={feature.feature}>
                    <strong>{feature.status === "completed" ? "✓" : "×"} {metricLabel(feature.feature)} · {metricLabel(feature.status)}</strong>
                    <span>{feature.reason}</span>
                    <small>{feature.backend}{Object.keys(feature.metrics).length > 0 ? ` · ${formatDecision(feature.metrics)}` : ""}</small>
                  </div>)}</div>
                  {execution.leftFlow && execution.rightFlow && <div className="clipSignals">
                    <span>left samples {execution.leftFlow.sampleCount} · mean {execution.leftFlow.meanMagnitude.toFixed(3)} · coherence {execution.leftFlow.directionalCoherence.toFixed(2)}</span>
                    <span>right samples {execution.rightFlow.sampleCount} · mean {execution.rightFlow.meanMagnitude.toFixed(3)} · coherence {execution.rightFlow.directionalCoherence.toFixed(2)}</span>
                    {execution.flowDirectionCompatibility != null && <span>flow direction match {execution.flowDirectionCompatibility.toFixed(2)}</span>}
                  </div>}
                </> : <div className="emptyState">Requested but not executed yet. Run `monter-analysis-execute`; Studio will not infer completion from the plan alone.</div>}
              </div>;
            })}</div> : <div className="emptyState">Cheap VIR/CutSignature evidence was sufficient for every current boundary; no expensive pass was budgeted.</div>}
            {bundle.advancedAnalysis.skippedBoundaries.length > 0 && <div className="findingList">{bundle.advancedAnalysis.skippedBoundaries.map((skipped) => <div className="finding finding-info" key={`${skipped.boundaryIndex}-${skipped.reason}`}><strong>Boundary {skipped.boundaryIndex} · skipped</strong><span>{skipped.reason}</span></div>)}</div>}
          </> : <div className="emptyState">Load `advanced-analysis-plan.json` to see where MONTER budgets compute. `advanced-analysis-results.json` is separate proof of what actually ran.</div>}
        </article>

        <article className="card timelineCard" id="corrections">
          <div className="sectionHeading"><div><p className="label">HUMAN FEEDBACK</p><h2>Correction ledger</h2></div><span className="pill">{bundle.corrections?.corrections.length ?? 0} overrides</span></div>
          {bundle.corrections ? <div className="timeline">{bundle.corrections.corrections.map((correction) => <div className="timelineClip" key={correction.id}>
            <div className="clipTop"><strong>{metricLabel(correction.kind)}</strong><span>{correction.targetType}{correction.targetRef ? ` ${correction.targetRef}` : ""}</span></div>
            <div className="clipTimes">AI · {formatDecision(correction.aiDecision)}</div>
            <div className="transitionReason">HUMAN · {formatDecision(correction.humanDecision)}</div>
            <p>{correction.reason}</p>
            {Object.keys(correction.context).length > 0 && <div className="clipSignals"><span>context · {formatDecision(correction.context)}</span></div>}
            <small>{correction.source} · {correction.createdAt}</small>
          </div>)}</div> : <div className="emptyState">No `human-corrections.json` loaded. Corrections remain supervised evidence only.</div>}
        </article>

        <article className="card assetsCard" id="reviews">
          <div className="sectionHeading"><div><p className="label">DECISION REVIEW</p><h2>Acceptance denominator</h2></div><span className="pill">{bundle.reviewSummary?.reviewed ?? bundle.reviews?.reviews.length ?? 0} reviewed</span></div>
          {bundle.reviewSummary ? <>
            <section className="statsGrid" aria-label="Decision review rates">
              <article className="statCard"><p className="label">REVIEWED</p><strong className="statValue">{bundle.reviewSummary.reviewed}</strong><span className="statNote">human-inspected decisions</span></article>
              <article className="statCard"><p className="label">ACCEPTED</p><strong className="statValue">{bundle.reviewSummary.accepted}</strong><span className="statNote">AI kept as-is</span></article>
              <article className="statCard"><p className="label">CORRECTED</p><strong className="statValue">{bundle.reviewSummary.corrected}</strong><span className="statNote">linked human overrides</span></article>
              <article className="statCard"><p className="label">ACCEPTANCE</p><strong className="statValue">{formatRate(bundle.reviewSummary.acceptanceRate)}</strong><span className="statNote">reviewed denominator</span></article>
            </section>
            {Object.keys(bundle.reviewSummary.byTransitionMechanism).length > 0 && <div className="assetTable"><p className="label">BY TRANSITION MECHANISM</p>{Object.entries(bundle.reviewSummary.byTransitionMechanism).map(([label, bucket]) => <ReviewBucketRow key={label} label={label} bucket={bucket} />)}</div>}
            {Object.keys(bundle.reviewSummary.byDirectorRole).length > 0 && <div className="assetTable"><p className="label">BY DIRECTOR ROLE</p>{Object.entries(bundle.reviewSummary.byDirectorRole).map(([label, bucket]) => <ReviewBucketRow key={label} label={label} bucket={bucket} />)}</div>}
            <div className="findingList">{bundle.reviewSummary.notes.map((note) => <div className="finding finding-info" key={note}><span>{note}</span></div>)}</div>
          </> : <div className="emptyState">Load `decision-review-summary.json`. Correction-only history is not used as an acceptance denominator.</div>}
        </article>

        <article className="card criticCard" id="critic">
          <div className="sectionHeading"><div><p className="label">CRITIC</p><h2>Quality dimensions</h2></div><span className={`statusBadge status-${bundle.critic?.status ?? "empty"}`}>{bundle.critic?.status ?? "not loaded"}</span></div>
          {bundle.critic ? <>
            <div className="metricGrid">{bundle.critic.metrics.map((metric) => <div className="metric" key={metric.name}><span>{metricLabel(metric.name)}</span><strong>{Number(metric.value.toFixed(3))}</strong><small>{metric.passed ? "pass" : `target ${metric.target}`}</small></div>)}</div>
            <div className="findingList">{bundle.critic.findings.map((finding, index) => <div className={`finding finding-${finding.severity}`} key={`${finding.code}-${index}`}><strong>{finding.code}</strong><span>{finding.message}</span></div>)}</div>
          </> : <div className="emptyState">Load `critic-report.json`.</div>}
        </article>

        <article className="card assetsCard">
          <div className="sectionHeading"><div><p className="label">SOURCE INDEX</p><h2>Assets</h2></div><span className="pill">portable paths only</span></div>
          {bundle.project ? <div className="assetTable">{bundle.project.assets.map((asset) => <div className="assetRow" key={asset.id}><div><strong>{asset.filename}</strong><span>{asset.sourceRelPath}</span></div><span>{asset.width ?? "?"}×{asset.height ?? "?"} · {asset.fps ?? "?"}fps</span><span>{asset.codec ?? "unknown"}</span><span>{formatBytes(asset.sourceSizeBytes)}</span></div>)}</div> : <div className="emptyState">Load `project.monter.json`.</div>}
        </article>
      </section>
    </main>
  </div>;
}
