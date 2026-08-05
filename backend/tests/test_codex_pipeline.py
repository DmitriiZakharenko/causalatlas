from __future__ import annotations

import asyncio
import json
import sys

from app.llm_common import AgentResult


def _agent_result(agent_name: str, payload: dict | list) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        result_text=json.dumps(payload),
        structured_output=payload if isinstance(payload, dict) else None,
        cost_usd=0.0,
        duration_ms=0,
        raw={},
    )


def test_codex_orchestrator_stream_delegates_to_pipeline(monkeypatch):
    import app.codex_cli as codex_cli

    async def _fake_pipeline(*args, **kwargs):
        yield {"type": "result", "is_error": False, "result": "ok", "total_cost_usd": 0.0, "duration_ms": 0}

    import app.codex_pipeline as pipeline

    monkeypatch.setattr(pipeline, "run_orchestrator_stream", _fake_pipeline)

    async def _collect():
        out = []
        async for event in codex_cli.run_orchestrator_stream("prompt"):
            out.append(event)
        return out

    events = asyncio.run(_collect())
    assert events == [{"type": "result", "is_error": False, "result": "ok", "total_cost_usd": 0.0, "duration_ms": 0}]


def test_graph_builder_accepts_codex_edges_without_optional_metadata():
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from build_graph import build_graph

    graph = build_graph(
        [{"source": "GSDMD", "target": "pyroptosis", "relation": "induces", "pmid": "1", "confidence": 0.8}]
    )

    assert graph["edges"][0]["years"] == [""]
    assert graph["edges"][0]["species"] == ["unknown"]
    assert graph["nodes"][0]["type"] == "unknown"


def test_drug_gene_evidence_states_keep_statistics_separate_from_literature(tmp_path):
    from app.codex_pipeline import PipelineContext, _build_drug_gene_evidence_states
    from app.target_models import AnalysisTarget, StatisticalCandidate

    target = AnalysisTarget(
        disease="NSCLC",
        genes=["EGFR"],
        drugs=["erlotinib"],
        statistical_candidates=[StatisticalCandidate(
            drug="erlotinib", gene="EGFR", method="colocalization", effect=0.31,
            p_value=0.001, source="study-x", source_id="assoc-1",
        )],
    )
    ctx = PipelineContext("run-1", "NSCLC", "EGFR", "let_it_rip", tmp_path, tmp_path, target, "graph_only")
    states = _build_drug_gene_evidence_states(ctx, [{
        "drug": "erlotinib",
        "predicate": "binds_target",
        "object": "EGFR protein",
        "edge": {"claim_id": "claim-1"},
    }])
    pair = states[0]
    assert pair["candidate_statistical"]["status"] == "supported"
    assert pair["literature_direct"]["status"] == "supported"
    assert pair["indirect_chain"]["status"] == "not_found"
    assert pair["no_literature_support"]["status"] == "not_applicable"


def test_drug_inhibitor_language_is_direct_and_pathway_language_is_indirect(tmp_path):
    from app.codex_pipeline import PipelineContext, _materialize_local_drug_knowledge
    from app.target_models import AnalysisTarget

    target = AnalysisTarget(disease="melanoma", genes=["BRAF"], drugs=["vemurafenib"])
    ctx = PipelineContext("run-1", "melanoma", "BRAF", "let_it_rip", tmp_path, tmp_path, target, "graph_only")
    payload = _materialize_local_drug_knowledge(ctx, [{
        "pmid": "1", "year": "2025", "species": "human",
        "abstract": "Vemurafenib is a selective BRAF inhibitor. Vemurafenib resistance activates the MAPK pathway.",
    }])
    predicates = {(claim["predicate"], claim["mechanism_class"]) for claim in payload["claims"]}
    assert ("binds_target", "direct_target") in predicates
    assert ("indirectly_modulates", "indirect_pathway") in predicates


