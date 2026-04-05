from __future__ import annotations

from pathlib import Path

import yaml

from .models import PageFrontmatter, WikiPage


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text.strip()

    marker = "\n---\n"
    end_index = text.find(marker, 4)
    if end_index == -1:
        return {}, text.strip()

    raw_frontmatter = text[4:end_index]
    body = text[end_index + len(marker) :].strip()
    payload = yaml.safe_load(raw_frontmatter) or {}
    if not isinstance(payload, dict):
        raise ValueError("Frontmatter must parse to a mapping.")
    return payload, body


def render_page(frontmatter: PageFrontmatter, body: str) -> str:
    yaml_payload = yaml.safe_dump(
        frontmatter.model_dump(exclude_none=True),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=False,
    ).strip()
    return f"---\n{yaml_payload}\n---\n\n{body.strip()}\n"


def load_page(path: Path) -> WikiPage:
    raw_text = path.read_text(encoding="utf-8")
    frontmatter_data, body = parse_frontmatter(raw_text)
    return WikiPage(
        path=str(path),
        frontmatter=PageFrontmatter.model_validate(frontmatter_data),
        body=body,
    )
