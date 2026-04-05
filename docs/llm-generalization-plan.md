---
title: LLM Wiki Generalization Plan
description: Roadmap for replacing heuristic logic with LLM-backed workflows, improving retrieval and ranking, and adding a stronger viewing experience.
---

# LLM Wiki Generalization Plan

## Objective

Generalize the current deterministic prototype into a real LLM-powered system without breaking the filesystem-first contract. The end state should preserve the current strengths:

- raw sources remain immutable
- the wiki remains plain markdown on disk
- `index.md` and `log.md` remain first-class navigation and audit artifacts
- file writes remain under application control

The change is in how decisions are made. Instead of heuristic extraction, heuristic query synthesis, and heuristic linting, the system should use an LLM for the reasoning-heavy parts and keep Python responsible for orchestration, validation, and writes.

## Current State

Today the repository has a working local CLI for:

- ingesting text and markdown sources
- generating source, entity, and concept pages
- answering questions from the wiki
- linting for structural problems and weak graph connectivity

However, all reasoning is currently heuristic. Retrieval is simple lexical scoring. Query answers are shallow. Lint catches structural issues but not deeper knowledge inconsistencies. There is also no dedicated viewing experience beyond raw markdown and external tools such as Obsidian.

## Design Principles

- Keep the wiki as the primary product, not the chat response.
- Use LLMs for synthesis, extraction, comparison, contradiction review, and prioritization.
- Keep deterministic guards around all writes.
- Prefer provider abstraction over hardcoding one API path.
- Support a strong local workflow first, then optional richer interfaces.
- Make retrieval staged rather than monolithic: index first, lexical filtering second, semantic reranking third, synthesis last.

## Architecture Direction

The generalized system should have five layers:

1. **Filesystem layer**
   - `vault/raw/` for immutable sources
   - `vault/wiki/` for generated knowledge pages
   - `vault/state/` for metadata, caches, and provider-safe state

2. **Application layer**
   - CLI commands for ingest, query, lint, and future maintenance tasks
   - deterministic page parsing, rendering, indexing, and logging

3. **Retrieval layer**
   - index-first routing
   - lexical candidate generation
   - optional local full-text search
   - optional embedding-based reranking

4. **LLM layer**
   - provider abstraction
   - prompt templates
   - structured JSON outputs
   - retry, validation, and cost controls

5. **Presentation layer**
   - terminal output
   - filed markdown artifacts
   - a local viewer for browsing, navigation, and maintenance workflows

## Workstreams

### 1. LLM Integration

This workstream replaces heuristic reasoning with provider-backed planning and synthesis while preserving deterministic file writes.

#### Goals

- add a provider abstraction
- support Gemini first, without coupling the rest of the codebase to Gemini-specific request shapes
- move ingest, query synthesis, and deeper lint analysis behind structured LLM calls
- support future providers such as OpenAI or Anthropic with the same internal interfaces

#### Proposed module layout

```text
src/llm_wiki/
  llm/
    __init__.py
    base.py
    config.py
    prompts.py
    schemas.py
    retry.py
    providers/
      gemini.py
      openai.py
```

#### Responsibilities

- `base.py`
  - provider interface
  - request and response models
  - common error types

- `config.py`
  - environment loading
  - model selection
  - temperature, token, and timeout defaults

- `prompts.py`
  - system prompts for ingest, query, and lint
  - reusable prompt sections for page conventions and schema rules

- `schemas.py`
  - Pydantic models for structured LLM outputs
  - response validation for extraction plans, page updates, candidate selection, and lint findings

- `providers/gemini.py`
  - Gemini API transport
  - auth using `GOOGLE_API_KEY`
  - structured generation wrapper

#### Core rule

The LLM should not directly emit markdown files as final authority. It should emit a structured plan that Python validates and applies.

Examples:

- ingest plan
  - source summary
  - entities to create or update
  - concepts to create or update
  - contradictions to note
  - candidate overview pages to revise

- query plan
  - selected pages
  - answer
  - uncertainty notes
  - filing suggestion