def test_codex_pipeline_emits_streamtranslator_compatible_events(tmp_path, monkeypatch):
    import app.codex_pipeline as pipeline
    import app.codex_cli as codex_cli

    from app.orchestrator import StreamTranslator

    root = tmp_path
    monkeypatch.setattr(pipeline, "ROOT", root)
    monkeypatch.setattr(pipeline, "_skills_for", lambda *args, **kwargs: [])
    monkeypatch.setattr(pipeline, "_materialize_local_publications", lambda ctx: {"publications": []})
    monkeypatch.setattr(pipeline, "_materialize_local_verification", lambda ctx: {"publications": []})
    monkeypatch.setattr(pipeline, "_materialize_local_mechanisms", lambda ctx: {"edges": []})
    monkeypatch.setattr(
        pipeline,
        "_step_skills_event",
        lambda ctx, agent_name, tool_id: {
            "agent01_baseline_canonical_knowledge": {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "id": tool_id, "name": "Skill", "input": {"skill": "canonical-baseline-lookup"}}
                    ]
                },
            },
            "agent02_literature_retrieval": {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "id": tool_id, "name": "Skill", "input": {"skill": "pubmed-literature-search"}}
                    ]
                },
            },
            "agent06_graph_builder": {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "id": tool_id, "name": "Skill", "input": {"skill": "graph-export-visualization"}}
                    ]
                },
            },
            "agent10_novelty_verification": {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "id": tool_id, "name": "Skill", "input": {"skill": "novelty-verification-protocol"}}
                    ]
                },
            },
        }.get(agent_name)
    )
    monkeypatch.setattr(
        pipeline,
        "_candidate_manifest",
        lambda ctx: [
            {
                "hypothesis_id": "G001",
                "original_statement": "IL11 feedback gap in idiopathic pulmonary fibrosis",
                "kind": "gap",
                "source": {"missing_edge": "IL11 -> fibroblast"},
            }
        ],
    )

    async def _fake_run_agent(agent_name: str, prompt: str, **kwargs):
        if agent_name == "agent01_baseline_canonical_knowledge":
            payload = {"canonical_entries": [{"nodes": ["IL11", "Fibroblast"]}]}
        elif agent_name == "agent02_literature_retrieval":
            payload = {
                "run_id": "ipf_test",
                "disease": "idiopathic pulmonary fibrosis",
                "publications": [
                    {
                        "pmid": "1",
                        "title": "IL11 drives fibrosis",
                        "abstract": "IL11 activates fibroblasts.",
                        "year": "2024",
                        "journal": "J Test",
                        "publication_type": "Original Research",
                        "species": "human",
                    }
                ],
            }
        elif agent_name == "agent03_publication_verification":
            payload = {
                "verification_report": {
                    "session": "ipf_test",
                    "agent": "agent03_publication_verification",
                    "verified_count": 1,
                    "rejected_count": 0,
                },
                "publications": [
                    {
                        "pmid": "1",
                        "title": "IL11 drives fibrosis",
                        "abstract": "IL11 activates fibroblasts.",
                        "year": "2024",
                        "journal": "J Test",
                        "publication_type": "Original Research",
                        "species": "human",
                    }
                ],
            }
        elif agent_name == "agent04_quality_filter":
            payload = {"publication_counts": {"high": 1}, "average_relevance": 0.9}
        elif agent_name == "agent05_mechanistic_extraction":
            payload = {
                "edges": [
                    {
                        "source": "IL11",
                        "target": "Fibroblast",
                        "relation": "activates",
                        "pmid": "1",
                        "year": "2024",
                        "species": "human",
                        "confidence": 0.9,
                        "source_type": "molecule",
                        "target_type": "cell",
                    }
                ]
            }
        elif agent_name == "agent10_novelty_verification":
            payload = {
                "hypothesis_id": "G001",
                "eligible_for_hypothesis_generation": True,
                "class": "D",
                "source_gap": "IL11 -> fibroblast",
                "specific_prediction": "Blocking IL11 should reduce fibroblast activation.",
            }
        elif agent_name == "agent11_hypothesis_generation":
            payload = {
                "hypothesis_id": "G001",
                "class": "D",
                "source_gap": "IL11 -> fibroblast",
                "specific_prediction": "Blocking IL11 should reduce fibroblast activation.",
                "recombines_edges": ["IL11 -> Fibroblast"],
                "why_connecting_edge_not_published": "No direct edge was found in the limited corpus.",
                "falsification": "Neutralize IL11 and observe no change in fibroblast state.",
            }
        elif agent_name == "agent12_peer_review":
            payload = {
                "hypothesis_id": "G001",
                "reviewer_searches": [],
                "votes": ["accept", "accept", "accept"],
                "consensus": "ACCEPT",
            }
        elif agent_name == "agent13_experiment_design":
            payload = {
                "hypothesis_id": "G001",
                "model_system": "mouse",
                "experiments": [{"name": "IL11 blockade", "readout": "fibrosis score"}],
                "negative_controls": [{"name": "isotype control"}],
                "primary_readout": "fibrosis score",
            }
        else:
            payload = {"result": agent_name}
        return _agent_result(agent_name, payload)

    monkeypatch.setattr(pipeline.codex_cli, "run_agent", _fake_run_agent)

    run_id = "ipf_test"
    session_dir = root / "data" / "sessions" / run_id
    prompt = "\n".join(
        [
            f"run_id: {run_id}",
            "disease: idiopathic pulmonary fibrosis",
            "gene: IL11",
            "autonomy_level: let_it_rip",
            f"session output directory (absolute): {session_dir}",
        ]
    )

    async def _collect():
        out = []
        async for event in codex_cli.run_orchestrator_stream(prompt):
            out.append(event)
        return out

    raw_events = asyncio.run(_collect())
    assert raw_events[-1]["type"] == "result", raw_events[-3:]
    ui_events = []
    translator = StreamTranslator()
    for raw in raw_events:
        ui_events.extend(translator.feed(raw))

    event_types = [event["type"] for event in ui_events]
    assert "skill_loaded" in event_types
    assert "agent_started" in event_types
    assert "agent_completed" in event_types
    assert "run_completed" in event_types

    assert (session_dir / "publications_verified.json").exists()
    assert (root / "data" / "graphs" / "idiopathic_pulmonary_fibrosis" / "knowledge_graph.json").exists()
    assert (root / "data" / "graphs" / "idiopathic_pulmonary_fibrosis" / "novelty_audit.json").exists()


