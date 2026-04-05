from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .config import DEFAULT_VAULT_DIRNAME, resolve_schema_root


class SchemaConfig(BaseModel):
    domain: str = "general"
    description: str = "General-purpose persistent knowledge wiki."
    preferred_outputs: list[str] = Field(default_factory=lambda: ["markdown"])
    frontmatter_fields: list[str] = Field(
        default_factory=lambda: [
            "title",
            "type",
            "updated_at",
            "source_ids",
            "summary",
            "aliases",
            "tags",
            "related_topics",
        ]
    )
    required_sections: dict[str, list[str]] = Field(default_factory=dict)
    prompt_versions: dict[str, str] = Field(default_factory=lambda: {"ingest": "v1", "query": "v1", "lint": "v1"})


class SchemaBundle(BaseModel):
    config: SchemaConfig
    common_prompt: str = ""
    ingest_prompt: str = ""
    query_prompt: str = ""
    lint_prompt: str = ""
    source_template: str = ""
    entity_template: str = ""
    concept_template: str = ""
    analysis_template: str = ""


def load_schema_bundle(
    *,
    base_path: Path,
    vault_name: str = DEFAULT_VAULT_DIRNAME,
) -> SchemaBundle:
    schema_root = resolve_schema_root(base_path, vault_name)
    config_path = schema_root / "config.yaml"
    if not config_path.exists():
        return SchemaBundle(config=SchemaConfig())

    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = SchemaConfig.model_validate(raw_config)

    return SchemaBundle(
        config=config,
        common_prompt=read_optional_text(schema_root / "prompts/common.md"),
        ingest_prompt=read_optional_text(schema_root / "prompts/ingest.md"),
        query_prompt=read_optional_text(schema_root / "prompts/query.md"),
        lint_prompt=read_optional_text(schema_root / "prompts/lint.md"),
        source_template=read_optional_text(schema_root / "templates/source.md"),
        entity_template=read_optional_text(schema_root / "templates/entity.md"),
        concept_template=read_optional_text(schema_root / "templates/concept.md"),
        analysis_template=read_optional_text(schema_root / "templates/analysis.md"),
    )


def read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
