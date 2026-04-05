---
title: LLM Wiki Phase 1 Plan
description: Concrete MVP plan and scaffold scope for a uv-managed local CLI.
---

# LLM Wiki Phase 1 Plan

## Objective

Build a local, filesystem-first CLI for maintaining a persistent LLM-managed wiki. Phase 1 focuses on bootstrapping the repository, defining the vault layout, and creating a stable entrypoint for later ingest, query, and lint work.

## Product Shape

The system has three durable layers:

- `vault/raw/` for immutable source material
- `vault/wiki/` for generated markdown pages, indexes, and logs
- `AGENTS.md` for the operating schema that tells an LLM how to maintain the wiki

Phase 1 does not try to solve search, embeddings, PDF parsing, or autonomous batch ingestion. It establishes the contract those future features will rely on.

## Repository Layout

```text
.
├── docs/
│   └── phase-1-plan.md
├── src/llm_wiki/
│   ├── cli.py
│   ├── config.py
│   ├── filesystem.py
│   ├── templates.py
│   └── commands/
│       ├── init.py
│       ├── ingest.py
│       ├── query.py
│       └── lint.py
├── tests/
│   └── test_init_command.py
├── AGENTS.md
└── vault/
    ├── raw/
    ├── wiki/
    └── state/
```

## Phase 1 Deliverables

### 1. Project Scaffold

- Create a `uv`-managed Python application package
- Define a `llm-wiki` CLI entrypoint
- Add a small dependency set for CLI ergonomics and structured configuration

### 2. Vault Bootstrap

- Add `llm-wiki init`
- Create the vault directory structure
- Seed `vault/wiki/index.md`
- Seed `vault/wiki/log.md`
- Seed `vault/state/sources.json`
- Seed a root `AGENTS.md` with workflow rules

### 3. Future Command Stubs

- `llm-wiki ingest`
- `llm-wiki query`
- `llm-wiki lint`

These are placeholders in Phase 1 so the command surface is explicit from the beginning.

## Design Principles

- Prefer plain files over infrastructure.
- Keep raw sources immutable.
- Make the wiki deterministic enough for tests.
- Let the model propose changes later, but keep file writes under Python control.
- Optimize for Obsidian compatibility and git-friendly markdown.

## Planned Follow-On Phases

### Phase 2: Single-source ingest

Phase 2 turns the repository from a static scaffold into a working wiki maintainer. The main goal is to process one source at a time and integrate it into the existing markdown graph instead of treating each question as fresh retrieval.

#### Scope

- Accept markdown and plain text sources first
- Register sources in `vault/state/sources.json`
- Generate a source summary page in `vault/wiki/sources/`
- Update existing concept, entity, and overview pages when the source materially changes them
- Create new concept or entity pages when the source introduces important recurring ideas or named things
- Update `vault/wiki/index.md` on every ingest
- Append a parseable chronological entry to `vault/wiki/log.md`

#### Intended workflow

The expected operating mode is human-in-the-loop and source-by-source:

1. The user drops a file into `vault/raw/sources/`.
2. The user runs `llm-wiki ingest <source>`.
3. The tool reads `index.md`, recent `log.md` entries, and any obviously relevant pages before touching the new raw source.
4. The LLM extracts the source's main claims, entities, concepts, themes, and contradictions.
5. The application turns that analysis into deterministic file updates.
6. The user reviews the resulting wiki changes in git or Obsidian.

This phase should optimize for careful, inspectable updates rather than batch throughput.

#### Output contract

Each ingest should be able to touch many pages in one pass. A single article, paper, or chapter may:

- create a new source summary page
- revise one or more entity pages
- revise one or more concept pages
- update a high-level overview or synthesis page
- add or strengthen wiki links between pages
- note where the new source confirms, sharpens, or contradicts older claims

The wiki is the compiled artifact. The ingest pipeline should therefore favor incremental synthesis over isolated summaries.

#### Source page shape