- lint plan
  - suspected contradictions
  - stale pages
  - missing concept pages
  - recommended new sources

#### Rollout phases

##### Phase A: Provider plumbing

- load `.env` safely
- add Gemini client
- add a CLI-visible config path for model selection
- add smoke-testable provider wrappers

##### Phase B: LLM-backed ingest

- replace heuristic extraction with a structured ingest prompt
- keep current Python merge/write logic
- validate response schema before file updates

##### Phase C: LLM-backed query synthesis

- use retrieval output as context
- synthesize answers and uncertainty notes with the model
- keep citation formatting deterministic

##### Phase D: LLM-backed lint reasoning

- keep structural lint in Python
- add model-assisted contradiction and stale-claim review over candidate page groups

#### Risks

- hallucinated entities or concepts
- unstable page naming
- over-eager page creation
- high token usage for large page sets
- hidden provider-specific assumptions

#### Controls

- strict structured outputs
- page title normalization in Python
- max touched pages per operation
- explicit human review mode for high-impact writes
- prompt versioning in code

### 2. Retrieval and Ranking

This workstream improves how the system finds relevant wiki pages and when it should fall back to raw sources.

#### Goals

- preserve `index.md` as the first routing layer
- improve candidate selection quality
- avoid full raw-source retrieval for ordinary questions
- support local search at larger wiki scale

#### Retrieval pipeline

The intended query path should become:

1. Read `index.md`.
2. Use index summaries and page metadata to shortlist candidate titles.
3. Run lexical retrieval over the shortlisted pages and optionally the full wiki.
4. Run semantic reranking on the top candidates.
5. Pass the best pages into synthesis.
6. Fall back to raw sources only when the wiki cannot answer confidently.

#### Retrieval improvements

##### Metadata enrichment

Add more usable frontmatter to pages:

- `tags`
- `aliases`
- `page_type`
- `source_count`
- `confidence`
- `last_reviewed_at`
- `related_topics`

This improves both index readability and search features such as faceting or reranking.

##### Better lexical search

Near-term improvements:

- field-aware scoring
  - title matches
  - heading matches
  - summary matches
  - body matches
- phrase boosting
- alias matching
- section-level snippets

This can be done entirely in Python first.

##### Semantic reranking

After lexical candidate generation, use either:

- local embeddings plus cosine similarity
- provider embeddings if acceptable
- LLM reranking on top N candidates

The most practical staged path is:

1. strong lexical retrieval
2. optional embedding store for page summaries
3. LLM reranker for the final 10 to 20 candidates

##### Raw-source fallback

If the wiki is missing coverage, the system should support a second-stage fallback:

- search source summaries first
- then raw source text
- then optional web research in a later workflow

This fallback should be explicit in the answer, not silent.

#### Optional search backends

The roadmap should support multiple retrieval backends:

- built-in Python lexical search
- `ripgrep`-based fallback
- `qmd` integration later for hybrid BM25/vector search

The retrieval interface should make backend choice configurable rather than hardcoded.

#### Ranking evaluation

Add a small benchmark set under `tests/fixtures/queries/`:

- query
- expected top pages
- acceptable alternates
- failure cases

This is important because retrieval quality will otherwise regress quietly.

### 3. Viewing and Interaction Layer

The wiki is already browseable in Obsidian, but the project should also have a first-party way to inspect content, follow links, review changes, and run maintenance flows.

#### Goals

- provide a pleasant local way to browse the wiki
- support search, graph-aware navigation, and maintenance review
- keep the viewer optional and non-destructive
- avoid turning the project into a heavy hosted app before the core workflows are solid

#### Recommended direction

Build the viewer as a lightweight local FastHTML app after the LLM and retrieval layers are stabilized.

Suggested stack:

- FastHTML for the local web layer
- server-rendered HTML with HTMX-style progressive enhancement where useful
- markdown rendering with wiki-link support
- MathJax-enabled rendering for LaTeX-heavy pages
- filesystem-backed data access only

#### Viewer capabilities

##### Core browsing

- page list by section
- full-text search box
- page detail view with rendered markdown
- backlinks view
- related pages panel
- recent log activity

