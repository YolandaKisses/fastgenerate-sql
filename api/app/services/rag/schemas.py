from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

SourceType = Literal["wiki", "schema", "lineage", "log", "demand"]


class SourceDocument(BaseModel):
    path: str
    absolute_path: str
    title: str
    source_type: SourceType
    datasource: str
    object_type: Optional[str] = None
    object_name: Optional[str] = None
    category: Optional[str] = None
    content: str
    content_hash: str
    mtime: float

    @property
    def path_obj(self) -> Path:
        return Path(self.absolute_path)


class IndexedChunk(BaseModel):
    chunk_id: str
    path: str
    absolute_path: str
    title: str
    source_type: SourceType
    datasource: str
    object_type: Optional[str] = None
    object_name: Optional[str] = None
    category: Optional[str] = None
    snippet: str
    content: str
    content_hash: str
    mtime: float
    tokens: List[str] = Field(default_factory=list)


class RetrievalItem(BaseModel):
    chunk_id: str
    score: float
    title: str
    path: str
    source_type: SourceType
    datasource: str
    object_type: Optional[str] = None
    object_name: Optional[str] = None
    snippet: str


class RelatedEntity(BaseModel):
    name: str
    entity_type: str
    path: str
    score: float


class RelatedRelation(BaseModel):
    subject: str
    predicate: str
    object: str
    path: str
    score: float


class RetrievalDiagnostics(BaseModel):
    related_entities: List[RelatedEntity] = Field(default_factory=list)
    related_relations: List[RelatedRelation] = Field(default_factory=list)


class RetrievalSummary(BaseModel):
    matched_count: int
    direct_hits: int
    source_types: List[SourceType]
    top_k_used: int


class SearchResult(BaseModel):
    items: List[RetrievalItem]
    retrieval: RetrievalSummary
    diagnostics: RetrievalDiagnostics = Field(default_factory=RetrievalDiagnostics)


class ContextBucket(BaseModel):
    label: str
    items: List[RetrievalItem]


class AssembledContext(BaseModel):
    query: str
    sources: List[RetrievalItem]
    buckets: List[ContextBucket]
    prompt_context: str
    prompt_text: str = ""


class IndexManifest(BaseModel):
    wiki_root: str
    indexed_at: str
    chunks: List[IndexedChunk] = Field(default_factory=list)
    file_states: Dict[str, Dict[str, object]] = Field(default_factory=dict)
