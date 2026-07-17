import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { EvidenceSummary } from "../api/types";
import { fallbackDemoSteps } from "../demoData";

export default function DemoReplayPage() {
  const [summary, setSummary] = useState<EvidenceSummary | null>(null);
  const [playing, setPlaying] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const stepCount = summary?.replay_steps?.length ?? fallbackDemoSteps.length;

  useEffect(() => { api.getDemoReplay().then(setSummary).catch((err) => setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err))); }, []);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setStep((current) => current >= stepCount - 1 ? (setPlaying(false), current) : current + 1), 2600);
    return () => window.clearInterval(timer);
  }, [playing, stepCount]);

  const steps = summary?.replay_steps ?? fallbackDemoSteps;
  const active = steps[Math.min(step, steps.length - 1)];

  return <div className="page page--wide demo-page">
    <section className="demo-hero card"><div><p className="eyebrow">Recorded run / presentation mode</p><h1>IPF + IL11: evidence to experiment</h1><p className="muted">This replay reads persisted artifacts from a completed run. It never calls Codex, PubMed or the live pipeline.</p></div><span className="demo-badge">RECORDED · READ ONLY</span></section>
    {error && <p className="muted">Standalone replay loaded. Connect the backend to display persisted run metrics.</p>}
    {summary && <section className="demo-summary"><div><span>Pipeline</span><strong>completed</strong></div><div><span>Evidence</span><strong>{summary.evidence.quality}</strong></div><div><span>Verified papers</span><strong>{summary.evidence.verified_papers}</strong></div><div><span>Hypotheses ready</span><strong>{summary.hypotheses.ready ? "yes" : "no"}</strong></div></section>}
    <section className="card demo-replay-card"><div className="section-heading"><div><p className="eyebrow">Guided replay / real artifacts</p><h2>{active.number} · {active.title}</h2></div><button className="button button--primary" onClick={() => setPlaying((value) => !value)}>{playing ? "Pause replay" : "Play replay"}</button></div><p className="demo-replay-card__description">{active.description}</p><div className="demo-result-grid">{active.metrics.map((metric) => <div key={metric}><span>Observed result</span><strong>{metric}</strong></div>)}</div><p className="demo-artifact"><b>Source artifact:</b> <code>{active.artifact}</code></p><input aria-label="Demo replay position" type="range" min="0" max={steps.length - 1} value={step} onChange={(event) => { setStep(Number(event.target.value)); setPlaying(false); }} /><div className="demo-timeline">{steps.map((item, index) => <button key={item.number} className={index === step ? "is-active" : index < step ? "is-passed" : ""} onClick={() => { setStep(index); setPlaying(false); }}><span>{item.number}</span><small>{item.title}</small><em>{item.metrics[0]}</em></button>)}</div></section>
    <section className="card demo-cta"><div><h2>Want to run live?</h2><p className="muted">Use Launch &amp; Runs for an explicit live Codex analysis. The replay above is isolated from network, auth and token limits.</p></div><a className="button button--primary" href="/">Run live analysis</a></section>
  </div>;
}
