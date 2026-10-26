"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import type { ArtifactBundle } from "@/lib/artifacts";
import { mergeArtifacts } from "@/lib/artifacts";
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

export function StudioClient() {
  const [bundle, setBundle] = useState<ArtifactBundle>({});
  const [errors, setErrors] = useState<string[]>([]);
  const [videoUrl, setVideoUrl] = useState<string>();
  const [audioUrl, setAudioUrl] = useState<string>();

  useEffect(() => () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
  }, [videoUrl, audioUrl]);

  const assetById = useMemo(() => new Map(bundle.project?.assets.map((asset) => [asset.id, asset]) ?? []), [bundle.project]);
  const loadedCount = Object.values(bundle).filter(Boolean).length;

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    let next = bundle;
    const nextErrors: string[] = [];

    for (const file of files) {
      try {
        if (file.type.startsWith("video/")) {
          if (videoUrl) URL.revokeObjectURL(videoUrl);
          setVideoUrl(URL.createObjectURL(file));
          continue;
        }
        if (file.type.startsWith("audio/")) {
          if (audioUrl) URL.revokeObjectURL(audioUrl);
          setAudioUrl(URL.createObjectURL(file));
          continue;
        }
        if (!file.name.endsWith(".json")) continue;
        next = mergeArtifacts(next, file.name, JSON.parse(await file.text()));
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
        <a className="navItem" href="#critic">Critic</a>
      </nav>
      <div className="sidebarFooter"><span className="tinyLabel">PRIVACY</span><strong>Local files stay local</strong><p>JSON, video and audio are read through browser File APIs; this Studio does not upload them.</p></div>
    </aside>

    <main className="main" id="project">
      <header className="topbar">
        <div><p className="eyebrow">LOCAL ARTIFACT INSPECTOR</p><h1>{projectName}</h1><p className="subtitle">Load `.monter` JSON artifacts plus an optional rough-cut and music file.</p></div>
        <label className="importButton">Load artifacts<input type="file" multiple accept="application/json,video/*,audio/*" onChange={handleFiles} /></label>
      </header>

      {errors.length > 0 && <div className="errorBox">{errors.map((error) => <div key={error}>{error}</div>)}</div>}

      <section className="statsGrid" aria-label="Project metrics">
        <article className="card statCard"><p className="label">RAW FOOTAGE</p><strong className="statValue">{formatBytes(bundle.project?.sourceBytes)}</strong><span className="statNote">never uploaded</span></article>
        <article className="card statCard"><p className="label">PROXIES</p><strong className="statValue">{formatBytes(bundle.project?.proxyBytes)}</strong><span className="statNote">local bridge</span></article>
        <article className="card statCard"><p className="label">SHOTS</p><strong className="statValue">{bundle.vir?.shots.length ?? "—"}</strong><span className="statNote">VIR analysis</span></article>
        <article className="card statCard"><p className="label">CUT</p><strong className="statValue">{duration != null ? `${duration.toFixed(2)}s` : "—"}</strong><span className="statNote">{loadedCount} artifact types loaded</span></article>
      </section>

      <section className="contentGrid">
        <article className="card previewCard" id="preview">
          <div className="sectionHeading"><div><p className="label">LOCAL PREVIEW</p><h2>Rough cut</h2></div><span className="pill">no upload</span></div>
          {videoUrl ? <video className="previewVideo" src={videoUrl} controls preload="metadata" /> : <div className="emptyState">Add `rough-cut.mp4` with the Load artifacts button.</div>}
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
