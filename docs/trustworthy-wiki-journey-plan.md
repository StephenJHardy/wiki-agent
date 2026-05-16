---
title: Trustworthy Wiki Journey Plan
description: Concrete next steps for moving from a capable local wiki prototype to a reviewable, provenance-aware daily-use system.
---

# Trustworthy Wiki Journey Plan

## Objective

Move the repository from a capable local prototype into a trustworthy daily-use wiki system.

The main development journey is no longer basic command coverage. The core surfaces exist. The next work is about making generated knowledge reviewable, auditable, and easier to maintain over time.

## Current Position

The project now has:

- local vault initialization
- source ingest for markdown, text, HTML, PDF, URLs, and directories
- LLM-backed ingest, query, and lint behind provider interfaces
- schema-driven prompts and templates
- wiki-backed query with optional filing
- lint issue reporting
- operation artifacts
- source publication provenance fields
- topic-level claim timeline entries
- a FastHTML viewer for browsing, search, issues, and operations

The local `vault/` should now be treated as runtime data rather than source code. New wiki scaffolds should be generated from application templates, not maintained as tracked repo-local vault files.

## Step 1: Commit Hygiene And Repository Boundary

Goal: make the repo clearly distinguish application source from generated local wiki data.

Tasks:

- keep `.gitignore` blocking repo-local `vault/` runtime data
- commit removal of previously tracked vault files from the Git index
- keep scaffold definitions in `src/llm_wiki/templates.py`
- keep behavior covered by tests rather than committed example vault output

Commit shape:

```text
Stop tracking generated local vault data
```

Then commit feature work separately:

```text
Add source provenance and claim timeline scaffolding
```

This separation matters because generated vault state should not obscure application behavior changes.

## Step 2: Backfill And Refresh Story

Goal: make new metadata features usable on existing vaults.

Status: implemented for registered source refresh and index rebuild.

Current provenance fields only appear when sources are ingested or re-ingested. Existing local pages will not automatically gain publication metadata or claim timeline entries.

Add one or more explicit refresh workflows:

```bash
llm-wiki refresh-source <source-id>
llm-wiki refresh-source --all
llm-wiki rebuild-index
```

Implemented command behavior:

- `refresh-source <source-id>` refreshes one registered source
- `refresh-source --all` refreshes every registered source
- `rebuild-index` rebuilds `vault/wiki/index.md` from current wiki pages
- refresh uses the ingest change-planning path with operation name `refresh`
- refresh supports `--dry-run`, `--llm/--no-llm`, provider/model overrides, and max file-change guards

Likely behavior:

- read source records from `vault/state/sources.json`
- reload raw or extracted source text
- regenerate source metadata
- update source pages
- update affected concept/entity claim timelines
- rebuild `index.md`
- append one log entry
- save an operation artifact

This should use the same change planning path as ingest.

## Step 3: Durable Review Queue

Goal: make high-impact changes reviewable before they mutate the wiki.

Status: implemented for saved `ChangePlan` review, including pending/applied/rejected state and CLI apply/reject commands. Lint-generated fixes remain part of Step 4.

Dry-run currently previews a `ChangePlan`, but it is not a durable workflow. Add persisted review plans under state:

```text
vault/state/reviews/
  pending/
  applied/
  rejected/
```

New commands:

```bash
llm-wiki review list
llm-wiki review show <review-id>
llm-wiki review apply <review-id>
llm-wiki review reject <review-id>
```

Implemented command behavior:

- `review list` lists saved review plans by status
- `review show <review-id>` renders the stored change plan and diffs
- `review apply <review-id>` applies a pending plan and moves it to `applied/`
- `review reject <review-id>` moves a pending plan to `rejected/`
- applying a review checks that current file contents still match the stored `before` content

Ingest, query filing, refresh, and lint fixes should be able to emit pending plans:

```bash
llm-wiki ingest paper.pdf --review
llm-wiki query "question" --file --review
llm-wiki lint --propose-fixes --review
```

Implemented review-producing commands:

- `ingest --review`
- `query --file --review`
- `refresh-source <source-id> --review`
- `refresh-source --all --review`
- `rebuild-index --review`

Implementation notes:

- store serialized `ChangePlan` objects as JSON
- include prompt versions, model metadata, retrieval traces, and source fallback status
- validate max touched files before saving
- render diffs from the stored plan
- move plans to `applied/` or `rejected/` after user action

## Step 4: Lint As Fix Generator

Goal: turn lint from a report into a maintenance workflow.

Status: implemented for conservative deterministic fixes. Broader ambiguous fixes remain suggestions.

Current lint can report issues and persist issue state. The next step is to let lint propose fixes as reviewable plans.

Initial fix classes:

- missing cross-links
- broken links with obvious target candidates
- stale source metadata
- missing claim timeline sections
- pages missing from `index.md`
- orphan pages that can be linked from known related topics

Implemented fix classes:

- pages missing from `index.md`
- missing `Claim Timeline` sections on entity and concept pages
- broken wiki links where the target has an exact case-insensitive page-title match

New command shape:

```bash
llm-wiki lint --propose-fixes
llm-wiki lint --propose-fixes --review
```

Implemented behavior:

- `lint --propose-fixes` prints conservative change-plan previews
- `lint --propose-fixes --review` saves those plans under `vault/state/reviews/pending/`
- proposed fixes are not applied directly by lint
- fixes are applied through `llm-wiki review apply <review-id>`

Rules:

- fixes should be conservative
- every proposed edit should cite the issue it resolves
- lint should not directly rewrite pages unless explicitly applied
- ambiguous fixes should remain suggestions, not edits

## Step 5: Claim-Level Provenance

Goal: move from topic-level timelines to explicit knowledge provenance.

The current claim timeline says a source discusses or mentions a page. That is useful scaffolding, but it is not yet true claim tracking.

Introduce a structured claim model:

```yaml
claims:
  - claim_id: nes-vmc-free-parameters
    text: NES-VMC avoids free parameters and explicit orthogonalization for the targeted excited states.
    introduced_by_source_id: accurateexcitedstateswithneuralnetworks-pdf
    published_at: 2024-05-17
    observed_at: 2026-04-05T23:24:53+10:00
    confidence: 0.8
    related_pages:
      - NES-VMC
      - Quantum Excited States
```

Possible storage:

```text
vault/state/claims.json
vault/wiki/concepts/<page>.md
vault/wiki/entities/<page>.md
```

Start with state storage and render summaries into pages. This keeps claim tracking machine-readable without making markdown frontmatter too noisy.

Useful derived questions:

- which source first introduced this claim to the wiki?
- what was the source publication date?
- when did the wiki observe it?
- which later sources reinforced it?
- which later sources contradicted it?

## Step 6: Provenance And Review Viewer

Goal: make trust signals visible without requiring terminal inspection.

Add viewer routes:

```text
/reviews
/reviews/{id}
/timeline
/sources/{source-id}
/page/{slug}/provenance
```

Viewer capabilities:

- list pending review plans
- show diffs for a plan
- show source publication metadata
- show source-to-page lineage
- show page claim timeline
- show which claims are oldest, newest, contradicted, or thinly sourced

The viewer should remain a reflection of markdown and state files. It should not become a separate source of truth.

## Step 7: Retrieval And Query Upgrade

Goal: make provenance available to answers.

Once claim provenance exists, query should use it.

Near-term improvements:

- include source publication dates in query answers when relevant
- distinguish "published in source" from "ingested into wiki"
- prefer newer or more authoritative sources when the question is temporal
- expose retrieval traces in filed analysis pages
- benchmark retrieval against fixed query cases

Example answer behavior:

```text
The earliest source currently in the wiki for NES-VMC is [[Accurate Computation of Quantum Excited States with Neural Networks]], dated 2024-05-17 and ingested on 2026-04-05.
```

## Recommended Order

1. Commit repository boundary cleanup.
2. Commit source provenance and claim timeline scaffolding.
3. Add refresh/backfill commands.
4. Add durable review queue.
5. Teach lint to propose fixes into the review queue.
6. Add claim-level provenance state.
7. Add viewer routes for reviews, sources, timelines, and provenance.
8. Feed provenance into query answers and retrieval evaluation.

## Non-Goals For This Journey

- replacing markdown with a database
- making the viewer the canonical state store
- automatic high-impact edits without review
- solving semantic retrieval before write/review safety is solid
- treating a repo-local example vault as source code