Source summary pages should include:

- YAML frontmatter with `title`, `type: source`, `source_id`, `source_path`, `ingested_at`, and `source_ids`
- a concise summary of the source
- key claims or takeaways
- notable entities and concepts with wiki links
- contradictions, uncertainties, or limitations
- pointers to related pages updated during ingest

#### Entity and concept maintenance

Entity pages should accumulate what the wiki currently believes about a named thing over multiple sources. Concept pages should synthesize themes, ideas, frameworks, or recurring topics across sources. In both cases, ingest should prefer updating existing pages over creating duplicates with near-identical names.

Important constraint: contradictions should not be silently flattened. When a new source challenges an older one, the page should record that explicitly, ideally with a short note about which source says what.

#### Index and log behavior

`index.md` is the navigation layer, not an afterthought. On every ingest it should be updated with:

- a link to each new page
- a one-line description
- enough metadata to guide later retrieval, such as page type or source count

`log.md` should remain append-only and easy to parse with shell tools. Entries should follow a stable prefix such as:

```md
## [2026-04-05] ingest | Source Title
```

Each log entry should capture:

- the source processed
- the wiki pages created or updated
- whether contradictions or open questions were found

#### Technical milestones

- Add source discovery and source ID generation
- Add frontmatter parsing and rendering
- Add markdown page load/update helpers
- Define a structured LLM response schema for proposed wiki changes
- Implement deterministic merge/write logic for source, entity, concept, and overview pages
- Add tests with fixture sources and golden-file expectations

#### Explicit deferrals

- PDF parsing beyond a minimal adapter
- image understanding during ingest
- unattended multi-source ingestion
- embeddings or external search infrastructure

### Phase 3: Wiki-backed query

Phase 3 uses the wiki as the primary knowledge interface. The raw source collection remains the ground truth, but most questions should be answerable by consulting the maintained wiki first, because the synthesis and cross-references have already been compiled.

#### Scope

- Read `vault/wiki/index.md` before deeper retrieval
- Identify candidate pages from the wiki itself rather than querying raw sources by default
- Synthesize answers with citations to wiki pages
- Support filing useful answers back into `vault/wiki/analyses/`
- Support multiple output shapes over time, starting with markdown answers

#### Query philosophy

This phase should embody the core difference from standard RAG:

- the LLM should not rediscover the knowledge base from scratch every time
- the first retrieval target is the persistent wiki, not arbitrary chunks from raw documents
- answers should reflect prior synthesis, cross-linking, and contradiction tracking already embedded in the wiki

At moderate scale, `index.md` should remain the first routing layer. The workflow is:

1. Read `index.md`.
2. Select likely relevant pages by title, summary, and section.
3. Read the selected pages in full.
4. Synthesize an answer from those pages.
5. Fall back to raw sources only when the wiki is clearly insufficient.

#### Answer contract

Query responses should include:

- a direct answer
- citations to relevant wiki pages
- explicit uncertainty where the wiki is thin, conflicting, or stale
- optional suggestions for follow-up sources or questions when gaps are detected

The initial implementation should produce markdown in the terminal and optionally save a reusable result as a new page.

#### Filing answers back into the wiki

One of the main value multipliers in this system is that useful explorations should compound. Phase 3 should therefore support a mode where a strong answer is persisted as a new page in `vault/wiki/analyses/`.

Examples:

- a comparison table between two tools or ideas
- an evolving synthesis on a research question
- a topic-specific briefing generated from multiple existing wiki pages

Filed analyses should include frontmatter linking them back to the pages and source IDs they rely on.

#### Output formats

The initial implementation should focus on markdown. The plan should leave room for richer formats later, because the request explicitly calls out outputs like:

- comparison tables
- Marp slide decks
- matplotlib charts
- canvas-style artifacts

Those should be treated as alternate renderers over the same wiki-backed synthesis pipeline, not separate products.

#### Search evolution