def test_codex_pipeline_preserves_agent_written_outputs(tmp_path, monkeypatch):
    import app.codex_pipeline as pipeline

    ctx = pipeline.PipelineContext(
        run_id="run-1",
        disease="idiopathic pulmonary fibrosis",
        gene="IL11",
        autonomy_level="let_it_rip",
        session_dir=tmp_path / "session",
        graph_dir=tmp_path / "graph",
    )
    ctx.session_dir.mkdir(parents=True)
    ctx.graph_dir.mkdir(parents=True)

    rich_publications = {"session": "run-1", "publications": [{"pmid": "1", "title": "kept"}]}
    (ctx.session_dir / "publications_raw.json").write_text(json.dumps(rich_publications))
    (ctx.session_dir / "verification_report.json").write_text(json.dumps({"accepted": 1}))
    (ctx.session_dir / "publications_verified.json").write_text(json.dumps({"session": "run-1", "publications": [{"pmid": "1"}]}))

    wrapper = {"result_text": "{\"type\":\"turn.completed\"}"}

    pipeline._persist_agent_output(ctx, "agent02_literature_retrieval", wrapper)
    pipeline._persist_agent_output(ctx, "agent03_publication_verification", wrapper)

    assert json.loads((ctx.session_dir / "publications_raw.json").read_text()) == rich_publications
    assert json.loads((ctx.session_dir / "publications_verified.json").read_text()) == {
        "session": "run-1",
        "publications": [{"pmid": "1"}],
    }


def test_codex_pipeline_materializes_compact_agent05_inputs(tmp_path, monkeypatch):
    import app.codex_pipeline as pipeline

    root = tmp_path
    monkeypatch.setattr(pipeline, "ROOT", root)

    ctx = pipeline.PipelineContext(
        run_id="run-compact",
        disease="idiopathic pulmonary fibrosis",
        gene="IL11",
        autonomy_level="let_it_rip",
        session_dir=root / "data" / "sessions" / "run-compact",
        graph_dir=root / "data" / "graphs" / "idiopathic_pulmonary_fibrosis",
    )
    ctx.session_dir.mkdir(parents=True)
    ctx.graph_dir.mkdir(parents=True)

    publications = []
    for idx in range(20):
        publication = {
            "pmid": str(1000 + idx),
            "title": f"Paper {idx}",
            "abstract": f"Abstract {idx} with IL11 and fibrosis evidence.",
            "year": 2026 - idx % 3,
            "journal": "J Test",
            "publication_type": "Journal Article",
            "species": "human",
            "verified": True,
            "relevance_score": round(1.0 - idx * 0.03, 2),
            "quality": {"evidence_level": "primary_research", "confidence_score": round(0.99 - idx * 0.01, 2)},
            "query_strategies_matched": [f"S{idx:02d}"],
        }
        publications.append(publication)
    (ctx.session_dir / "publications_verified.json").write_text(
        json.dumps({"session": ctx.run_id, "publications": publications})
    )
    (ctx.session_dir / "quality_scores.json").write_text(
        json.dumps({"session": ctx.run_id, "agent": "agent04_quality_filter", "publication_counts": {"primary_research": 20}, "average_relevance": 0.73})
    )
    (ctx.session_dir / "canonical_baseline.json").write_text(json.dumps({"session": ctx.run_id, "canonical_entries": []}))

    compact_publications_path, compact_quality_path = pipeline._materialize_agent05_compact_inputs(ctx, limit=5)
    compact_publications = json.loads(compact_publications_path.read_text())
    compact_quality = json.loads(compact_quality_path.read_text())

    assert len(compact_publications["publications"]) == 5
    assert compact_publications["publications"][0]["pmid"] == "1000"
    assert compact_quality["compact_publication_count"] == 15
    assert compact_quality["top_pmids"][0] == "1000"

    prompt = pipeline._prepare_prompt(ctx, "agent05_mechanistic_extraction")
    assert "publications_verified_compact.json" in prompt
    assert "quality_scores_compact.json" in prompt
    assert str(ctx.session_dir / "publications_verified.json") not in prompt
    assert str(ctx.session_dir / "quality_scores.json") not in prompt

    quality_prompt = pipeline._prepare_prompt(ctx, "agent04_quality_filter")
    assert "publications_verified_compact.json" in quality_prompt
    assert str(ctx.session_dir / "publications_verified.json") not in quality_prompt


