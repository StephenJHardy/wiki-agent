# LLM Wiki

A local CLI for building persistent, LLM-maintained personal knowledge bases.

This project implements the "LLM wiki" pattern as a filesystem-first tool. Raw sources stay immutable on disk, the generated wiki lives in markdown files you can browse in Obsidian, and an agent guide defines how an LLM should maintain the knowledge base over time.

## Status

Phase 4 foundation is implemented, with local-first source normalization for papers and web pages.

What exists today:

- `uv`-managed Python project
- `llm-wiki` CLI entrypoint
- `llm-wiki init` to bootstrap a new vault
- `llm-wiki ingest` for local markdown, text, HTML, and PDF sources, plus remote HTML/PDF snapshot ingestion
- `llm-wiki query` for wiki-backed answers with optional filing to `vault/wiki/analyses/`
- `llm-wiki lint` for wiki health checks with optional filing to `vault/wiki/analyses/`
- `llm-wiki view` to launch a FastHTML-based local wiki viewer
- Gemini-backed LLM integration behind a provider abstraction
- schema-driven prompt and domain configuration under `vault/schema/`
- starter templates for `AGENTS.md`, `index.md`, `log.md`, and source state
- metadata-enriched wiki page generation for source, entity, concept, and analysis pages
- source publication provenance for authors, publication dates, venues, DOI, and arXiv IDs when available
- generated claim timelines on entity and concept pages to distinguish publication dates from wiki ingest dates
- index rebuilding and append-only logging across ingest, query, and lint
- field-aware retrieval and ranking for wiki-backed query
- MathJax-enabled markdown viewing for LaTeX-heavy wiki pages
- local-first paper ingestion with derived extraction stored separately from raw sources

What does not exist yet:

- semantic reranking and embedding-backed retrieval
- contradiction detection beyond simple structural heuristics
- rich output formats beyond markdown
- broader provider coverage beyond Gemini
- deep domain-specific merge logic beyond prompt/schema specialization

## Quickstart

Install dependencies:

```bash
uv sync
```

Initialize a vault in the current repository:

```bash
uv run llm-wiki init .
```

This creates:

```text
AGENTS.md
vault/
  raw/
    sources/
    assets/
  wiki/
    index.md
    log.md
    overviews/
    entities/
    concepts/
    sources/
    analyses/
  state/
    sources.json
    extracted/
    issues/
    operations/
    reviews/
  schema/
    config.yaml
    prompts/
    templates/
```

## CLI

Current commands:

- `uv run llm-wiki init [PATH]`
- `uv run llm-wiki ingest <SOURCE>`
- `uv run llm-wiki ingest-dir <DIRECTORY>`
- `uv run llm-wiki refresh-source <SOURCE_ID>`
- `uv run llm-wiki rebuild-index`
- `uv run llm-wiki review list`
- `uv run llm-wiki query "<QUESTION>"`
- `uv run llm-wiki lint`
- `uv run llm-wiki view`

All commands are implemented.

Example ingest flow:

```bash
uv run llm-wiki ingest my-article.md
```

You can also ingest a local PDF or snapshot a remote paper page:

```bash
uv run llm-wiki ingest transformers.pdf
uv run llm-wiki ingest https://arxiv.org/html/1706.03762
```

For a directory of local papers:

```bash
uv run llm-wiki ingest-dir /path/to/papers --path .
```

Ingest expects local sources to exist under `vault/raw/sources/` unless you pass an explicit path. When given an HTTP(S) URL, it first snapshots the remote document into `vault/raw/sources/` so the local vault remains the source of truth. Ingest currently:

- registers the source in `vault/state/sources.json`
- preserves the raw local source under `vault/raw/sources/`
- writes derived markdown extraction for HTML and PDF sources to `vault/state/extracted/`
- extracts bibliographic provenance such as authors, publication date, DOI, arXiv ID, and venue when available
- creates or updates a source summary page in `vault/wiki/sources/`
- creates or updates related entity and concept pages
- adds claim timeline entries to entity and concept pages so the wiki can track which source introduced or reinforced a topic
- rebuilds `vault/wiki/index.md`
- appends an ingest entry to `vault/wiki/log.md`

`ingest-dir` copies supported local files from the input directory into `vault/raw/sources/` first, then ingests those copied files. Unsupported files are skipped.

Refresh existing registered sources when extractor behavior or schema conventions improve:

```bash
uv run llm-wiki refresh-source attention-paper --path .
uv run llm-wiki refresh-source --all --path .
```

Refresh reloads source records from `vault/state/sources.json`, reprocesses the raw source, backfills source metadata and claim timelines, rebuilds `index.md`, appends a `refresh` log entry, and saves an operation artifact.

If `index.md` needs to be rebuilt without reprocessing sources:

```bash
uv run llm-wiki rebuild-index --path .
```

If a supported LLM is configured in `.env`, ingest will use it automatically. Disable that path with `--no-llm`.

Write-producing commands also support:

- `--dry-run` to preview a structured file-change plan without writing
- `--review` to save a pending change plan under `vault/state/reviews/pending/`
- `--max-file-changes` to guard against unexpectedly large edits

Each run now saves an operation artifact under `vault/state/operations/` with provider/model metadata, prompt versions, and retrieval traces.

Review saved change plans:

```bash
uv run llm-wiki review list --path .
uv run llm-wiki review show <review-id> --path .
uv run llm-wiki review apply <review-id> --path .
uv run llm-wiki review reject <review-id> --path .
```

Applying a review checks that files still match the saved `before` content before writing, so stale review plans fail instead of overwriting newer edits.

