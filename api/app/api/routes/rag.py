from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session
from typing import List, Optional

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.services import setting_service
from app.services.rag import context_assembler, hermes_answer_service, retriever

router = APIRouter(prefix="/rag", tags=["rag"], dependencies=[Depends(get_current_user)])


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    datasource: Optional[str] = None
    source_types: Optional[List[str]] = None
    demand_name: Optional[str] = None
    object_type: Optional[str] = None
    top_k: int = Field(default=8, ge=1, le=20)


class RagSearchItem(BaseModel):
    chunk_id: str
    score: float
    title: str
    path: str
    source_type: str
    datasource: str
    object_type: Optional[str] = None
    object_name: Optional[str] = None
    snippet: str


class RagRetrievalResponse(BaseModel):
    matched_count: int
    direct_hits: int
    source_types: List[str]
    top_k_used: int


class RagRelatedEntityResponse(BaseModel):
    name: str
    entity_type: str
    path: str
    score: float


class RagRelatedRelationResponse(BaseModel):
    subject: str
    predicate: str
    object: str
    path: str
    score: float


class RagDiagnosticsResponse(BaseModel):
    related_entities: List[RagRelatedEntityResponse]
    related_relations: List[RagRelatedRelationResponse]


class RagSearchResponse(BaseModel):
    items: List[RagSearchItem]
    retrieval: RagRetrievalResponse
    diagnostics: RagDiagnosticsResponse


class RagAskResponse(BaseModel):
    answer: str
    sources: List[RagSearchItem]
    retrieval: RagRetrievalResponse
    diagnostics: RagDiagnosticsResponse


def _get_wiki_root(session: Session) -> str:
    return setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)


def _build_filters(payload: RagSearchRequest) -> dict:
    filters: dict[str, object] = {}
    if payload.datasource:
        filters["datasource"] = payload.datasource
    if payload.source_types:
        filters["source_types"] = payload.source_types
    if payload.demand_name:
        filters["demand_name"] = payload.demand_name
    if payload.object_type:
        filters["object_type"] = payload.object_type
    return filters


@router.post("/search", response_model=RagSearchResponse)
def rag_search(payload: RagSearchRequest, session: Session = Depends(get_session)):
    wiki_root = _get_wiki_root(session)
    result = retriever.search(
        query=payload.query,
        wiki_root=wiki_root,
        filters=_build_filters(payload),
        top_k=payload.top_k,
    )
    return result.model_dump()


@router.post("/ask", response_model=RagAskResponse)
def rag_ask(payload: RagSearchRequest, session: Session = Depends(get_session)):
    wiki_root = _get_wiki_root(session)
    filters = _build_filters(payload)
    remote_result = retriever.ask(
        query=payload.query,
        wiki_root=wiki_root,
        filters=filters,
        top_k=payload.top_k,
    )
    if remote_result:
        return remote_result

    search_result = retriever.search(
        query=payload.query,
        wiki_root=wiki_root,
        filters=filters,
        top_k=payload.top_k,
    )
    assembled = context_assembler.assemble_context(payload.query, search_result)
    try:
        answer_result = hermes_answer_service.answer_with_hermes(
            payload.query,
            assembled,
            {"retrieval": search_result.retrieval, "diagnostics": search_result.diagnostics},
        )
    except Exception as exc:
        answer_result = {
            "answer": f"问答生成失败：{exc}",
            "sources": assembled.sources,
        }

    return {
        "answer": answer_result["answer"],
        "sources": [item.model_dump() for item in answer_result["sources"]],
        "retrieval": search_result.retrieval.model_dump(),
        "diagnostics": search_result.diagnostics.model_dump(),
    }


@router.post("/index/rebuild")
def rebuild_rag_index(session: Session = Depends(get_session)):
    wiki_root = _get_wiki_root(session)
    try:
        return retriever.rebuild_index(wiki_root)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"重建问答索引失败: {exc}") from exc
