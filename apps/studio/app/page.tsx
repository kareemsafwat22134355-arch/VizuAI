import { sampleProject } from "@/lib/sample-project";

const pipelineSteps = [
  ["ffprobe ingest", "pass"],
  ["proxy generation", "ready"],
  ["shot intelligence", "next"],
  ["motion pass", "next"],
  ["audio map", "next"],
  ["director plan", "prototype"],
] as const;

function formatBytes(bytes: number) {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)} MB`;
  return `${Math.round(bytes / 1_000)} KB`;
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="card statCard">
      <p className="label">{label}</p>
      <strong className="statValue">{value}</strong>
      <span className="statNote">{note}</span>
    </article>
  );
}

export default function Home() {
  const project = sampleProject;
  const assetById = new Map(project.assets.map((asset) => [asset.id, asset]));

  return (
    <div className="shell">
      <aside className="sidebar">
        <div><div className="brand">MONTER</div><div className="brandSub">cinematic intelligence</div></div>
        <nav className="nav" aria-label="Primary navigation">
          <span className="navItem navActive">Project</span><span className="navItem">Assets</span><span className="navItem">Director</span><span className="navItem">Timeline</span><span className="navItem">Critic</span>
        </nav>
        <div className="sidebarFooter"><span className="tinyLabel">ARCHITECTURE</span><strong>Local RAW + Web Studio</strong><p>Heavy media stays on the editor machine.</p></div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><p className="eyebrow">PROJECT / {project.schemaVersion}</p><h1>{project.projectName}</h1><p className="subtitle">Raw stays local. Decisions become portable.</p></div>
          <div className="bridgeStatus"><span className="statusDot" /> Bridge contract ready</div>
        </header>

        <section className="statsGrid" aria-label="Project metrics">
          <Stat label="RAW FOOTAGE" value={formatBytes(project.sourceBytes)} note="never uploaded" />
          <Stat label="ANALYSIS PROXIES" value={formatBytes(project.proxyBytes)} note="portable working set" />
          <Stat label="INDEXED ASSETS" value={String(project.assets.length)} note="source-linked" />
          <Stat label="TARGET CUT" value={`${project.director.targetDurationSeconds}s`} note="director intent" />
        </section>

        <section className="contentGrid">
          <article className="card energyCard">
            <div className="sectionHeading"><div><p className="label">DIRECTOR</p><h2>Energy curve</h2></div><span className="pill">viewer-state target</span></div>
            <div className="energyChart" aria-label="Director energy curve">
              {project.director.energyCurve.map((value, index) => <div className="energySlot" key={`${index}-${value}`}><div className="energyBar" style={{ height: `${value}%` }} title={`Energy ${value}`} /></div>)}
            </div>
            <div className="curveLabels"><span>restraint</span><span>build</span><span>rupture</span><span>payoff</span></div>
          </article>

          <article className="card pipelineCard">
            <div className="sectionHeading"><div><p className="label">ENGINE</p><h2>Pipeline</h2></div></div>
            <div className="pipelineList">{pipelineSteps.map(([name, state]) => <div className="pipelineRow" key={name}><span>{name}</span><span className={`pipelineState state-${state}`}>{state}</span></div>)}</div>
          </article>

          <article className="card timelineCard">
            <div className="sectionHeading"><div><p className="label">EDITORIAL PLAN</p><h2>Rough cut reasoning</h2></div><span className="pill">{project.editPlan.length} decisions</span></div>
            <div className="timeline">
              {project.editPlan.map((segment) => {
                const asset = assetById.get(segment.assetId);
                return <div className={`timelineClip role-${segment.role}`} key={segment.id}>
                  <div className="clipTop"><strong>{asset?.filename ?? segment.assetId}</strong><span>{segment.role}</span></div>
                  <div className="clipTimes">{segment.sourceInSeconds.toFixed(2)} → {segment.sourceOutSeconds.toFixed(2)}s</div>
                  <p>{segment.reason}</p><div className="confidence">confidence {Math.round(segment.confidence * 100)}%</div>
                </div>;
              })}
            </div>
          </article>

          <article className="card assetsCard">
            <div className="sectionHeading"><div><p className="label">SOURCE INDEX</p><h2>Assets</h2></div><span className="pill">8GB-first analysis</span></div>
            <div className="assetTable">
              <div className="assetHeader"><span>FILE</span><span>TECHNICAL</span><span>MOTION</span><span>SIZE</span></div>
              {project.assets.map((asset) => <div className="assetRow" key={asset.id}>
                <div><strong>{asset.filename}</strong><span>{asset.durationSeconds.toFixed(1)} seconds</span></div>
                <span>{asset.width}×{asset.height} · {asset.fps}fps · {asset.codec}</span>
                <span className={`motion motion-${asset.motionLevel}`}>{asset.motionLevel}</span><span>{formatBytes(asset.sourceSizeBytes)}</span>
              </div>)}
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}
