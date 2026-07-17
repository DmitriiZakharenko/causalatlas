import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { GraphEdge, GraphNode, GraphResponse } from "../api/types";

type Section = {
  title: string;
  summary: string;
  bullets: string[];
};

type FocusStory = {
  node: GraphNode;
  incoming: GraphEdge[];
  outgoing: GraphEdge[];
  score: number;
};

function normalizeLabel(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function formatNode(node: GraphNode): string {
  return node.label || node.id;
}

function edgeSentence(edge: GraphEdge): string {
  const relation = edge.relation ?? "relates to";
  return `${edge.source} ${relation} ${edge.target}`;
}

function nodeTypeRank(type: string | null): number {
  switch (type) {
    case "Cytokine":
      return 4;
    case "Molecule":
      return 3;
    case "Cell":
      return 2;
    case "Clinical_phenotype":
      return 1;
    default:
      return 2;
  }
}

function chooseFocus(graph: GraphResponse, requestedNodeId?: string | null): FocusStory | null {
  if (graph.elements.nodes.length === 0) return null;

  const byId = new Map(graph.elements.nodes.map((node) => [node.id, node]));
  if (requestedNodeId) {
    const requested = byId.get(requestedNodeId);
    if (requested) {
      return {
        node: requested,
        incoming: graph.elements.edges.filter((edge) => edge.target === requested.id),
        outgoing: graph.elements.edges.filter((edge) => edge.source === requested.id),
        score: Number.POSITIVE_INFINITY,
      };
    }
  }
  let best: FocusStory | null = null;

  for (const node of graph.elements.nodes) {
    const incoming = graph.elements.edges.filter((edge) => edge.target === node.id);
    const outgoing = graph.elements.edges.filter((edge) => edge.source === node.id);
    const incident = incoming.length + outgoing.length;
    const support = incoming.reduce((sum, edge) => sum + edge.pmid_count, 0) + outgoing.reduce((sum, edge) => sum + edge.pmid_count, 0);
    const bidirectionalBonus = incoming.length > 0 && outgoing.length > 0 ? 500 : 0;
    const typeBonus = nodeTypeRank(node.type) * 25;
    const noisePenalty = node.looks_like_noise ? -1500 : 0;
    const normalized = normalizeLabel(formatNode(node));
    const compactnessBonus = normalized.length <= 12 ? 25 : normalized.length <= 20 ? 10 : 0;
    const score = incident * 100 + support * 12 + bidirectionalBonus + typeBonus + compactnessBonus + noisePenalty;

    if (
      !best ||
      score > best.score ||
      (score === best.score && node.pmid_count > best.node.pmid_count) ||
      (score === best.score && node.pmid_count === best.node.pmid_count && formatNode(node).length < formatNode(best.node).length)
    ) {
      best = { node: byId.get(node.id) ?? node, incoming, outgoing, score };
    }
  }

  return best;
}

function buildSections(graph: GraphResponse, requestedNodeId?: string | null): { focus: FocusStory | null; sections: Section[] } {
  const focus = chooseFocus(graph, requestedNodeId);
  if (!focus) {
    return {
      focus: null,
      sections: [
        {
          title: "Core story",
          summary: "The graph is too sparse to identify a clear mechanistic hub.",
          bullets: ["No non-noise nodes were available for a causal readout."],
        },
      ],
    };
  }

  const upstream = focus.incoming;
  const downstream = focus.outgoing;
  const upstreamTop = upstream
    .slice()
    .sort((a, b) => b.pmid_count - a.pmid_count || (b.confidence ?? 0) - (a.confidence ?? 0))
    .slice(0, 3);
  const downstreamTop = downstream
    .slice()
    .sort((a, b) => b.pmid_count - a.pmid_count || (b.confidence ?? 0) - (a.confidence ?? 0))
    .slice(0, 4);

  const upstreamSources = [...new Set(upstream.map((edge) => edge.source))].slice(0, 3);
  const downstreamTargets = [...new Set(downstream.map((edge) => edge.target))].slice(0, 3);
  const focusLabel = formatNode(focus.node);
  const upstreamText = upstreamSources.length > 0 ? upstreamSources.join(", ") : "other upstream nodes";
  const downstreamText = downstreamTargets.length > 0 ? downstreamTargets.join(", ") : "downstream effect nodes";

  const interpretation = [
    upstream.length > 0 ? `${focusLabel} receives input from ${upstreamText}.` : null,
    downstream.length > 0 ? `${focusLabel} connects onward to ${downstreamText}.` : null,
    upstream.length > 0 && downstream.length > 0
      ? `${focusLabel} looks like a bridge between upstream signaling and downstream tissue remodeling rather than an isolated endpoint.`
      : null,
  ].filter(Boolean) as string[];

  const motifBullets: string[] = [];
  if (
    upstream.some((edge) => /TGF/i.test(edge.source)) &&
    downstream.some((edge) => /myofibroblast|collagen|ecm|matrix/i.test(edge.target))
  ) {
    motifBullets.push("The graph supports a profibrotic loop: upstream TGF-family input converges on the focus node, then points toward myofibroblast or matrix programs.");
  }
  if (downstream.some((edge) => /ERK|MEK|STAT|SMAD/i.test(edge.target))) {
    motifBullets.push("Signaling outputs include kinase/transcriptional pathways, which makes the mechanism read like a control node rather than a single terminal effect.");
  }
  if (downstream.some((edge) => /collagen|fibronectin|ecm|matrix/i.test(edge.target))) {
    motifBullets.push("There is direct support for extracellular matrix output, which is the part that matters clinically for scar formation.");
  }
  if (motifBullets.length === 0 && upstream.length + downstream.length > 0) {
    motifBullets.push("The graph is connected enough to tell a causal story, but it does not expose a named canonical motif in a single line.");
  }

  return {
    focus,
    sections: [
      {
        title: requestedNodeId ? "Selected node" : "Central node",
        summary: requestedNodeId
          ? `${focusLabel} was selected by the user and has ${upstream.length} incoming and ${downstream.length} outgoing edges in this graph.`
          : `${focusLabel} is the graph's main hub here, with ${upstream.length} incoming and ${downstream.length} outgoing edges.`,
        bullets: [
          upstreamTop.length > 0 ? `Strongest upstream edge: ${upstreamTop[0] ? edgeSentence(upstreamTop[0]) : "—"}` : "No direct upstream edge was found for the hub.",
          downstreamTop.length > 0 ? `Strongest downstream edge: ${downstreamTop[0] ? edgeSentence(downstreamTop[0]) : "—"}` : "No direct downstream edge was found for the hub.",
          `Node type: ${focus.node.type ?? "unknown"} · ${focus.node.pmid_count} supporting PMIDs`,
        ],
      },
      {
        title: "Plain-language story",
        summary: `This graph says how ${focusLabel} sits between upstream signals and downstream biological effects.`,
        bullets: interpretation.length > 0 ? interpretation : ["The visible graph does not provide enough links to narrate a causal story."],
      },
      {
        title: "What this means for disease",
        summary: "The most relevant mechanism-level takeaways from the visible edges.",
        bullets: motifBullets,
      },
    ],
  };
}

export default function DiseasePathogenesisPage() {
  const { diseaseSlug } = useParams<{ diseaseSlug: string }>();
  const [searchParams] = useSearchParams();
  const requestedNodeId = searchParams.get("node");
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!diseaseSlug) return;
    api
      .getGraph(diseaseSlug)
      .then((response) => {
        setGraph(response);
        setError(null);
      })
      .catch((err) => setError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  }, [diseaseSlug]);

  const story = useMemo(() => {
    if (!graph) return { focus: null as FocusStory | null, sections: [] as Section[] };
    return buildSections(graph, requestedNodeId);
  }, [graph, requestedNodeId]);

  const focusLabel = story.focus ? formatNode(story.focus.node) : null;
  const supportingEdges = useMemo(() => {
    if (!story.focus) return [];
    return [...story.focus.incoming, ...story.focus.outgoing].sort(
      (a, b) => b.pmid_count - a.pmid_count || (b.confidence ?? 0) - (a.confidence ?? 0),
    );
  }, [story.focus]);

  if (!diseaseSlug) {
    return <p className="error-text">Missing disease slug in URL.</p>;
  }

  return (
    <div className="page page--wide">
      <section className="card">
        <div className="run-header">
          <div>
            <h1>Pathogenesis summary</h1>
            <p className="muted">
              Disease graph: <code>{diseaseSlug}</code>
              {requestedNodeId && <> · selected node: <code>{requestedNodeId}</code></>}
            </p>
          </div>
          <Link className="button" to="/graphs">
            Back to graph
          </Link>
        </div>
        {error && <p className="error-text">{error}</p>}
        {!error && !graph && <p className="muted">Loading graph…</p>}
        {graph && focusLabel && (
          <p className="muted">
            This page turns the selected node into a short explanation of how <strong>{focusLabel}</strong> sits
            inside the disease mechanism. It is text-first, so the causal story is visible without reading every
            edge by hand.
          </p>
        )}
      </section>

      <div className="graph-layout">
        <section className="card">
          <h2>Core story</h2>
          {story.sections.map((section) => (
            <article key={section.title} style={{ marginBottom: "1.5rem" }}>
              <h3>{section.title}</h3>
              <p className="muted">{section.summary}</p>
              <ul className="connections-list">
                {section.bullets.map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            </article>
          ))}
        </section>

        <section className="card">
          <h2>Supporting edges</h2>
          {story.focus && (
            <>
              <p className="muted">
                Focus node: <strong>{focusLabel}</strong> · {story.focus.node.type ?? "unknown"} · {story.focus.node.pmid_count} PMIDs
              </p>
              <ul className="connections-list">
                {supportingEdges.slice(0, 12).map((edge) => (
                  <li key={`${edge.source}-${edge.target}-${edge.relation ?? "related"}`}>
                    <strong>{edge.source}</strong> → <strong>{edge.target}</strong>
                    <div className="muted">
                      {edge.relation ?? "related"} · {edge.pmid_count} PMID{edge.pmid_count === 1 ? "" : "s"}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          {!story.focus && <p className="muted">No hub could be identified from the current graph.</p>}
        </section>
      </div>
    </div>
  );
}
