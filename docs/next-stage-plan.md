---
title: LLM Wiki Next Stage Plan
description: Roadmap for the next development stage based on the repository's current capabilities rather than the original greenfield sequence.
---

# LLM Wiki Next Stage Plan

## Objective

Move the project from a working generalized prototype into a trustworthy day-to-day system for maintaining a persistent LLM-written wiki.

The next stage is not about adding another major surface area. The core surfaces already exist:

- ingest
- query
- lint
- view
- provider-backed LLM integration
- schema-driven prompt configuration

The next stage should make these surfaces safer, deeper, and more reliable.

## Current Baseline

The repository already has:

- deterministic filesystem writes for wiki pages
- Gemini-backed LLM calls behind a provider abstraction
- schema-aware prompt construction from `AGENTS.md` and `vault/schema/`
- field-aware lexical retrieval
- a FastHTML viewer with MathJax-capable markdown rendering

This means the remaining work is not greenfield product design. It is mostly:

- stronger write planning and review
- better retrieval quality
- better knowledge maintenance
- better domain-specific behavior
- better observability and trust

## Success Criteria For This Stage

By the end of this stage:

- high-impact wiki writes can be previewed and reviewed before apply
- retrieval quality is meaningfully better on a fixed benchmark set
- query can transparently fall back when the wiki is insufficient
- lint can surface more useful, higher-confidence maintenance work
- the viewer supports maintenance workflows, not just browsing
- prompt/schema versions and model metadata are visible enough to debug behavior

## Workstreams

### 1. Safe Write Planning

The biggest remaining gap is that the system can write useful pages, but it still lacks a robust review layer. This is the highest-priority workstream.

#### Goal

Convert ingest, filed query answers, and future maintenance actions into explicit proposed changes that can be previewed before apply.

#### Deliverables

- a structured `ChangePlan` model
- a dry-run mode for ingest, query filing, and lint filing
- diff previews before files are written
- touched-page limits and write guards
- prompt/model metadata in operation logs

#### Target design

Every write-producing command should follow:

1. gather context
2. produce a structured change plan
3. validate the plan
4. render a preview
5. apply only when allowed

#### Proposed modules

```text
src/llm_wiki/
  planning.py
  apply.py
  diffing.py
  review.py
```

#### Notes

- Python remains the only layer that mutates files.
- LLM outputs should describe intended changes, not directly author arbitrary files.
- Review mode should become the default for high-impact ingest once the workflow is mature.

### 2. Retrieval Quality Upgrade

Lexical retrieval is now serviceable, but it is still the weakest part of the stack relative to the plan.

#### Goal

Improve candidate selection enough that query quality scales past small demo vaults.

#### Deliverables

- retrieval benchmark fixtures
- query evaluation cases with expected top pages
- section-aware snippets and scoring introspection
- a reranking interface
- optional embedding-backed reranking
- explicit raw-source fallback path when the wiki is thin

#### Proposed execution order

##### Step A: Benchmarking

- add `tests/fixtures/queries/`
- record query, expected pages, and allowed alternates
- make retrieval changes measurable

##### Step B: Better lexical retrieval

- phrase windows
- heading weighting refinements
- alias normalization improvements
- section-level snippet extraction

##### Step C: Reranking layer

- add a `Reranker` interface
- support a provider-backed reranker first
- optionally add local embedding storage later

##### Step D: Raw-source fallback

- if wiki confidence is low, search source summaries
- if source summaries are insufficient, read raw text
- keep fallback explicit in the answer

### 3. LLM Planning Depth

LLM integration exists, but it is still relatively shallow. The next stage should move from “LLM supplies structured content” to “LLM supplies structured maintenance intent.”

#### Goal

Use the model for better change planning without allowing opaque direct file control.

#### Deliverables

- richer ingest plan schema
- query filing recommendation schema
- lint maintenance action schema
- explicit contradiction objects rather than free-text notes
- page-create vs page-update vs page-link recommendations

#### Example shift

