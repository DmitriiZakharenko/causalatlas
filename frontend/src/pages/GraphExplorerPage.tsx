import { useEffect, useMemo, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import type * as cytoscape from "cytoscape";
import { api, ApiError } from "../api/client";
import type { GraphEdge, GraphNode, GraphResponse, GraphSummary } from "../api/types";

const TYPE_COLORS: Record<string, string> = {
  Cell: "#5b8def",
  Cytokine: "#ef8354",
  Molecule: "#8ac926",
  Tissue: "#bd93f9",
  Clinical_phenotype: "#e63946",
};
const DEFAULT_COLOR = "#8892a6";
const SPOTLIGHT_COLOR = "#ffd166";
const SEARCH_COLOR = "#2ecc71";

// Cytoscape core supports "mapData(prop, min, max, out_min, out_max)" as a
// string-encoded mapper -- used here instead of JS function style values so
// the stylesheet stays plain, serializable data that types cleanly against
// @types/cytoscape's `Css.Node`/`Css.Edge` (which model function values only
// for a handful of properties, not arbitrary ones).
const STYLESHEET: cytoscape.StylesheetJsonBlock[] = [
  {
    selector: "node",
    style: {
      "background-color": "data(color)",
      label: "data(label)",
      "font-size": 8,
      "min-zoomed-font-size": 7,
      color: "#e6e8ee",
      "text-outline-width": 1.2,
      "text-outline-color": "#1a1d29",
      "text-margin-y": -2,
      width: "mapData(pmid_count, 0, 150, 9, 42)",
      height: "mapData(pmid_count, 0, 150, 9, 42)",
      "border-width": 0,
      "transition-property": "opacity, border-width, border-color",
      "transition-duration": 120,
    },
  },
  {
    selector: "edge",
    style: {
      width: "mapData(pmid_count, 0, 50, 0.6, 5)",
      "line-color": "#3a3f55",
      "target-arrow-color": "#3a3f55",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.7,
      "curve-style": "bezier",
      opacity: 0.55,
      "transition-property": "opacity, line-color, width",
      "transition-duration": 120,
    },
  },
  // Applied to everything NOT part of the current focus set once something
  // is selected -- this is what actually makes a dense graph legible: instead
  // of trying to lay out 838 nodes so every label is readable at once, we
  // lean on selection to collapse attention down to one node's neighborhood.
  {
    selector: ".faded",
    style: { opacity: 0.06, "text-opacity": 0 },
  },
  {
    selector: ".spotlight-node",
    style: {
      "border-width": 3,
      "border-color": SPOTLIGHT_COLOR,
      "font-size": 11,
      "z-index": 999,
    },
  },
  {
    selector: ".spotlight-neighbor",
    style: { "font-size": 9, "z-index": 998 },
  },
  {
    selector: ".spotlight-edge",
    style: {
      "line-color": SPOTLIGHT_COLOR,
      "target-arrow-color": SPOTLIGHT_COLOR,
      opacity: 1,
      width: 2.5,
      "z-index": 997,
    },
  },
  {
    selector: ".search-match",
    style: { "border-width": 2.5, "border-color": SEARCH_COLOR },
  },
];

type SelectedElement = { kind: "node"; data: GraphNode } | { kind: "edge"; data: GraphEdge } | null;

interface Connection {
  edge: GraphEdge;
  otherNode: GraphNode;
  direction: "out" | "in";
}

export default function GraphExplorerPage() {
  const [graphs, setGraphs] = useState<GraphSummary[] | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [hideNoise, setHideNoise] = useState(true);
  const [selected, setSelected] = useState<SelectedElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    api
      .listGraphs()
      .then((r) => {
        setGraphs(r.graphs);
        if (r.graphs.length > 0) setSelectedSlug(r.graphs[0].disease_slug);
      })
      .catch((err) => setLoadError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  }, []);

  useEffect(() => {
    if (!selectedSlug) return;
    setGraph(null);
    setSelected(null);
    api
      .getGraph(selectedSlug)
      .then(setGraph)
      .catch((err) => setLoadError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  }, [selectedSlug]);

  const nodeById = useMemo(() => {
    const map = new Map<string, GraphNode>();
    graph?.elements.nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [graph]);

  const { visibleNodes, visibleEdges, hiddenNoiseCount } = useMemo(() => {
    if (!graph) return { visibleNodes: [] as GraphNode[], visibleEdges: [] as GraphEdge[], hiddenNoiseCount: 0 };
    const nodes = hideNoise ? graph.elements.nodes.filter((n) => !n.looks_like_noise) : graph.elements.nodes;
    const keptIds = new Set(nodes.map((n) => n.id));
    const edges = graph.elements.edges.filter((e) => keptIds.has(e.source) && keptIds.has(e.target));
    return {
      visibleNodes: nodes,
      visibleEdges: edges,
      hiddenNoiseCount: graph.elements.nodes.length - nodes.length,
    };
  }, [graph, hideNoise]);

  const elements = useMemo(() => {
    return [
      ...visibleNodes.map((n) => ({ data: { ...n, color: TYPE_COLORS[n.type ?? ""] ?? DEFAULT_COLOR } })),
      ...visibleEdges.map((e) => ({ data: { ...e } })),
    ];
  }, [visibleNodes, visibleEdges]);

  // Selection -> cytoscape classes. Deliberately separate from the tap
  // handlers below so clicking a connection in the side panel (which just
  // calls setSelected) re-triggers the same spotlight as clicking the node
  // directly on the canvas.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("faded spotlight-node spotlight-neighbor spotlight-edge");
    if (!selected) return;

    if (selected.kind === "node") {
      const el = cy.getElementById(selected.data.id);
      if (el.empty()) return;
      const neighborhood = el.closedNeighborhood();
      cy.elements().difference(neighborhood).addClass("faded");
      el.addClass("spotlight-node");
      el.connectedEdges().addClass("spotlight-edge");
      el.neighborhood("node").addClass("spotlight-neighbor");
    } else {
      const el = cy.getElementById(selected.data.id);
      if (el.empty()) return;
      const neighborhood = el.connectedNodes().union(el);
      cy.elements().difference(neighborhood).addClass("faded");
      el.addClass("spotlight-edge");
      el.connectedNodes().addClass("spotlight-node");
    }
  }, [selected]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass("search-match");
    if (!search.trim()) return;
    const term = search.trim().toLowerCase();
    cy.nodes().forEach((n) => {
      if ((n.data("label") as string)?.toLowerCase().includes(term)) {
        n.addClass("search-match");
      }
    });
  }, [search, elements]);

  const connections: Connection[] = useMemo(() => {
    if (!graph || selected?.kind !== "node") return [];
    const id = selected.data.id;
    const result: Connection[] = [];
    for (const e of visibleEdges) {
      if (e.source === id) {
        const other = nodeById.get(e.target);
        if (other) result.push({ edge: e, otherNode: other, direction: "out" });
      } else if (e.target === id) {
        const other = nodeById.get(e.source);
        if (other) result.push({ edge: e, otherNode: other, direction: "in" });
      }
    }
    return result.sort((a, b) => b.edge.pmid_count - a.edge.pmid_count);
  }, [graph, selected, visibleEdges, nodeById]);

  const selectNode = (node: GraphNode) => setSelected({ kind: "node", data: node });

  return (
    <div className="page page--wide">
      <section className="card">
        <div className="graph-toolbar">
          <label>
            Disease
            <select value={selectedSlug ?? ""} onChange={(e) => setSelectedSlug(e.target.value)}>
              {graphs?.map((g) => (
                <option key={g.disease_slug} value={g.disease_slug}>
                  {g.disease} ({g.node_count} nodes / {g.edge_count} edges)
                </option>
              ))}
            </select>
          </label>
          <label>
            Find node
            <input
              type="text"
              placeholder="e.g. IL-33"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <label className="form__radio" style={{ alignSelf: "flex-end", marginBottom: 2 }}>
            <input type="checkbox" checked={hideNoise} onChange={(e) => setHideNoise(e.target.checked)} />
            <span>Hide likely-noise nodes (heuristic filter)</span>
          </label>
          {graph && (
            <span className="muted">
              {graph.metadata.updated ? `Updated ${String(graph.metadata.updated).slice(0, 10)}` : null}
              {graph.metadata.version ? ` · v${graph.metadata.version}` : null}
            </span>
          )}
        </div>
        {hideNoise && hiddenNoiseCount > 0 && (
          <p className="muted" style={{ marginTop: "0.5rem" }}>
            Hiding {hiddenNoiseCount} of {graph?.elements.nodes.length} nodes flagged by a heuristic as likely
            sentence-fragment extraction artifacts (this is a display-only filter — the underlying graph file is
            untouched, and the heuristic is imperfect in both directions).
          </p>
        )}
        {loadError && <p className="error-text">{loadError}</p>}
      </section>

      <div className="graph-layout">
        <section className="card graph-canvas-card">
          {!graph && !loadError && <p className="muted">Loading graph…</p>}
          {graph && (
            <CytoscapeComponent
              elements={CytoscapeComponent.normalizeElements(elements)}
              stylesheet={STYLESHEET}
              layout={
                {
                  name: "cose",
                  animate: false,
                  nodeRepulsion: 12000,
                  idealEdgeLength: 70,
                  numIter: 1500,
                } as cytoscape.LayoutOptions
              }
              style={{ width: "100%", height: "70vh", background: "#12141d", borderRadius: 8 }}
              cy={(cy) => {
                cyRef.current = cy;
                cy.removeAllListeners();
                cy.on("tap", "node", (evt) => selectNode(evt.target.data() as GraphNode));
                cy.on("tap", "edge", (evt) => {
                  const e = evt.target.data() as GraphEdge;
                  setSelected({ kind: "edge", data: e });
                });
                cy.on("tap", (evt) => {
                  if (evt.target === cy) setSelected(null);
                });
              }}
            />
          )}
        </section>

        <section className="card graph-detail-card">
          <div className="run-header">
            <h3>Details</h3>
            {selected && (
              <button className="button" onClick={() => setSelected(null)}>
                Clear
              </button>
            )}
          </div>
          {!selected && (
            <p className="muted">
              Click a node or edge to spotlight it — everything else dims so you can actually read its
              neighborhood.
            </p>
          )}
          {selected?.kind === "node" && (
            <div>
              <h4>{selected.data.label}</h4>
              <p>
                <strong>Type:</strong> {selected.data.type ?? "—"}
                {selected.data.looks_like_noise && (
                  <span className="badge badge--outcome-confirmed_false_positive_historical" style={{ marginLeft: 6 }}>
                    flagged as likely noise
                  </span>
                )}
              </p>
              <p>
                <strong>PMID count:</strong> {selected.data.pmid_count}
              </p>
              <p>
                <strong>Sample PMIDs:</strong>
              </p>
              <ul className="pmid-list">
                {selected.data.sample_pmids.map((pmid) => (
                  <li key={pmid}>
                    <a href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}`} target="_blank" rel="noreferrer">
                      {pmid}
                    </a>
                  </li>
                ))}
              </ul>
              <p style={{ marginTop: "0.75rem" }}>
                <strong>Connections ({connections.length}):</strong>
              </p>
              <ul className="connections-list">
                {connections.map((c) => (
                  <li key={c.edge.id}>
                    <button className="connection-row" onClick={() => selectNode(c.otherNode)}>
                      <span className="connection-row__arrow">{c.direction === "out" ? "→" : "←"}</span>
                      <span className="connection-row__label">{c.otherNode.label}</span>
                      <span className="muted connection-row__meta">
                        {c.edge.relation ?? "related"} · {c.edge.pmid_count} pmid
                      </span>
                    </button>
                  </li>
                ))}
                {connections.length === 0 && <li className="muted">No visible connections.</li>}
              </ul>
            </div>
          )}
          {selected?.kind === "edge" && (
            <div>
              <h4>
                {selected.data.source} → {selected.data.target}
              </h4>
              <p>
                <strong>Relation:</strong> {selected.data.relation ?? "—"}
              </p>
              <p>
                <strong>Confidence:</strong> {selected.data.confidence ?? "—"}
              </p>
              <p>
                <strong>Evidence strength:</strong> {selected.data.evidence_strength ?? "—"}
              </p>
              <p>
                <strong>PMID count:</strong> {selected.data.pmid_count}
              </p>
              <ul className="pmid-list">
                {selected.data.sample_pmids.map((pmid) => (
                  <li key={pmid}>
                    <a href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}`} target="_blank" rel="noreferrer">
                      {pmid}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