Example query flow:

```bash
uv run llm-wiki query "When does retrieval help?" --file --title "Retrieval Brief"
```

Query currently:

- reads the wiki index first
- ranks candidate wiki pages with field-aware lexical retrieval
- answers from the maintained wiki rather than raw source files
- emits markdown with wiki-page citations
- shows the retrieved pages, scores, and match reasons
- can transparently fall back to local raw-source text when the wiki is too thin
- can file the answer back into `vault/wiki/analyses/`

When Gemini is configured, query uses the model for synthesis and uncertainty notes while keeping citation rendering and file writes deterministic.

Retrieval currently uses:

- title, alias, tag, heading, summary, and body scoring
- page-type bonuses for concept, entity, and overview pages
- frontmatter metadata written during ingest to improve future search quality

Example lint flow:

```bash
uv run llm-wiki lint --file --title "Weekly Wiki Lint"
```

Lint currently checks for:

- broken wiki links
- missing `source_ids`
- pages missing from `index.md`
- potentially stale pages relative to source updates
- orphaned or isolated pages
- likely missing cross-links between related pages
- persists a structured maintenance queue to `vault/state/issues/lint-issues.json`

When Gemini is configured, lint can add model-assisted review findings on contradictions, stale claims, missing pages, and research gaps.

Lint can also propose conservative reviewable fixes:

```bash
uv run llm-wiki lint --propose-fixes --review
```

Current fix proposals cover missing index entries, missing `Claim Timeline` sections, and broken wiki links where the target page differs only by casing. Lint does not apply those edits directly; apply them through `llm-wiki review apply <review-id>`.

Example viewer flow:

```bash
uv run llm-wiki view --path .
```

The FastHTML viewer currently provides:

- a local web UI over the markdown wiki
- page browsing by section
- retrieval-backed search
- backlinks and recent log activity
- maintenance issue and operation-artifact dashboards
- MathJax rendering for inline and block LaTeX in markdown pages

## Project Structure

- `src/llm_wiki/cli.py` wires the CLI surface.
- `src/llm_wiki/commands/` contains one module per command.
- `src/llm_wiki/templates.py` defines the starter wiki files.
- `src/llm_wiki/filesystem.py` contains deterministic file-writing helpers.
- `src/llm_wiki/source_loader.py` snapshots remote sources locally and normalizes PDF/HTML inputs for ingest.
- `src/llm_wiki/planning.py`, `src/llm_wiki/diffing.py`, and `src/llm_wiki/review.py` provide change-plan, diff, and preview support.
- `src/llm_wiki/schema.py` loads domain schema and prompt fragments from `vault/schema/`.
- `src/llm_wiki/viewer.py` contains the FastHTML viewer and math-aware markdown rendering.
- `docs/phase-1-plan.md` captures the implementation plan.
- `docs/llm-generalization-plan.md` captures the roadmap for LLM integration, retrieval upgrades, and a viewing layer.
- `docs/next-stage-plan.md` captures the roadmap from the repository's current state into the next development stage.
- `docs/deferred-engineering-items.md` records investigated work that is intentionally deferred.

## Workflow Intent

The intended steady-state workflow is:

1. Add a source file under `vault/raw/sources/`.
2. Run an ingest workflow that reads the new source and updates multiple wiki pages.
3. Ask questions against the compiled wiki rather than the raw source pile.
4. Periodically lint the wiki for gaps, contradictions, and stale claims.

The current implementation remains deterministic and heuristic-driven so it is testable. A later phase can swap in LLM-backed extraction, retrieval, and maintenance passes without changing the on-disk contract.

For paper-heavy workflows, the current ingest stack is:

- PDF extraction via `pymupdf4llm`, with a plain-text `pymupdf` fallback
- HTML extraction via `trafilatura`
- local raw-source snapshots kept immutable under `vault/raw/sources/`
- derived extraction stored separately under `vault/state/extracted/`

## Development

Run tests:

```bash
uv run pytest
```

Run the CLI help:

```bash
uv run llm-wiki --help
```

## LLM Configuration

The app looks for a local `.env` file in the repository root used for the command's `--path`.

Supported variables today:

- `GOOGLE_API_KEY`
- `LLM_WIKI_PROVIDER`
- `LLM_WIKI_MODEL`
- `LLM_WIKI_TEMPERATURE`
- `LLM_WIKI_TIMEOUT_SECONDS`

Example:

```bash
GOOGLE_API_KEY=your-key
LLM_WIKI_PROVIDER=gemini
LLM_WIKI_MODEL=gemini-3-flash-preview
```

Each command supports:

- `--llm/--no-llm`
- `--provider`
- `--model`

## Schema Configuration

Each vault includes a `vault/schema/` directory that generalizes domain behavior without rewriting the application code.

Contents:

- `config.yaml` for domain, frontmatter, required sections, and prompt versions
- `prompts/*.md` for common, ingest, query, and lint guidance
- `templates/*.md` for page-shape guidance

When you initialize a new vault, you can choose a domain:

```bash
uv run llm-wiki init . --domain research
```

Supported scaffolded domains today:

- `general`
- `research`
- `personal`
- `fiction`

The LLM prompt layer automatically loads `AGENTS.md` plus `vault/schema/` and uses both when building ingest, query, and lint prompts.

## Design Constraints

- Raw files are immutable source-of-truth inputs.
- The wiki is a persistent markdown artifact, not an ephemeral chat output.
- File writes should stay under application control even when an LLM proposes changes.
- The repository should remain easy to inspect, diff, and use with Obsidian.
