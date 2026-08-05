# ADR 0001: Multidimensional Analysis Targets

- Status: accepted
- Date: 2026-08-05
- Baseline: `v0.2.0`

## Context

CausalAtlas currently accepts a disease and an optional gene. The research group
needs to constrain an analysis by additional biological dimensions, including
drugs, tissues, and cell types.

The repository already contains durable sessions, cumulative graphs, an API, an
offline UI, and historical fixtures. Replacing these contracts would make prior
analyses harder to reproduce and would unnecessarily create a second product.

## Decision

Extend the current application additively with a versioned analysis-target
contract. The legacy `disease` and optional `gene` request remains supported and
is normalized internally into the new contract.

The new dimensions are optional:

- disease
- genes
- drugs
- tissues
- cell types
- an explicit or derived query mode

Every run records the resolved target and its schema version as a session artifact.
Existing database columns and legacy graph files are retained. Database changes
are additive-only migrations.

Canonical database evidence remains distinct from PMID evidence. A drug-target
relationship, a disease association, and clinical efficacy are separate claims and
must not be collapsed into one edge or one quality label.

## Versioning

`v0.2.0` is the immutable baseline for the disease-target implementation. The
extension is developed on a feature branch and will receive a later release tag.
The target contract has its own schema version; this does not imply a product
rewrite or a breaking API release.

## Compatibility requirements

- Legacy `{disease, gene}` requests continue to work.
- Existing session artifacts remain readable.
- Existing cumulative graphs are never rewritten in place solely to add schema
  fields.
- Offline replay and historical fixtures remain valid.
- Failed, paused, and partial runs retain explicit states.

## Scientific safety requirements

- Search queries must record their strategy, scope, and result counts.
- Retrieval, publication verification, evidence quality, and mechanistic extraction
  remain separate stages.
- Noise filtering is display- or stage-specific and must not silently delete
  provenance-bearing evidence.
- Novelty classification still requires the independent A-E verification protocol.
- No drug is described as effective merely because it binds a target or appears in
  a publication.

## Consequences

The API, persistence layer, pipeline context, agent contracts, query generation,
graph metadata, and UI require coordinated additive changes. This is more work than
adding extra form fields, but it preserves reproducibility and prevents biological
context from being lost in free-text prompts.