This phase should still work without embeddings or a vector database. `index.md` plus filesystem search should be enough initially. If the wiki grows beyond that, the next step is a local search tool rather than a hosted retrieval stack.

The most likely extension path is:

- keep the basic index-first strategy
- add local markdown search
- optionally integrate a tool like `qmd` later for BM25/vector hybrid retrieval and reranking

#### Technical milestones

- Add page selection and citation formatting helpers
- Implement an index-first retrieval strategy
- Add a query execution pipeline that separates page selection from synthesis
- Add a `--file` or similar option to persist answers into `vault/wiki/analyses/`
- Add tests for citation output and filing behavior

#### Explicit deferrals

- web search during ordinary queries
- rich media outputs in the first release
- MCP integration for query-time tools
- raw-source-first retrieval as the default path

### Phase 4: Linting and maintenance

Phase 4 keeps the wiki healthy as it scales. The goal is not just syntax linting. It is knowledge maintenance: finding places where the compiled artifact has drifted, become sparse, or failed to absorb what the source base now contains.

#### Scope

- Broken wiki links
- Orphan pages with no inbound links
- Important concepts or entities mentioned repeatedly but lacking their own page
- Pages with weak or missing source references
- Stale claims that newer sources may have superseded
- Contradictions across pages
- Missing cross-references between closely related pages
- Suggestions for next research questions or missing source types

#### Lint philosophy

The lint command should act as a periodic health check on the knowledge base, not a formatter. It should answer questions like:

- what pages are disconnected from the rest of the graph
- where the wiki says conflicting things
- which summaries lag behind recently ingested sources
- what important areas are underspecified relative to the raw material

This is the maintenance work humans usually neglect and the LLM is unusually well suited to doing.

#### Checks to implement

##### Structural checks

- broken internal links
- duplicate or near-duplicate page titles
- missing required frontmatter fields
- pages present in the wiki but absent from `index.md`

##### Knowledge checks

- claims on one page contradicted by another
- overview pages that omit major entities or concepts introduced by recent sources
- concepts mentioned repeatedly in source summaries but lacking dedicated pages
- entity pages that have not absorbed information from relevant newer sources

##### Navigation checks

- orphan pages
- weakly linked clusters
- pages with many outbound references but no inbound references
- opportunities to strengthen graph connectivity for Obsidian graph view usefulness

#### Output contract

Lint results should be grouped by severity and actionability, for example:

- errors for broken links or corrupt frontmatter
- warnings for stale or weakly sourced pages
- suggestions for missing pages, cross-links, and follow-up research

The command should be able to either:

- print a report only
- or file a maintenance note into the wiki, for example under `vault/wiki/analyses/` or a future `maintenance/` area

Every lint pass should append an entry to `log.md` so the wiki has a visible maintenance history.

#### Relationship to external search

The request explicitly calls out data gaps that could be filled with web search. Phase 4 should detect and report those gaps, but not automatically browse or mutate the raw source base. A good first implementation is to suggest:

- what is missing
- why it matters
- what kind of source would close the gap

Later versions can add optional web-assisted research workflows.

#### Technical milestones

- Add markdown link graph construction
- Add inbound/outbound link analysis
- Add frontmatter validation
- Add heuristics for stale pages based on `updated_at`, `source_ids`, and recent log activity
- Add an LLM-assisted contradiction review pass over related pages
- Add report rendering in terminal-friendly markdown

#### Explicit deferrals

- automatic corrective edits during lint
- autonomous web research and source ingestion
- graph visualizations inside the CLI
- heavy semantic deduplication infrastructure

## Non-Goals

- Web UI
- Remote services beyond an LLM provider
- Vector database integration
- Full document parsing for PDFs and images
- Team workflows or access control

## Success Criteria

- A user can clone the repo, run one setup command, and initialize a vault.
- The repository clearly communicates the intended wiki architecture.
- The codebase has enough structure to add ingest, query, and lint logic without refactoring the foundations.
