from __future__ import annotations

from pathlib import Path

APP_NAME = "llm-wiki"
DEFAULT_VAULT_DIRNAME = "vault"
WIKI_SECTION_DIRECTORY: dict[str, str] = {
    "overview": "overviews",
    "entity": "entities",
    "concept": "concepts",
    "source": "sources",
    "analysis": "analyses",
}

VAULT_DIRECTORIES = (
    "raw/sources",
    "raw/assets",
    "schema/prompts",
    "schema/templates",
    "wiki/overviews",
    "wiki/entities",
    "wiki/concepts",
    "wiki/sources",
    "wiki/analyses",
    "state",
    "state/extracted",
    "state/issues",
    "state/operations",
    "state/reviews/pending",
    "state/reviews/applied",
    "state/reviews/rejected",
)


def resolve_vault_root(base_path: Path, vault_name: str = DEFAULT_VAULT_DIRNAME) -> Path:
    return base_path / vault_name


def resolve_source_root(base_path: Path, vault_name: str = DEFAULT_VAULT_DIRNAME) -> Path:
    return resolve_vault_root(base_path, vault_name) / "raw/sources"


def resolve_wiki_root(base_path: Path, vault_name: str = DEFAULT_VAULT_DIRNAME) -> Path:
    return resolve_vault_root(base_path, vault_name) / "wiki"


def resolve_state_root(base_path: Path, vault_name: str = DEFAULT_VAULT_DIRNAME) -> Path:
    return resolve_vault_root(base_path, vault_name) / "state"


def resolve_extracted_root(base_path: Path, vault_name: str = DEFAULT_VAULT_DIRNAME) -> Path:
    return resolve_state_root(base_path, vault_name) / "extracted"


def resolve_schema_root(base_path: Path, vault_name: str = DEFAULT_VAULT_DIRNAME) -> Path:
    return resolve_vault_root(base_path, vault_name) / "schema"
