from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PageType = Literal["overview", "entity", "concept", "source", "analysis"]
SourceFileType = Literal["markdown", "text", "html", "pdf"]


class PageFrontmatter(BaseModel):
    title: str
    type: PageType
    updated_at: str
    source_ids: list[str] = Field(default_factory=list)
    summary: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)
    confidence: float | None = None
    last_reviewed_at: str | None = None
    source_id: str | None = None
    source_path: str | None = None
    derived_path: str | None = None
    original_url: str | None = None
    ingested_at: str | None = None


class WikiPage(BaseModel):
    path: str
    frontmatter: PageFrontmatter
    body: str


class SourceRecord(BaseModel):
    source_id: str
    title: str
    path: str
    checksum: str
    file_type: SourceFileType
    extracted_path: str | None = None
    original_url: str | None = None
    ingested_at: str
    updated_at: str


class SourceRegistry(BaseModel):
    sources: list[SourceRecord] = Field(default_factory=list)


class SourceAnalysis(BaseModel):
    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
