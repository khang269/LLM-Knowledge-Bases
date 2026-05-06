from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# --- LLM Output Schemas ---

class AnalysisResult(BaseModel):
    summary: str = Field(description="A concise summary of the note.")
    key_concepts: List[str] = Field(description="Extracted key concepts (3-8 max). Must be highly specific, valid, non-empty strings. Do not return null.")
    suggested_topics: List[str] = Field(description="Broader suggested topics.", default_factory=list)
    quality: str = Field(description="Quality of the source: high, medium, low", default="medium")
    language: Optional[str] = Field(description="Detected ISO 639-1 language code (e.g. 'en').", default=None)

class SingleArticle(BaseModel):
    title: str = Field(description="The title of the article.")
    content: str = Field(description="The markdown content of the article.")
    tags: List[str] = Field(description="Tags for the article.")

class ConnectionArticle(BaseModel):
    title: str = Field(description="The title of the connection article (e.g. 'Connection: X and Y')")
    connects: List[str] = Field(description="List of concept names this article connects")
    summary: str = Field(description="A 1-sentence summary of why these concepts are connected")

class CompileResult(BaseModel):
    article: SingleArticle = Field(description="The compiled concept article")
    connections: List[ConnectionArticle] = Field(default_factory=list, description="Cross-cutting insights linking this concept to others, if discovered in the sources")

class LintIssue(BaseModel):
    path: str
    issue_type: str
    description: str
    suggestion: str
    auto_fixable: bool = False

class LintResult(BaseModel):
    issues: List[LintIssue]
    health_score: float
    summary: str

# --- State DB Records ---

class RawNoteRecord(BaseModel):
    path: str
    content_hash: str
    status: str = "new"  # new, ingested, compiled, failed
    summary: Optional[str] = None
    quality: Optional[str] = None
    language: Optional[str] = None
    error: Optional[str] = None
    ingested_at: Optional[datetime] = None

class WikiArticleRecord(BaseModel):
    path: str
    title: str
    sources: List[str]
    content_hash: str
    is_draft: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
