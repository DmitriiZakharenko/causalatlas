"""Evidence and hypothesis summaries derived from persisted pipeline artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SESSIONS_DIR = REPO_ROOT / "data" / "sessions"
GRAPHS_DIR = REPO_ROOT / "data" / "graphs"
SEARCH_BUDGETS = {
    "agent02_literature_retrieval": {"max_queries": 6, "max_publications": 100, "deadline_s": 240},
    "agent10_novelty_verification": {"max_queries": 8, "max_publications": 40, "deadline_s": 180},
    "agent12_peer_review": {"max_queries": 6, "max_publications": 30, "deadline_s": 180},
}


def _read(path: Path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _session_dir(run_id: str) -> Path:
    return SESSIONS_DIR / run_id


def _graph_dir_for_run(run: dict) -> Path:
    disease_dir = GRAPHS_DIR / _slug(run["disease"])
    versioned = disease_dir / run["run_id"]
    return versioned if versioned.exists() else disease_dir


def _transcript_text(value: object) -> str:
    """Flatten nested Codex JSONL output and remove repeated JSON escaping."""
    text = str(value or "")
    for _ in range(3):
        unescaped = text.replace('\\"', '"').replace("\\\\", "\\")
        if unescaped == text:
            break
        text = unescaped
    return text


def _normalize_audit(audit: dict, fallback_statement: str | None = None) -> dict:
    if any(key in audit for key in ("classification", "novelty_class", "eligible_for_hypothesis_generation")):
        return audit
    text = _transcript_text(audit.get("result_text", ""))
    def find(pattern: str, default=None):
        match = re.findall(pattern, text)
        return match[-1] if match else default
    classification = find(r"classification['\"]?\s*:\s*['\"]?\s*(A|B|C|D|E|RESTATED)")
    eligible = find(r"eligible_for_hypothesis_generation['\"]?\s*:\s*['\"]?(true|false)")
    statement = find(r"original_statement['\"]?\s*:\s*['\"]([^'\"]{1,500})")
    hypothesis_id = find(r"hypothesis_id['\"]?\s*:\s*['\"]([^'\"]+)" )
    action = find(r"action['\"]?\s*:\s*['\"]([^'\"]{1,700})")
    generic_statement = not statement or (fallback_statement and statement.strip().lower() == fallback_statement.strip().lower())
    inferred_candidate = find(r"as a previously published ([^,;]{1,300}mechanism)")
    if generic_statement and inferred_candidate:
        statement = f"Candidate mechanism: {inferred_candidate}"
    elif generic_statement and fallback_statement:
        statement = f"No concrete mechanistic hypothesis supplied. Candidate label: {fallback_statement}"
    statement = statement or None
    return {
        "hypothesis_id": hypothesis_id,
        "classification": classification,
        "novelty_class": classification,
        "eligible_for_hypothesis_generation": eligible == "true" if eligible is not None else False,
        "original_statement": statement,
        "action": action or (
            "Fallback placeholder: no concrete causal chain was supplied; this is not a substantive hypothesis."
            if fallback_statement else "No concrete candidate statement was persisted."
        ),
    }


def _class_code(value) -> str:
    raw = str(value or "").upper()
    if "RESTATED" in raw:
        return "RESTATED"
    match = re.search(r"\b([A-E])\b", raw)
    return match.group(1) if match else "UNKNOWN"


def _extract_hypothesis_records(payload: dict) -> list[dict]:
    records = []
    for item in payload.get("hypotheses", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        if "result_text" not in item:
            records.append(item)
            continue
        text = _transcript_text(item.get("result_text"))
        def find(field: str, limit: int = 1200):
            matches = re.findall(rf"{field}['\"]?\s*:\s*['\"]([^'\"]{{1,{limit}}})", text)
            return matches[-1] if matches else None
        hypothesis_ids = re.findall(r"id['\"]?\s*:\s*['\"](H[-A-Za-z0-9_]+)", text)
        record = {
            "id": (hypothesis_ids or re.findall(r"hypothesis_id['\"]?\s*:\s*['\"]([^'\"]+)", text) or [None])[-1],
            "class": find("class"),
            "source_gap": find("source_gap"),
            "specific_prediction": find("specific_prediction"),
            "falsification": find("falsification"),
        }
        if any(record.values()):
            records.append(record)
    return records


def _extract_experiment_records(payload: dict) -> list[dict]:
    records = []
    for item in payload.get("experiments", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        if "result_text" not in item:
            records.append(item)
            continue
        text = _transcript_text(item.get("result_text"))
        def find(field: str, limit: int = 1800):
            matches = re.findall(rf"{field}['\"]?\s*:\s*['\"]([^'\"]{{1,{limit}}})", text)
            return matches[-1] if matches else None
        ids = re.findall(r"id['\"]?\s*:\s*['\"](E[-A-Za-z0-9_]+)", text)
        methods = re.findall(r"method['\"]?\s*:\s*['\"]([^'\"]{1,1800})", text)
        outcomes = re.findall(r"predicted_outcome['\"]?\s*:\s*['\"]([^'\"]{1,1800})", text)
        falsifications = re.findall(r"falsification_criterion['\"]?\s*:\s*['\"]([^'\"]{1,1800})", text)
        for index, experiment_id in enumerate(ids):
            record = {
                "id": experiment_id,
                "method": methods[index] if index < len(methods) else None,
                "predicted_outcome": outcomes[index] if index < len(outcomes) else None,
                "falsification_criterion": falsifications[index] if index < len(falsifications) else None,
            }
            records.append(record)
    return records


def _novelty_catalog() -> list[dict]:
    catalog = []
    for path in GRAPHS_DIR.rglob("novelty_audit.json"):
        data = _read(path, {})
        audits = data.get("audits", []) if isinstance(data, dict) else []
        manifest = _read(path.parent / "novelty_candidate_manifest.json", {})
        manifest_candidates = manifest.get("candidates", []) if isinstance(manifest, dict) else []
        for index, audit in enumerate(audits):
            manifest_item = manifest_candidates[index] if index < len(manifest_candidates) and isinstance(manifest_candidates[index], dict) else {}
            normalized = _normalize_audit(audit, manifest_item.get("original_statement")) if isinstance(audit, dict) else {}
            code = _class_code(normalized.get("classification", normalized.get("novelty_class")))
            if code == "UNKNOWN":
                continue
            catalog.append({"source": str(path.relative_to(REPO_ROOT)), "hypothesis_id": normalized.get("hypothesis_id") or f"candidate-{index + 1}", "classification": code, "eligible": bool(normalized.get("eligible_for_hypothesis_generation")), "statement": normalized.get("original_statement")})
    return catalog


def summarize_run(run: dict, include_catalog: bool = True) -> dict:
    run_id = run["run_id"]
    session = _session_dir(run_id)
    raw = _read(session / "publications_raw.json", {})
    verified_payload = _read(session / "publications_verified.json", {})
    verification = _read(session / "verification_report.json", {})
    graph_dir = _graph_dir_for_run(run)
    novelty = _read(graph_dir / "novelty_audit.json", {})
    # Disease graph directories are shared across runs. Never expose a prior
    # run's novelty result while the current run has not produced its own audit.
    if isinstance(novelty, dict) and novelty.get("session") not in {None, run_id}:
        novelty = {}
    hypotheses_payload = _read(session / "hypotheses.json", {})
    experiment_payload = _read(session / "experiment_design.json", {})
    reviews_payload = _read(session / "peer_review.json", {})
    graph = _read(graph_dir / "knowledge_graph.json", {})

    publications = raw.get("publications", []) if isinstance(raw, dict) else []
    verified = verified_payload.get("publications", []) if isinstance(verified_payload, dict) else []
    verification_record = verification.get("verification_report", verification) if isinstance(verification, dict) else {}
    if not isinstance(verification_record, dict):
        verification_record = {}
    rejected = verification_record.get("rejected", verification_record.get("rejected_count", 0))
    reported_verified = verification_record.get(
        "verified_count",
        verification_record.get("accepted", verification_record.get("verified", len(verified))),
    )
    try:
        reported_verified = int(reported_verified)
    except (TypeError, ValueError):
        reported_verified = len(verified)
    verification_count_discrepancy = reported_verified != len(verified)
    queries = raw.get("queries", []) if isinstance(raw, dict) else []
    chains = [
        {"strategy": q.get("strategy", "unknown"), "query": q.get("query", ""), "papers": q.get("retrieved", 0)}
        for q in queries if isinstance(q, dict)
    ]
    audits = novelty.get("audits", []) if isinstance(novelty, dict) else []
    manifest = _read(graph_dir / "novelty_candidate_manifest.json", {})
    manifest_candidates = manifest.get("candidates", []) if isinstance(manifest, dict) else []
    audit_views = [
        _normalize_audit(
            audit,
            manifest_candidates[index].get("original_statement")
            if index < len(manifest_candidates) and isinstance(manifest_candidates[index], dict)
            else None,
        )
        for index, audit in enumerate(audits)
        if isinstance(audit, dict)
    ]
    hypotheses = hypotheses_payload.get("hypotheses", []) if isinstance(hypotheses_payload, dict) else []
    hypothesis_records = _extract_hypothesis_records(hypotheses_payload)
    experiment_records = _extract_experiment_records(experiment_payload)
    reviews = reviews_payload.get("reviews", []) if isinstance(reviews_payload, dict) else []
    accepted_reviews = [r for r in reviews if str(r.get("consensus", "")).upper() not in {"REJECT", "REJECTED"}]
    fallback_files = []
    for path in session.glob("*.json"):
        try:
            if "fallback" in path.read_text().lower():
                fallback_files.append(path.name)
        except OSError:
            continue

    evidence_degraded = bool(fallback_files) or verification_count_discrepancy or (bool(publications) and not verified) or not bool(queries)
    hypothesis_ready = bool(accepted_reviews) and not evidence_degraded
    return {
        "run_id": run_id,
        "execution": {
            "status": run.get("status"),
            "complete": run.get("status") == "completed",
            "current_agent": run.get("current_agent"),
            "error": run.get("error"),
        },
        "evidence": {
            "quality": "degraded" if evidence_degraded else "usable",
            "verified_papers": reported_verified,
            "corpus_papers": len(verified),
            "rejected_papers": int(rejected or 0),
            "verification_count_discrepancy": verification_count_discrepancy,
            "independent_sources": len({p.get("journal") for p in verified if p.get("journal")}),
            "papers_per_mechanism_chain": chains,
            "fallback_count": len(fallback_files),
            "fallback_files": fallback_files,
            "contradictions": len(graph.get("contradictions", [])) if isinstance(graph, dict) else 0,
        },
        "hypotheses": {
            "novelty_candidates": len(audit_views),
            "d_e_candidates": sum(1 for a in audit_views if str(a.get("classification", a.get("novelty_class", ""))).upper() in {"D", "E"}),
            "generated": len(hypotheses),
            "accepted": len(accepted_reviews),
            "ready": hypothesis_ready,
        },
        "hypothesis_records": hypothesis_records,
        "experiment_design": {
            "status": experiment_payload.get("status") if isinstance(experiment_payload, dict) else None,
            "hypothesis_id": (experiment_payload.get("hypothesis_id") if isinstance(experiment_payload, dict) else None) or (hypothesis_records[0].get("id") if hypothesis_records else None),
            "model_system": experiment_payload.get("model_system") if isinstance(experiment_payload, dict) else None,
            "experiments": experiment_records,
            "primary_readout": experiment_payload.get("primary_readout") if isinstance(experiment_payload, dict) else None,
            "negative_controls": experiment_payload.get("negative_controls", []) if isinstance(experiment_payload, dict) else [],
        },
        "budgets": SEARCH_BUDGETS,
        "checkpoints": sorted(path.name for path in (session / "checkpoints").glob("*.json")) if (session / "checkpoints").exists() else [],
        "novelty_audits": [{"hypothesis_id": a.get("hypothesis_id"), "classification": a.get("classification", a.get("novelty_class")), "eligible": bool(a.get("eligible_for_hypothesis_generation")), "statement": a.get("original_statement"), "action": a.get("action")} for a in audit_views],
        "novelty_catalog": _novelty_catalog() if include_catalog else [],
        "artifacts": sorted(path.name for path in session.glob("*.json")),
    }


def _slug(value: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "target"


def demo_summary() -> dict:
    run_id = "idiopathic_pulmonary_fibrosis_20260705T215344Z"
    run = {"run_id": run_id, "disease": "idiopathic pulmonary fibrosis", "gene": "IL11", "status": "completed", "current_agent": "agent13_experiment_design", "error": None}
    summary = summarize_run(run)
    session = _session_dir(run_id)
    graph_dir = GRAPHS_DIR / _slug(run["disease"])
    raw = _read(session / "publications_raw.json", {})
    verified = _read(session / "publications_verified.json", {})
    verification = _read(session / "verification_report.json", {})
    mechanisms = _read(session / "mechanisms_extracted.json", {})
    graph = _read(graph_dir / "knowledge_graph.json", {})
    loops = _read(graph_dir / "loops.json", {})
    metrics = _read(graph_dir / "network_metrics.json", {})
    contradictions = _read(graph_dir / "contradictions.json", {})
    gaps = _read(graph_dir / "knowledge_gaps.json", {})
    novelty = _read(graph_dir / "novelty_audit.json", {})
    hypotheses = _read(session / "hypotheses.json", {})
    reviews = _read(session / "peer_review.json", {})
    experiments = _read(session / "experiment_design.json", {})
    def count_items(payload, key: str) -> int:
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            value = payload.get(key, [])
            return len(value) if isinstance(value, list) else 0
        return 0
    architectures = metrics.get("architectures", []) if isinstance(metrics, dict) else []
    summary["replay_steps"] = [
        {"number": "00", "title": "Orchestrator", "description": "Sequenced the run and persisted each hand-off.", "metrics": ["13 agents scheduled", "let_it_rip", "terminal: completed"], "artifact": "run_events + session directory"},
        {"number": "01", "title": "Canonical baseline", "description": "Loaded the established biological context before literature retrieval.", "metrics": [f"{len((_read(session / 'canonical_baseline.json', {}) or {}).get('entries', []))} canonical entries", "4 database sources", "fallback-aware"], "artifact": "canonical_baseline.json"},
        {"number": "02", "title": "Literature retrieval", "description": "Searched mechanism-specific IPF + IL11 chains across year bands.", "metrics": [f"{len(raw.get('queries', []))} query strategies", f"{raw.get('total_unique_publications', len(raw.get('publications', [])))} unique papers", f"{len(raw.get('year_band_distribution', {}))} year bands"], "artifact": "publications_raw.json"},
        {"number": "03", "title": "Publication verification", "description": "Checked publication identity and metadata before downstream extraction.", "metrics": [f"{len(verified.get('publications', []))} verified", f"{verification.get('rejected', 0)} rejected", f"{verification.get('total_input', 0)} input"], "artifact": "verification_report.json"},
        {"number": "04", "title": "Quality filter", "description": "Ranked the evidence and preserved translational uncertainty.", "metrics": [f"{len((verified.get('publications', [])))} papers scored", f"{len((_read(session / 'quality_scores.json', {}) or {}).get('publication_counts', {}))} evidence levels", "species/model flags"], "artifact": "quality_scores.json"},
        {"number": "05", "title": "Mechanistic extraction", "description": "Converted explicit paper findings into directed causal statements.", "metrics": [f"{mechanisms.get('total_edges', len(mechanisms.get('edges', [])))} extracted edges", f"{len(mechanisms.get('edges', []))} provenance records", "direction preserved"], "artifact": "mechanisms_extracted.json"},
        {"number": "06–09", "title": "Graph stages", "description": "Built the graph, discovered loops, ranked topology and checked contradictions.", "metrics": [f"{graph.get('metadata', {}).get('node_count', len(graph.get('nodes', [])))} nodes", f"{graph.get('metadata', {}).get('edge_count', len(graph.get('edges', [])))} edges", f"{count_items(loops, 'loops')} loops", f"{count_items(contradictions, 'contradictions')} contradictions"], "artifact": "knowledge_graph.json + graph reports"},
        {"number": "10", "title": "Novelty verification", "description": "Applied the independent A–E novelty gate to candidate mechanisms.", "metrics": [f"{len(novelty.get('audits', []))} candidates audited", f"{summary['hypotheses']['d_e_candidates']} D/E candidates", "independent search required"], "artifact": "novelty_audit.json"},
        {"number": "11–12", "title": "Hypothesis + peer review", "description": "Generated candidate hypotheses and attempted to falsify them.", "metrics": [f"{len(hypotheses.get('hypotheses', []))} hypotheses", f"{len(reviews.get('reviews', []))} reviews", f"{summary['hypotheses']['accepted']} accepted"], "artifact": "hypotheses.json + peer_review.json"},
        {"number": "13", "title": "Experiment design", "description": "Translated surviving candidates into validation plans.", "metrics": [f"{len(experiments.get('experiments', []))} experiment designs", "controls + readouts", "falsification criteria"], "artifact": "experiment_design.json"},
    ]
    summary["demo"] = {"recorded": True, "source": "persisted session artifacts", "live": False}
    return summary
