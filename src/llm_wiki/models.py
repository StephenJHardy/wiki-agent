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
    authors: list[str] = Field(default_factory=list)
    published_at: str | None = None
    published_at_precision: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None


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
    authors: list[str] = Field(default_factory=list)
    published_at: str | None = None
    published_at_precision: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None


class SourceRegistry(BaseModel):
    sources: list[SourceRecord] = Field(default_factory=list)


class ClaimRecord(BaseModel):
    claim_id: str
    text: str
    introduced_by_source_id: str
    source_title: str
    published_at: str | None = None
    published_at_precision: str | None = None
    observed_at: str
    confidence: float = 0.6
    related_pages: list[str] = Field(default_factory=list)
    reinforced_by_source_ids: list[str] = Field(default_factory=list)
    contradicted_by_source_ids: list[str] = Field(default_factory=list)


class ClaimStore(BaseModel):
    claims: list[ClaimRecord] = Field(default_factory=list)


class SourceAnalysis(BaseModel):
    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    published_at: str | None = None
    published_at_precision: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
