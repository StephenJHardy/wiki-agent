from __future__ import annotations

from pydantic import BaseModel, Field


class StructuredIngestAnalysis(BaseModel):
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


class StructuredQuerySynthesis(BaseModel):
    answer: str
    uncertainty_notes: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class StructuredLintReview(BaseModel):
    contradictions: list[str] = Field(default_factory=list)
    stale_claims: list[str] = Field(default_factory=list)
    missing_pages: list[str] = Field(default_factory=list)
    missing_cross_references: list[str] = Field(default_factory=list)
    research_gaps: list[str] = Field(default_factory=list)
