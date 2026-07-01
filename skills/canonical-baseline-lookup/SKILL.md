---
name: canonical-baseline-lookup
description: Use this skill when fetching already-established, curated mechanistic facts from structured canonical databases (Reactome/KEGG/UniProt/MyDisease.info) before any literature search -- Agent 1's only job, so downstream agents never have to re-discover known-consensus mechanisms via a live literature search on every run.
---

# Skill: Canonical Baseline Lookup

Free-only, zero auth token required for all four sources (KEGG requires no token but has
academic-use licensing terms, see Source 2 below). All endpoints below are official,
documented REST APIs -- none inferred or guessed.

## When to use this skill
- **Agent 1 (Baseline Canonical Knowledge) only.** No other agent calls these four APIs
  directly — Agent 5 (Mechanistic Extraction) and Agent 10 (Novelty Verification) consume
  Agent 1's `canonical_baseline.json` output, they never call Reactome/KEGG/UniProt/
  MyDisease.info themselves.

## Source 1: Reactome Content Service

- Base: `https://reactome.org/ContentService`
- Free-text search (Solr-backed): `/search/query?query={term}&species=Homo+sapiens&cluster=true`
- Known stable ID lookup: `/data/query/{stId}`
- Participating molecules for a pathway/reaction: `/data/event/{stId}/participatingPhysicalEntities`
- Fields returned: `displayName`, `stId`, `dbId`, `species`, `schemaClass`; nested
  `literatureReference` objects include `pubMedIdentifier`/`title`/`year`/`journal` -- useful
  for cross-linking a canonical edge back to its original supporting PMIDs if needed.
- Auth: none. Rate limit: not formally published -- keep to reasonable single-client volume,
  no bulk scraping.
- Format: JSON (default) or `text/plain` depending on `Accept` header.

## Source 2: KEGG REST API

- Base: `https://rest.kegg.jp`
- Search: `/find/{database}/{query}` -- e.g. `/find/pathway/asthma` or `/find/disease/asthma`
- Full entry: `/get/{dbentries}` -- e.g. `/get/hsa05310` (asthma pathway ID); **max 10 IDs per
  call**.
- Cross-reference to gene/UniProt: `/conv/{target_db}/{source_db}` -- e.g. mapping KEGG gene
  IDs <-> UniProt IDs directly, useful for stitching this agent's output to Agent 5's later
  UniProt-sourced nodes.
- Auth: none required.
- **Rate limit: hard cap 3 requests/second (documented, will block on excess)** -- stricter
  than PubMed's; throttle explicitly, do not rely on retry-after behavior alone.
- **Licensing: KEGG's REST API is restricted to "academic use by academic users"** -- this is
  explicitly documented on KEGG's own API page. This is a usage-terms restriction, not a
  free-vs-paid-tier distinction -- do not confuse it with KEGG's separate paid FTP/subscription
  product for bulk downloads, which is unrelated. Academic/course-project use of the REST API
  as specified here is within terms.
- Format: flat text by default; `/get/{id}/json` for JSON where supported.

## Source 3: UniProt REST API

- Base: `https://rest.uniprot.org`
- Search: `/uniprotkb/search?query=gene:{gene}+AND+organism_id:9606&fields=accession,gene_names,cc_function,go_id`
- Query syntax: Solr-style, supports `AND`/`OR`/`NOT` and field-scoped terms (`gene:`,
  `organism_id:`, `protein_name:`, etc.) -- full field list at uniprot.org/help/query-fields.
- Fields worth requesting for this project: `cc_function` (protein function summary text),
  `go_id`/`go` (Gene Ontology terms -- a direct source for canonical "activates/inhibits"
  style edges), `cc_pathway`, `ft_domain`.
- Auth: none. Rate limit: not hard-capped for reasonable single-client use; UniProt's own
  guidance is to batch queries rather than loop single-entry lookups.
- Response headers include `X-Total-Results` (log corpus size the same way the
  `pubmed-literature-search` skill logs `total_in_pubmed`) and `X-UniProt-Release` (version
  string -- stamp this into `canonical_baseline.json` for reproducibility).
