from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    ensure_directory(path.parent)
    path.write_bytes(content)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_directory(path.parent)
    path.write_text(render_json(payload), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def compute_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "untitled"
