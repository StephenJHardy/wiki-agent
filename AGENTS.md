# LLM Wiki Agent Guide

This repository is a filesystem-first personal wiki maintained by an LLM agent.

## Core Rules

- Treat files under `vault/raw/` as immutable sources of truth.
- Write generated knowledge into `vault/wiki/`.
- Update `vault/wiki/index.md` whenever pages are created or materially changed.
- Append one chronological entry to `vault/wiki/log.md` for every ingest, query filing, or lint pass.
- Prefer revising existing pages over creating duplicates.
- Use wiki links (`[[Page Title]]`) between related pages.

## Page Conventions

- Every wiki page should have YAML frontmatter.
- Include `title`, `type`, `updated_at`, and `source_ids`.
- Keep source summaries in `vault/wiki/sources/`.
- Keep reusable concepts in `vault/wiki/concepts/`.
- Keep people, companies, places, and named things in `vault/wiki/entities/`.
- Keep question-driven writeups in `vault/wiki/analyses/`.

## Workflow

1. Read `vault/wiki/index.md` before answering questions or editing the wiki.
2. Read the relevant wiki pages before touching raw sources.
3. When ingesting a new source, update all affected pages in one pass.
4. When new information conflicts with older pages, preserve the contradiction explicitly instead of silently overwriting it.
5. When a chat answer is broadly useful, file it back into the wiki as a new or updated page.