def test_codex_pipeline_curates_multiple_ipf_il11_hypotheses(tmp_path, monkeypatch):
    import app.codex_pipeline as pipeline

    root = tmp_path
    monkeypatch.setattr(pipeline, "ROOT", root)

    ctx = pipeline.PipelineContext(
        run_id="ipf-1",
        disease="idiopathic pulmonary fibrosis",
        gene="IL11",
        autonomy_level="let_it_rip",
        session_dir=root / "data" / "sessions" / "ipf-1",
        graph_dir=root / "data" / "graphs" / "idiopathic_pulmonary_fibrosis",
    )
    ctx.session_dir.mkdir(parents=True)
    ctx.graph_dir.mkdir(parents=True)
    (ctx.graph_dir / "knowledge_graph.json").write_text(
        json.dumps(
            {
                "nodes": [],
                "edges": [
                    {
                        "source": "TGFβ signaling",
                        "target": "IL-11",
                        "primary_relation": "activates",
                        "pmid_count": 1,
                        "pmids": ["1"],
                    },
                    {
                        "source": "IL-11",
                        "target": "Myofibroblast",
                        "primary_relation": "differentiates",
                        "pmid_count": 2,
                        "pmids": ["2", "3"],
                    },
                    {
                        "source": "IL-11",
                        "target": "ERK1/2 phosphorylation",
                        "primary_relation": "activates",
                        "pmid_count": 1,
                        "pmids": ["4"],
                    },
                    {
                        "source": "IL-11",
                        "target": "Collagen I expression",
                        "primary_relation": "activates",
                        "pmid_count": 1,
                        "pmids": ["5"],
                    },
                    {
                        "source": "Smad2",
                        "target": "IL-11",
                        "primary_relation": "activates",
                        "pmid_count": 1,
                        "pmids": ["6"],
                    },
                ],
            }
        )
    )

    candidates = pipeline._curated_ipf_il11_candidates(ctx)
    audits = pipeline._template_audits_from_candidates(candidates)

    assert len(candidates) == 3
    assert len(audits) == 3
    assert all(a["eligible_for_hypothesis_generation"] for a in audits)

    hypothesis = pipeline._synthesize_hypothesis_candidate(ctx, candidates[0], 1)
    assert hypothesis["hypothesis_id"] == "H001"
    assert hypothesis["provisional"] is False
    assert hypothesis["supporting_pmids"] == ["1", "2", "3"]


def test_codex_pipeline_compacts_agent12_peer_review_input():
    import app.codex_pipeline as pipeline

    hypothesis = {
        "hypothesis_id": "H001",
        "class": "D",
        "statement": "Test statement",
        "specific_prediction": "A very long prediction " + ("x" * 2000),
        "falsification": "A very long falsification " + ("y" * 2000),
        "source_candidate": {
            "hypothesis_id": "C001",
            "kind": "gap",
            "original_statement": "Original statement " + ("z" * 1000),
        },
        "supporting_pmids": [str(i) for i in range(20)],
        "supporting_edges": [
            {"source": "IL11", "relation": "activates", "target": "Fibroblast", "pmid": "1", "confidence": 0.9}
            for _ in range(10)
        ],
        "recombined_edges": [f"edge-{i}" for i in range(10)],
        "why_connecting_edge_not_published": "not published " + ("w" * 1500),
        "notes": "notes " + ("n" * 1500),
    }
    contradictions = [
        {
            "id": f"X{i}",
            "node_pair": ["IL11", "Fibroblast"],
            "direction": "forward",
            "summary": "summary " + ("s" * 1000),
            "pmids": [str(i), str(i + 1), str(i + 2)],
        }
        for i in range(10)
    ]

    payload = pipeline._compact_peer_review_payload(hypothesis, contradictions, 1)

    assert payload["hypothesis_id"] == "H001"
    assert len(payload["supporting_pmids"]) == 8
    assert len(payload["supporting_edges"]) == 5
    assert len(payload["recombined_edges"]) == 5
    assert len(payload["contradictions"]) == 5
    assert len(json.dumps(payload)) < 8000