##### Maintenance views

- ingest review screen showing proposed file changes before apply
- lint dashboard grouped by severity
- stale page queue
- contradiction review queue
- orphan page queue

##### Knowledge exploration

- graph neighborhood view for a page
- source-to-page lineage view
- timeline view from `log.md`
- filters by source, page type, topic, or date

#### Math-heavy content support

Math is a first-class requirement rather than a later enhancement. The viewer should:

- preserve inline and block LaTeX from markdown sources and generated wiki pages
- render equations with MathJax
- avoid markdown processing that corrupts TeX syntax
- support mixed prose, lists, code blocks, and displayed math on the same page

The markdown pipeline should therefore be math-aware and tested against representative wiki content.

#### Obsidian compatibility

The viewer should not replace Obsidian. It should complement it.

The safest design is:

- keep markdown files as the single source of truth
- render wiki links exactly as they exist on disk
- do not introduce viewer-only page state that cannot be reconstructed from the repo

#### Near-term alternative

Before building a web app, add a stronger terminal and file-based view layer:

- `llm-wiki show <PAGE>`
- `llm-wiki backlinks <PAGE>`
- `llm-wiki recent`
- `llm-wiki search "<QUERY>"`

This is a lower-risk step and will probably improve the development loop immediately.

### 4. Schema and Prompt Generalization

The system becomes materially more useful once the agent schema is explicit enough to guide different LLMs reliably.

#### Goals

- move page rules out of implicit code behavior and into reusable schema documents
- support different domains without rewriting core code
- make prompts depend on declared conventions rather than hidden assumptions

#### Proposed artifacts

- `AGENTS.md`
  - repository operating manual for agent behavior
- `vault/schema/`
  - optional domain-specific prompt fragments
  - page templates
  - controlled vocabularies

#### Domain overrides

Examples:

- research wiki
  - claims, evidence, open questions, competing hypotheses
- personal wiki
  - goals, habits, patterns, reflections, experiments
- fiction-reading wiki
  - characters, locations, plot threads, themes, spoilers

The core app should load the same orchestration flow but allow prompt/schema specialization by domain.

### 5. Safety, Validation, and Review

A stronger LLM system increases both capability and risk. This workstream keeps the behavior inspectable and reversible.

#### Goals

- avoid silent corruption of the wiki
- make LLM actions reviewable
- give users confidence about why a page changed

#### Required controls

- dry-run mode for ingest, query filing, and lint filing
- diff previews before apply
- per-command limits on pages touched
- command logs that include prompt and model metadata
- structured validation failures surfaced clearly to the user

#### Audit metadata

Add optional fields such as:

- `generated_by`
- `model`
- `prompt_version`
- `review_status`

These can live in frontmatter or state files depending on how noisy the user wants the markdown to be.

## Recommended Delivery Sequence

### Phase 5: LLM foundation

- env loading
- provider abstraction
- Gemini client
- prompt and schema modules
- smoke tests

### Phase 6: LLM-backed ingest

- structured extraction prompt
- deterministic merge engine reused from current ingest
- review mode and dry-run support

### Phase 7: Retrieval upgrade

- better lexical search
- metadata enrichment
- reranking interface
- retrieval benchmark fixtures

### Phase 8: LLM-backed query and lint

- query synthesis with citations and uncertainty
- contradiction review pass in lint
- source-gap suggestions

### Phase 9: Viewer

- terminal navigation helpers first
- then lightweight local web viewer
- ingest review and lint review surfaces

## Success Criteria

- ingest, query, and lint all use a provider-backed reasoning path behind stable Python interfaces
- retrieval quality is meaningfully better than the current heuristic scorer on a fixed benchmark set
- filed analyses and maintenance reports remain deterministic markdown artifacts
- the viewer makes the wiki easier to navigate without becoming the source of truth
- the system remains usable offline except for LLM provider calls

## Non-Goals

- replacing the markdown wiki with a database-backed product
- making the viewer the canonical data store
- autonomous web crawling by default
- opaque end-to-end agent writes without validation
