---
name: pubmed-literature-search
description: Use this skill whenever an agent needs to search or retrieve biomedical literature -- PubMed corpus construction (Agent 1), or independent novelty cross-checks against PubMed/Semantic Scholar/OpenAlex (Agent 9, Agent 11 reviewers).
---

# Skill: PubMed Literature Search

Free-only, no paid API or tier anywhere in this skill. All three sources below are either
fully free and keyless, or free with registration.

## When to use this skill
- Agent 1 (Literature Retrieval): primary corpus construction for a `{disease, gene?}`
  target.
- Agent 9 (Novelty Verification): independent external search per candidate hypothesis --
  MUST be a fresh query, not a re-read of Agent 1's corpus.
- Agent 11 (Peer Review): each reviewer's own independent search, phrased differently from
  Agent 9's and from the other reviewers'.

## Source 1: PubMed E-utilities (primary corpus retrieval)

- Base: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- Search: `esearch.fcgi?db=pubmed&term={query}&retmax=200&api_key={key}`
- Fetch full metadata: `efetch.fcgi?db=pubmed&id={pmids}&rettype=abstract&retmode=xml&api_key={key}`
- Lightweight summary: `esummary.fcgi?db=pubmed&id={pmids}&api_key={key}`
- **Free NCBI API key** (no cost, registration only): raises rate limit from 3 req/sec
  (keyless) to 10 req/sec. Register at https://www.ncbi.nlm.nih.gov/account/ and set
  `PUBMED_API_KEY` in `.env`. No paid tier exists for E-utilities, ever.
- If `PUBMED_API_KEY` is not configured, throttle requests to 3 req/sec (do not omit `key=`
  silently and hammer at 10 req/sec -- that will get rate-limited mid-run).

## Source 2: Semantic Scholar Graph API (structured cross-check)

- Base: `https://api.semanticscholar.org/graph/v1/`
- Search: `paper/search?query={query}&fields=title,year,abstract,citationCount,externalIds`
- Free; keyless works at low volume. A free API key (higher rate limit, still $0) is
  available at https://www.semanticscholar.org/product/api.
- Use for: independent literature search during Agent 9 novelty checks and Agent 11
  reviewer independent searches. Provides `citationCount`, which E-utilities does not --
  useful as a rough "how established is this" signal (a chain with a 500-citation review
  stating it directly is a strong signal toward A/B classification, not D/E).

## Source 3: OpenAlex API (broadest-coverage second cross-check)

- Base: `https://api.openalex.org/works`
- Search: `?search={query}&per-page=25`
- Fully free, no key required. Add `&mailto={real_contact_email}` to join the "polite pool"
  (higher rate limit, still free) -- use a real contact email, never a placeholder.
- Use for: the same purpose as Semantic Scholar. Run both and compare.

## Mandatory rule for novelty-classification use (Agent 9 / Agent 11)

**Never trust a single source's zero-hit result as proof of novelty.** Query at least two of
the three sources above per candidate before classifying based on absence of prior art. This
rule exists because of a real historical gap: Session 003's H-D001 and H-C002
(`data/sessions/asthma_003/session_003_report.json`) were classified D/C based on 4/4
PubMed-only zero-hit searches, run before this pipeline had a second structured source. A
single index's coverage gap can produce a false "potentially novel" result; a second,
differently-indexed source (Semantic Scholar or OpenAlex) is the check against that.

## Explicitly excluded: Google Scholar

**Never use Google Scholar** in any form -- direct scraping, or indirectly via a general
WebSearch tool call that happens to return google.com/scholar results -- as a logged source
in `novelty_audit.json`. Reasons: (1) no official API exists, so any access method is
scraping and violates Google's Terms of Service; (2) results are unstructured HTML with no
stable per-result PMID/DOI/citation-count fields, so they cannot be logged the way this
protocol's audit trail requires (a real query string + real structured results, not a vague
"I checked Google Scholar and found nothing").

## Query construction guidance (Agent 1 specifically)

- Use MeSH terms + keyword expansion, run multiple complementary query strategies per target
  (mechanism-specific: e.g. "IL-33 asthma", "ILC2 airway", not just "asthma"). At least 3
  distinct strategies per target.
- Record `total_in_pubmed` (the full hit count) alongside `retrieved` (how many were
  actually fetched) -- a query strategy that only fetches the top 40 of 20,366 total hits is
  legitimate for corpus breadth, but must not silently claim comprehensive coverage.
- **Dedup by PMID before writing output.** A paper matched by more than one query strategy
  must appear exactly once in `publications`, with all matching strategies noted if useful --
  never counted twice toward corpus size.

## Mandatory year-band stratification rule (the Session 002 fix)

This is the specific rule this skill exists to encode in one place, rather than scattered
across individual agent prompts:

- Explicitly bucket every retrieved publication by year band (e.g. 2021-2022, 2023-2024,
  2025-2026) and compute each band's share of the total corpus.
- **If any single band exceeds ~60% of the corpus, this is a hard flag, not a soft
  warning** -- set `year_band_flag: true` and surface it in the session report. Do not
  silently proceed with a temporally skewed corpus.
- Real historical failure this rule fixes: Session 001's initial asthma retrieval was 96%
  one year (430/448 papers from 2026), because PubMed's default sort is most-recent-first
  and the retrieval did not paginate (`retstart`) or stratify by year band. A corpus this
  skewed cannot support downstream "established vs. new" novelty judgments (see Agent 9's H2
  fixture, which depends on 2016-2018 papers being present in the corpus).
- Fix: paginate deeper per query strategy (use `retstart` across multiple `esearch.fcgi`
  calls) rather than accepting only the first `retmax` most-recent results.

## Rate limits (practical handling)

- Keyless: 3 req/sec across all of E-utilities combined, not per-endpoint.
- With `PUBMED_API_KEY` set: 10 req/sec.
- Batch `efetch`/`esummary` calls by passing multiple comma-separated PMIDs in one request
  rather than one request per PMID -- this is both faster and rate-limit-friendlier.
