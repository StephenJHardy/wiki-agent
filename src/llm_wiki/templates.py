from __future__ import annotations

from textwrap import dedent


SUPPORTED_DOMAINS = ("general", "research", "personal", "fiction")


def agents_template() -> str:
    return dedent(
        """
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
        """
    ).strip()


def index_template() -> str:
    return dedent(
        """
        # Index

        This file is the top-level catalog for the wiki.

        ## Overviews

        - No overview pages yet.

        ## Entities

        - No entity pages yet.

        ## Concepts

        - No concept pages yet.

        ## Sources

        - No source summaries yet.

        ## Analyses

        - No analysis pages yet.
        """
    ).strip()


def log_template() -> str:
    return dedent(
        """
        # Log

        ## [uninitialized] bootstrap | Repository scaffolded

        - Created the initial LLM Wiki vault structure.
        - Next step: ingest a first source and begin building the wiki.
        """
    ).strip()


def sources_state_template() -> dict[str, object]:
    return {"sources": []}


def schema_config_template(domain: str = "general") -> str:
    payloads = {
        "general": dedent(
            """
            domain: general
            description: General-purpose persistent knowledge wiki.
            preferred_outputs:
              - markdown
            frontmatter_fields:
              - title
              - type
              - updated_at
              - source_ids
              - summary
              - aliases
              - tags
              - related_topics
            required_sections:
              source:
                - Summary
                - Key Points
                - Entities
                - Concepts
                - Caveats
              concept:
                - Concept Summary
                - Sources
                - Related Pages
              entity:
                - Entity Summary
                - Sources
                - Related Pages
              analysis:
                - Answer
                - Citations
            prompt_versions:
              ingest: v1
              query: v1
              lint: v1
            """
        ),
        "research": dedent(
            """
            domain: research
            description: Research-focused wiki emphasizing claims, evidence, uncertainty, and synthesis.
            preferred_outputs:
              - markdown
              - tables
              - slides
            frontmatter_fields:
              - title
              - type
              - updated_at
              - source_ids
              - summary
              - aliases
              - tags
              - related_topics
              - confidence
              - last_reviewed_at
            required_sections:
              source:
                - Summary
                - Key Points
                - Entities
                - Concepts
                - Caveats
              concept:
                - Concept Summary
                - Sources
                - Related Pages
              analysis:
                - Answer
                - Uncertainty
                - Citations
            prompt_versions:
              ingest: v1-research
              query: v1-research
              lint: v1-research
            """
        ),
        "personal": dedent(
            """
            domain: personal
            description: Personal knowledge wiki focused on goals, habits, reflections, and experiments.
            preferred_outputs:
              - markdown
            frontmatter_fields:
              - title
              - type
              - updated_at
              - source_ids
              - summary
              - aliases
              - tags
              - related_topics
            required_sections:
              source:
                - Summary
                - Key Points
                - Concepts
              analysis:
                - Answer
                - Follow-up Questions
                - Citations
            prompt_versions:
              ingest: v1-personal
              query: v1-personal
              lint: v1-personal
            """
        ),
        "fiction": dedent(
            """
            domain: fiction
            description: Reading companion wiki focused on characters, locations, plot threads, and themes.
            preferred_outputs:
              - markdown
              - timelines
            frontmatter_fields:
              - title
              - type
              - updated_at
              - source_ids
              - summary
              - aliases
              - tags
              - related_topics
            required_sections:
              source:
                - Summary
                - Key Points
                - Entities
                - Concepts
              entity:
                - Entity Summary
                - Sources
                - Related Pages
              analysis:
                - Answer
                - Citations
            prompt_versions:
              ingest: v1-fiction
              query: v1-fiction
              lint: v1-fiction
            """
        ),
    }
    return payloads[domain].strip()


def schema_prompt_templates(domain: str = "general") -> dict[str, str]:
    shared = {
        "common.md": dedent(
            """
            Respect the configured wiki schema. Prefer updating existing pages over creating near-duplicates.
            Use stable page titles and explicit uncertainty. Keep the wiki interlinked and navigable.
            """
        ).strip(),
        "source.md": dedent(
            """
            # Source Page Template

            - Keep source pages concise and evidence-focused.
            - Summaries should describe what the source says, not what the assistant thinks broadly.
            - Use wiki links to connect notable entities and concepts.
            """
        ).strip(),
        "entity.md": dedent(
            """
            # Entity Page Template

            - Entity pages accumulate what the wiki currently believes about a named thing.
            - Prefer synthesis over copying raw source phrasing.
            """
        ).strip(),
        "concept.md": dedent(
            """
            # Concept Page Template

            - Concept pages should synthesize recurring themes across sources.
            - Highlight contrasts, dependencies, and relationships when they matter.
            """
        ).strip(),
        "analysis.md": dedent(
            """
            # Analysis Page Template

            - Analysis pages should answer a reusable question or capture a durable synthesis.
            - They should be file-worthy, not transient chat residue.
            """
        ).strip(),
    }
    domain_prompts = {
        "general": {
            "ingest.md": "Extract stable entities, concepts, and caveats. Avoid unnecessary page proliferation.",
            "query.md": "Answer directly from the wiki, cite pages explicitly, and be honest when coverage is thin.",
            "lint.md": "Prioritize contradictions, stale pages, missing cross-links, and missing topic pages.",
        },
        "research": {
            "ingest.md": "Extract claims, evidence-bearing concepts, open questions, and competing interpretations where present.",
            "query.md": "Optimize for synthesis, uncertainty tracking, and explicit citations to competing pages or claims.",
            "lint.md": "Look for stale claims, unsupported synthesis, contradictory conclusions, and obvious evidence gaps.",
        },
        "personal": {
            "ingest.md": "Track recurring patterns, goals, habits, experiments, and tensions without overformalizing every note.",
            "query.md": "Answer with concrete synthesis and actionable follow-up questions when the wiki is thin or fragmented.",
            "lint.md": "Look for recurring topics that deserve pages, stale reflections, and disconnected patterns across notes.",
        },
        "fiction": {
            "ingest.md": "Track characters, locations, themes, plot threads, and chronology without leaking speculative claims as fact.",
            "query.md": "Answer from the maintained narrative wiki and keep chronology or spoiler-sensitive context explicit.",
            "lint.md": "Look for orphan characters, unresolved plot threads, missing location pages, and broken chronology.",
        },
    }
    prompts = domain_prompts[domain]
    return shared | prompts