Current ingest asks for a structured analysis of a source.

Next-stage ingest should ask for:

- source summary
- candidate pages to update
- why each page should change
- whether a new page is required
- whether conflicting claims must be preserved
- confidence per proposed action

#### Constraints

- do not let the LLM choose arbitrary file paths
- do not let the LLM bypass schema rules
- do not let the LLM create unbounded new pages in one pass

### 4. Lint As Maintenance Workflow

Lint already finds structural issues and some model-assisted issues, but it does not yet drive a maintenance loop.

#### Goal

Turn lint from a report generator into a useful queue of maintenance actions.

#### Deliverables

- grouped maintenance issue types
- confidence scoring for findings
- deduplicated issue tracking in state
- “resolve by updating page” suggestions
- source-gap suggestions grouped by topic

#### High-value issue classes

- contradictions
- stale synthesis
- missing concept pages
- missing cross-links
- isolated topic clusters
- source pages that were ingested but never propagated properly

#### Viewer tie-in

The viewer should eventually expose:

- contradiction queue
- stale page queue
- orphan page queue
- issue detail views with candidate fixes

### 5. Viewer Maintenance UX

The viewer is already useful for reading, but the next stage should make it useful for operating the wiki.

#### Goal

Add maintenance and review workflows to the FastHTML app without turning it into a second source of truth.

#### Deliverables

- review page for pending change plans
- richer search results with filters
- page history and lineage view
- backlinks and related pages on more routes
- issue dashboard from lint output
- source-to-page traceability view

#### Important rule

The viewer should remain a reflection of the markdown repo, not a separate application state machine.

### 6. Schema Maturity

Schema generalization is in place, but it is still mostly prompt decoration. The next stage should make schema affect real behavior more deeply.

#### Goal

Let domain schemas shape merge behavior, validation, and viewer defaults instead of only prompt wording.

#### Deliverables

- schema-driven required section validation
- schema-driven page template rendering hints
- domain-specific frontmatter defaults
- domain-specific lint checks
- domain-specific viewer facets

#### Examples

##### Research domain

- stronger contradiction handling
- evidence and uncertainty sections
- stale-claim emphasis

##### Personal domain

- recurring-pattern detection
- goals and experiments as first-class tags

##### Fiction domain

- chronology checks
- spoiler-aware page conventions
- stronger entity/location/thread linking

### 7. Observability And Debugging

As the system gets more adaptive, behavior becomes harder to understand. The next stage should make reasoning and failures more legible.

#### Goal

Make it easier to understand why the system did what it did.

#### Deliverables

- prompt version capture
- model/provider capture
- retrieval reason traces stored with query logs
- optional saved prompt/response artifacts in `vault/state/`
- clearer fallback reporting when LLM calls fail

#### Practical output

When a query answer is weak, the user should be able to inspect:

- which pages were retrieved
- why they were ranked
- whether the LLM path ran
- which schema and prompt version were used
- whether raw-source fallback was triggered

## Recommended Delivery Order

### Phase A: Trust And Review

- structured change plans
- dry-run mode
- diff previews
- operation metadata logging

### Phase B: Retrieval Measurement And Upgrade

- retrieval benchmarks
- reranking interface
- raw-source fallback

### Phase C: Maintenance Workflows

- stronger lint issue model
- issue queues
- viewer issue dashboard

### Phase D: Schema-Driven Behavior

- schema-aware validation
- domain-specific lint and merge rules
- template-aware page shaping

## Non-Goals For This Stage

- replacing markdown with a database
- multi-user collaboration features
- hosted SaaS deployment
- autonomous web crawling by default
- rich media generation beyond focused outputs already supported by markdown workflows

## Immediate Next Task Recommendation

Start with **Safe Write Planning**.

That work unlocks the rest:

- richer LLM planning becomes safer
- viewer review screens have something meaningful to show
- lint can propose fixes without immediately mutating the wiki
- retrieval and schema changes become easier to debug because the write path is inspectable
