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
      "font-size": 7,
      color: "#e6e8ee",
      "text-outline-width": 1,
      "text-outline-color": "#1a1d29",
      width: "mapData(pmid_count, 0, 150, 10, 40)",
      height: "mapData(pmid_count, 0, 150, 10, 40)",
    },
  },
  {
    selector: "edge",
    style: {
      width: "mapData(pmid_count, 0, 50, 1, 6)",
      "line-color": "#3a3f55",
      "target-arrow-color": "#3a3f55",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      opacity: 0.7,
    },
  },
  {
    selector: ".highlighted",
    style: {
      "background-color": "#ffd166",
      "line-color": "#ffd166",
      "target-arrow-color": "#ffd166",
      opacity: 1,
    },
  },
];

type SelectedElement = { kind: "node"; data: GraphNode } | { kind: "edge"; data: GraphEdge } | null;

export default function GraphExplorerPage() {
  const [graphs, setGraphs] = useState<GraphSummary[] | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
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

  const elements = useMemo(() => {
    if (!graph) return [];
    return [
      ...graph.elements.nodes.map((n) => ({
        data: { ...n, color: TYPE_COLORS[n.type ?? ""] ?? DEFAULT_COLOR },
      })),
      ...graph.elements.edges.map((e) => ({ data: { ...e } })),
    ];
  }, [graph]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("highlighted");
    if (!search.trim()) return;
    const term = search.trim().toLowerCase();
    cy.nodes().forEach((n) => {
      if ((n.data("label") as string)?.toLowerCase().includes(term)) {
        n.addClass("highlighted");
        n.connectedEdges().addClass("highlighted");
      }
    });
  }, [search, graph]);

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
          {graph && (
            <span className="muted">
              {graph.metadata.updated ? `Updated ${String(graph.metadata.updated).slice(0, 10)}` : null}
              {graph.metadata.version ? ` · v${graph.metadata.version}` : null}
            </span>
          )}
        </div>
        {loadError && <p className="error-text">{loadError}</p>}
      </section>

      <div className="graph-layout">
        <section className="card graph-canvas-card">
          {!graph && !loadError && <p className="muted">Loading graph…</p>}
          {graph && (
            <CytoscapeComponent
              elements={CytoscapeComponent.normalizeElements(elements)}
              stylesheet={STYLESHEET}
              layout={{ name: "cose", animate: false, nodeRepulsion: 8000, idealEdgeLength: 60 } as cytoscape.LayoutOptions}
              style={{ width: "100%", height: "70vh", background: "#12141d", borderRadius: 8 }}
              cy={(cy) => {
                cyRef.current = cy;
                cy.removeAllListeners();
                cy.on("tap", "node", (evt) => {
                  const n = evt.target.data() as GraphNode;
                  setSelected({ kind: "node", data: n });
                });
                cy.on("tap", "edge", (evt) => {
                  const e = evt.target.data() as GraphEdge;
                  setSelected({ kind: "edge", data: e });
                });
              }}
            />
          )}
        </section>

        <section className="card graph-detail-card">
          <h3>Details</h3>
          {!selected && <p className="muted">Click a node or edge to inspect its provenance.</p>}
          {selected?.kind === "node" && (
            <div>
              <h4>{selected.data.label}</h4>
              <p>
                <strong>Type:</strong> {selected.data.type ?? "—"}
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