- Format: JSON via `Accept: application/json`, or TSV for bulk table export.

## Source 4: MyDisease.info (BioThings suite)

- Base: `https://mydisease.info/v1`
- Query: `/query?q={term}&fields=disgenet,hpo,ctd,mondo` -- e.g. `?q=asthma&fields=disgenet`
- Get by ID: `/disease/{MONDO_id}` -- e.g. `/disease/MONDO:0004979` (asthma's MONDO ID).
- Batch: `POST /query` or `POST /disease` with `ids=` comma-separated list, **up to 1000 per
  call** -- use this instead of looping single GETs when pulling multiple gene-disease pairs.
- Fields worth requesting: `disgenet` (gene-disease association scores), `hpo` (phenotype
  ontology terms), `ctd` (chemical/environmental relations), `mondo.xrefs` (cross-database ID
  mapping, useful for linking back to the Reactome/KEGG disease IDs above).
- Auth: none required, but docs request an `email=` param on batch calls for usage-tracking
  courtesy (optional, still $0).
- Rate limit: not hard-published; same "don't hammer it" norm as sibling BioThings APIs
  (MyGene.info, MyChem.info -- available if gene- or drug-specific lookups are ever needed).
- Format: JSON.

## Procedure

1. For the target `{disease, gene?}`, query all four sources: Reactome search, KEGG
   `find`/`get`, UniProt search (if a `gene` is given), MyDisease.info query.
2. For each hit, extract the canonical statement/relationship and record it as a
   `canonical_baseline.json` entry with `provenance_type: "canonical_db"` and the real
   source-database identifier (Reactome `stId`, KEGG entry ID, UniProt accession, or MONDO
   ID) -- never a synthesized ID.
3. If a source returns zero results for the target, record it in `sources_queried` with zero
   entries from that source -- do not skip recording that the source was tried.
4. Throttle KEGG calls to <=3 req/sec explicitly; batch UniProt and MyDisease.info calls
   where the API supports it (MyDisease.info's `POST` batch, UniProt's field-scoped queries)
   rather than looping single-entity GETs.
5. Stamp `X-UniProt-Release` (or equivalent version info from other sources, where available)
   into the output for reproducibility -- a canonical database's content can change between
   runs, and a downstream discrepancy should be traceable to a version, not treated as a bug.

## Mandatory rule: never invent a canonical identifier

Every `canonical_baseline.json` entry MUST trace to a real, independently verifiable
identifier from one of the four sources above (a real Reactome `stId`, a real KEGG entry ID,
a real UniProt accession, or a real MONDO ID). If none of the four sources return a usable
hit for a given candidate relationship, that relationship is NOT in the canonical baseline --
do not backfill with a plausible-sounding entry. This is the same anti-fabrication standard
`pubmed-literature-search` and `novelty-verification-protocol` apply to PMIDs and search
results.

## Downstream consumption (read-only for everyone except Agent 1)

- Agent 5 (Mechanistic Extraction) may use `canonical_baseline.json` as context for entity
  naming/disambiguation, but must never tag a new edge as PMID-sourced when its only real
  support is a canonical_db entry.
- Agent 6 (Graph Builder) merges canonical_db entries into the graph with
  `provenance_type: "canonical_db"` preserved, never conflated with PMID-sourced provenance.
- Agent 10 (Novelty Verification) treats a canonical_baseline match as sufficient grounds to
  auto-classify a candidate `A (Established consensus)` **without needing a
  PubMed/Semantic Scholar/OpenAlex hit-count search** -- this is the entire reason Agent 1 and
  this skill exist as a separate first pipeline step, rather than folding canonical-database
  lookups into Agent 10 itself (which would mean re-querying these four sources fresh on
  every single candidate, on every single run).

## Success criteria
- Every `canonical_baseline.json` entry's identifier is independently verifiable by querying
  the cited source directly.
- All four sources are recorded in `sources_queried` every run, even when a source returned
  zero entries.
- KEGG calls never exceed 3 req/sec; no other agent besides Agent 1 calls these four APIs
  directly.
