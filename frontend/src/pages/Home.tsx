import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";

/**
 * Phase 0 proof-of-wiring page: calls the real backend health endpoint on
 * mount, and lets the user fire the hardcoded /api/pipeline/run stub, so we
 * can visually confirm frontend <-> backend wiring before any real agent
 * logic exists (Phase 2).
 */
export default function Home() {
  const [health, setHealth] = useState<unknown>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [stubResult, setStubResult] = useState<unknown>(null);
  const [stubError, setStubError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((err: ApiError) => setHealthError(`${err.status}: ${err.message}`));
  }, []);

  const runStub = async () => {
    setLoading(true);
    setStubError(null);
    try {
      const result = await api.runPipelineStub({ disease: "asthma", autonomy_level: "let_it_rip" });
      setStubResult(result);
    } catch (err) {
      setStubError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 760, margin: "2rem auto", fontFamily: "system-ui, sans-serif", padding: "0 1rem" }}>
      <h1>LoopFinder — Phase 0 scaffold</h1>
      <p style={{ color: "#666" }}>
        This page proves the frontend talks to the real FastAPI backend. Nothing below is
        fabricated client-side — every value comes from an actual HTTP response.
      </p>

      <section style={{ marginTop: "2rem" }}>
        <h2>Backend health</h2>
        {healthError && <pre style={{ color: "crimson" }}>{healthError}</pre>}
        {!healthError && !health && <p>Loading…</p>}
        {health !== null && <pre>{JSON.stringify(health, null, 2)}</pre>}
      </section>

      <section style={{ marginTop: "2rem" }}>
        <h2>Pipeline run (Phase 0 stub)</h2>
        <p style={{ color: "#666" }}>
          Real orchestration lands in Phase 2 — this button currently hits a hardcoded stub
          endpoint, clearly labeled as such in the response.
        </p>
        <button onClick={runStub} disabled={loading}>
          {loading ? "Calling backend…" : "POST /api/pipeline/run"}
        </button>
        {stubError && <pre style={{ color: "crimson" }}>{stubError}</pre>}
        {stubResult !== null && <pre>{JSON.stringify(stubResult, null, 2)}</pre>}
      </section>
    </div>
  );
}
