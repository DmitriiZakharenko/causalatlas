import { useEffect, useMemo, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import type * as cytoscape from "cytoscape";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { GraphEdge, GraphNode, GraphResponse, GraphSummary } from "../api/types";

const TYPE_COLORS: Record<string, string> = {
  Disease: "#be123c",
  Gene: "#2563eb",
  Drug: "#7c3aed",
  Tissue: "#0891b2",
  Cell_type: "#16a34a",
  Cell: "#6b8fcf",
  Cytokine: "#e07a3f",
  Molecule: "#5aa469",
  Pathway: "#d97706",
  Clinical_phenotype: "#c23a4b",
  canonical_db: "#475569",
  unknown: "#94a3b8",
};
const TYPE_SHAPES: Record<string, string> = {
  Disease: "round-rectangle",
  Gene: "hexagon",
  Drug: "diamond",
  Tissue: "rectangle",
  Cell_type: "ellipse",
  Cell: "ellipse",
  Cytokine: "ellipse",
  Molecule: "diamond",
  Pathway: "tag",
  Clinical_phenotype: "round-rectangle",
  canonical_db: "round-rectangle",
  unknown: "ellipse",
};
const LEGEND_TYPES = ["Disease", "Gene", "Drug", "Tissue", "Cell_type", "Cell", "Cytokine", "Molecule", "Pathway", "Clinical_phenotype", "canonical_db", "unknown"];
const DEFAULT_COLOR = "#9ca7b8";
const DEFAULT_SHAPE = "ellipse";
const SPOTLIGHT_COLOR = "#d97706";
const SEARCH_COLOR = "#15803d";
const GRAPH_CANVAS_BG = "#f7faff";

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
      shape: "ellipse",
      label: "data(label)",
      "font-size": 8,
      "min-zoomed-font-size": 7,
      color: "#1f2937",
      "text-outline-width": 1.2,
      "text-outline-color": "#ffffff",
      "text-margin-y": -2,
      width: "mapData(pmid_count, 0, 150, 9, 42)",
      height: "mapData(pmid_count, 0, 150, 9, 42)",
      "border-width": 1,
      "border-color": "#ffffff",
      "transition-property": "opacity, border-width, border-color",
      "transition-duration": 120,
    },
  },
  { selector: 'node[type = "Disease"]', style: { shape: "round-rectangle" } },
  { selector: 'node[type = "Gene"]', style: { shape: "hexagon" } },
  { selector: 'node[type = "Drug"]', style: { shape: "diamond" } },
  { selector: 'node[type = "Tissue"]', style: { shape: "rectangle" } },
  { selector: 'node[type = "Cell_type"]', style: { shape: "ellipse" } },
  { selector: 'node[type = "Molecule"]', style: { shape: "diamond" } },
  { selector: 'node[type = "Pathway"]', style: { shape: "tag" } },
  { selector: 'node[type = "Clinical_phenotype"]', style: { shape: "round-rectangle" } },
  { selector: 'node[type = "canonical_db"]', style: { shape: "round-rectangle", "border-style": "dotted", "border-width": 2 } },
  {
    selector: ".input-only",
    style: {
      "border-width": 2,
      "border-style": "dashed",
      "border-color": "#475569",
      width: 28,
      height: 28,
      "font-size": 10,
    },
  },
  {
    selector: "edge",
    style: {
      width: "mapData(pmid_count, 0, 50, 0.6, 5)",
      "line-color": "#94a3b8",
      "target-arrow-color": "#94a3b8",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.7,
      "curve-style": "bezier",
      opacity: 0.65,
      "transition-property": "opacity, line-color, width",
      "transition-duration": 120,
    },
  },
  {
    selector: 'edge[evidence_strength = "weak"]',
    style: { "line-style": "dashed", opacity: 0.5 },
  },
  {
    selector: 'edge[provenance_type = "canonical_db"]',
    style: { "line-style": "dotted", "line-color": "#475569", "target-arrow-color": "#475569", opacity: 0.8 },
  },
  {
    selector: 'edge[contradiction_group]',
    style: { "line-color": "#dc2626", "target-arrow-color": "#dc2626" },
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
  const [searchParams] = useSearchParams();
  const [graphs, setGraphs] = useState<GraphSummary[] | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [hideNoise, setHideNoise] = useState(true);
  const [showInputOnly, setShowInputOnly] = useState(false);
  const [showUnresolved, setShowUnresolved] = useState(false);
  const [typeFilter, setTypeFilter] = useState("all");
  const [provenanceFilter, setProvenanceFilter] = useState("all");
  const [selected, setSelected] = useState<SelectedElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    api
      .listGraphs()
      .then((r) => {
        setGraphs(r.graphs);
        if (r.graphs.length > 0) {
          const requestedDisease = searchParams.get("disease");
          const requestedRun = searchParams.get("run");
          const runMatch = requestedRun
            ? r.graphs.find((graph) => graph.run_id === requestedRun || graph.disease_slug.endsWith(`__${requestedRun}`))
            : undefined;
          const diseaseMatch = requestedDisease
            ? r.graphs.find((graph) => graph.disease_slug === requestedDisease)
            : undefined;
          const diseaseRuns = requestedDisease
            ? r.graphs.filter((graph) => graph.disease_slug.startsWith(`${requestedDisease}__`))
            : [];
          const latestDiseaseRun = [...diseaseRuns].sort((a, b) => (b.run_id ?? "").localeCompare(a.run_id ?? ""))[0];
          setSelectedSlug((runMatch ?? diseaseMatch ?? latestDiseaseRun ?? r.graphs[0]).disease_slug);
        }
      })
      .catch((err) => setLoadError(err instanceof ApiError ? `${err.status}: ${err.message}` : String(err)));
  }, [searchParams]);

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

  const { visibleNodes, visibleEdges, hiddenNoiseCount, hiddenInputCount, hiddenUnresolvedCount } = useMemo(() => {
    if (!graph) return { visibleNodes: [] as GraphNode[], visibleEdges: [] as GraphEdge[], hiddenNoiseCount: 0, hiddenInputCount: 0, hiddenUnresolvedCount: 0 };
    const nodes = graph.elements.nodes.filter((node) => {
      if (!showInputOnly && node.is_input_only) return false;
      if (!showUnresolved && node.type === "unknown") return false;
      if (hideNoise && node.looks_like_noise) return false;
      if (typeFilter !== "all" && node.type !== typeFilter) return false;
      if (provenanceFilter !== "all" && (node.provenance_type ?? "pmid") !== provenanceFilter) return false;
      return true;
    });
    const keptIds = new Set(nodes.map((n) => n.id));
    const edges = graph.elements.edges.filter((e) => keptIds.has(e.source) && keptIds.has(e.target));
    return {
      visibleNodes: nodes,
      visibleEdges: edges,
      hiddenNoiseCount: hideNoise ? graph.elements.nodes.filter((node) => node.looks_like_noise).length : 0,
      hiddenInputCount: showInputOnly ? 0 : graph.elements.nodes.filter((node) => node.is_input_only).length,
      hiddenUnresolvedCount: showUnresolved ? 0 : graph.elements.nodes.filter((node) => node.type === "unknown").length,
    };
  }, [graph, hideNoise, showInputOnly, showUnresolved, typeFilter, provenanceFilter]);

  const elements = useMemo(() => {
    return [
      ...visibleNodes.map((n) => ({
        data: {
          ...n,
          color: TYPE_COLORS[n.type ?? ""] ?? DEFAULT_COLOR,
          shape: TYPE_SHAPES[n.type ?? ""] ?? DEFAULT_SHAPE,
        },
        classes: n.is_input_only ? "input-only" : "",
      })),
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

  const spreadGraph = () => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.layout({
      name: "concentric",
      animate: false,
      avoidOverlap: true,
      minNodeSpacing: 55,
      padding: 90,
      spacingFactor: 1.8,
      concentric: (node: cytoscape.NodeSingular) => node.degree() * 10 + Number(node.data("pmid_count") ?? 0),
      levelWidth: () => 35,
    } as cytoscape.LayoutOptions).run();
    cy.fit(cy.elements(), 90);
  };

  return (
    <div className="page page--wide">
      <section className="card">
        <div className="graph-toolbar">
          <label>
            Disease
            <select value={selectedSlug ?? ""} onChange={(e) => setSelectedSlug(e.target.value)}>
              {graphs?.map((g) => (
                <option key={g.disease_slug} value={g.disease_slug}>
                  {g.disease}{g.run_id ? ` · ${g.run_id}` : " · latest alias"} ({g.node_count} nodes / {g.edge_count} edges)
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
          <label>
            Entity type
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="all">All types</option>
              {[...new Set(graph?.elements.nodes.map((node) => node.type).filter(Boolean))].sort().map((type) => (
                <option key={type} value={type ?? ""}>{type}</option>
              ))}
            </select>
          </label>
          <label>
            Provenance
            <select value={provenanceFilter} onChange={(e) => setProvenanceFilter(e.target.value)}>
              <option value="all">All sources</option>
              <option value="pmid">PMID evidence</option>
              <option value="canonical_db">Canonical database</option>
            </select>
          </label>
          <label className="form__radio" style={{ alignSelf: "flex-end", marginBottom: 2 }}>
            <input type="checkbox" checked={hideNoise} onChange={(e) => setHideNoise(e.target.checked)} />
            <span>Hide likely-noise nodes (heuristic filter)</span>
          </label>
          <label className="form__radio" style={{ alignSelf: "flex-end", marginBottom: 2 }}>
            <input type="checkbox" checked={showInputOnly} onChange={(e) => setShowInputOnly(e.target.checked)} />
            <span>Show input-only targets</span>
          </label>
          <label className="form__radio" style={{ alignSelf: "flex-end", marginBottom: 2 }}>
            <input type="checkbox" checked={showUnresolved} onChange={(e) => setShowUnresolved(e.target.checked)} />
            <span>Show unresolved-type nodes</span>
          </label>
          {graph && (
            <span className="muted">
              {graph.metadata.updated ? `Updated ${String(graph.metadata.updated).slice(0, 10)}` : null}
              {graph.metadata.version ? ` · v${graph.metadata.version}` : null}
            </span>
          )}
          {selectedSlug && (
            <Link
              className="button"
              to={`/graphs/${selectedSlug}/pathogenesis${selected?.kind === "node" ? `?node=${encodeURIComponent(selected.data.id)}` : ""}`}
            >
              {selected?.kind === "node" ? `Summarize ${selected.data.label}` : "Text summary"}
            </Link>
          )}
          <button type="button" className="button" onClick={spreadGraph} disabled={!graph}>
            Spread graph
          </button>
        </div>
        {graph && (
          <>
            <div className="graph-targets" aria-label="Analysis target dimensions">
              {Object.entries((graph.metadata.target_dimensions as Record<string, string[]> | undefined) ?? {}).flatMap(([type, values]) =>
                values.map((value) => (
                  <span className="graph-target-chip" key={`${type}-${value}`}>
                    <strong style={{ color: TYPE_COLORS[type] ?? DEFAULT_COLOR }}>{type.replace("_", " ")}:</strong> {value}
                  </span>
                )),
              )}
            </div>
            <div className="graph-legend" aria-label="Graph legend">
              <span className="graph-legend__title">Node legend</span>
              {LEGEND_TYPES.map((type) => (
                <span className="graph-legend__item" key={type}>
                  <i className={`graph-legend__swatch graph-legend__swatch--${TYPE_SHAPES[type]}`} style={{ backgroundColor: TYPE_COLORS[type] }} />
                  {type.replace("_", " ")}
                </span>
              ))}
              <span className="graph-legend__title">Edges</span>
              <span className="graph-legend__item"><i className="graph-legend__line" /> stronger PMID support</span>
              <span className="graph-legend__item"><i className="graph-legend__line graph-legend__line--dashed" /> weak evidence</span>
              <span className="graph-legend__item"><i className="graph-legend__swatch" style={{ backgroundColor: "#475569", borderStyle: "dashed" }} /> input-only target (optional overlay)</span>
              <span className="graph-legend__item"><i className="graph-legend__swatch" style={{ backgroundColor: TYPE_COLORS.canonical_db }} /> canonical evidence source</span>
              <span className="graph-legend__item"><i className="graph-legend__swatch" style={{ backgroundColor: TYPE_COLORS.unknown }} /> unresolved type</span>
            </div>
          </>
        )}
        {hideNoise && hiddenNoiseCount > 0 && (
          <p className="muted" style={{ marginTop: "0.5rem" }}>
            Hiding {hiddenNoiseCount} of {graph?.elements.nodes.length} nodes flagged by a heuristic as likely
            sentence-fragment extraction artifacts (this is a display-only filter — the underlying graph file is
            untouched, and the heuristic is imperfect in both directions).
          </p>
        )}
        {!showInputOnly && hiddenInputCount > 0 && (
          <p className="muted" style={{ marginTop: "0.5rem" }}>
            Hidden {hiddenInputCount} input-only target dimensions. They are shown above as target chips and are
            not evidence nodes; enable “Show input-only targets” only when auditing the submitted target.
          </p>
        )}
        {!showUnresolved && hiddenUnresolvedCount > 0 && (
          <p className="muted" style={{ marginTop: "0.5rem" }}>
            Hidden {hiddenUnresolvedCount} unresolved-type nodes from the primary view. Enable “Show unresolved-type
            nodes” to audit them; gray means the entity type was not confidently normalized.
          </p>
        )}
        {loadError && <p className="error-text">{loadError}</p>}
      </section>

      <div className="graph-layout">
        <section className="card graph-canvas-card">
          {!graph && !loadError && <p className="muted">Loading graph…</p>}
          {graph && (
            <CytoscapeComponent
              key={selectedSlug ?? "empty-graph"}
              elements={CytoscapeComponent.normalizeElements(elements)}
              stylesheet={STYLESHEET}
              layout={
                {
                  name: "concentric",
                  animate: false,
                  avoidOverlap: true,
                  minNodeSpacing: 55,
                  padding: 90,
                  spacingFactor: 1.8,
                  concentric: (node: cytoscape.NodeSingular) => node.degree() * 10 + Number(node.data("pmid_count") ?? 0),
                  levelWidth: () => 35,
                } as cytoscape.LayoutOptions
              }
              style={{ width: "100%", height: "78vh", minHeight: 640, background: GRAPH_CANVAS_BG, borderRadius: 8 }}
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
                {selected.data.type === "unknown" && (
                  <span className="muted"> — extracted node without a confident entity-type normalization</span>
                )}
                {selected.data.is_input_only && (
                  <span className="muted"> — user-supplied target dimension, not an evidence claim</span>
                )}
                {selected.data.is_canonical_source && (
                  <span className="muted"> — canonical database source, not a PMID-derived biological node</span>
                )}
                {selected.data.looks_like_noise && (
                  <span className="badge badge--outcome-confirmed_false_positive_historical" style={{ marginLeft: 6 }}>
                    flagged as likely noise
                  </span>
                )}
              </p>
              {selected.data.canonical_statement && (
                <p><strong>Canonical statement:</strong> {selected.data.canonical_statement}</p>
              )}
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
              {(selected.data.relation_variants ?? selected.data.relations ?? []).length > 0 && (
                <p><strong>Evidence variants:</strong> {(selected.data.relation_variants ?? selected.data.relations ?? []).join(", ")}</p>
              )}
              <p>
                <strong>Confidence:</strong> {selected.data.confidence ?? "—"}
              </p>
              <p>
                <strong>Evidence strength:</strong> {selected.data.evidence_strength ?? "—"}
              </p>
              <p>
                <strong>Provenance:</strong> {selected.data.provenance_type ?? "PMID evidence"}
              </p>
              {selected.data.sessions && selected.data.sessions.length > 0 && (
                <p><strong>Sessions:</strong> {selected.data.sessions.join(", ")}</p>
              )}
              {selected.data.context && Object.values(selected.data.context).some((value) => Array.isArray(value) && value.length > 0) && (
                <p><strong>Context:</strong> {JSON.stringify(selected.data.context)}</p>
              )}
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
              {(selected.data.source_refs ?? []).some((ref) => typeof ref === "object" && ref !== null && ref.source_sentence) && (
                <div className="edge-evidence-sentences">
                  <p><strong>Evidence sentences:</strong></p>
                  <ul>
                    {(selected.data.source_refs ?? [])
                      .filter((ref): ref is Record<string, unknown> => typeof ref === "object" && ref !== null && typeof ref.source_sentence === "string")
                      .slice(0, 5)
                      .map((ref, index) => (
                        <li key={`${String(ref.pmid ?? "source")}-${index}`}>
                          {ref.pmid ? <a href={`https://pubmed.ncbi.nlm.nih.gov/${String(ref.pmid)}`} target="_blank" rel="noreferrer">PMID {String(ref.pmid)}</a> : "Source"}: {String(ref.source_sentence)}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
