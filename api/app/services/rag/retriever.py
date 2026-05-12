from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, Optional

from app.services.rag import index_manager, knowledge_tools
from app.services.rag.schemas import RelatedEntity, RelatedRelation, RetrievalDiagnostics, RetrievalItem, RetrievalSummary, SearchResult


def _tokenize(text: str) -> list[str]:
    return knowledge_tools.tokenize(text) + knowledge_tools._ngram_cjk(text)


def _matches_filters(chunk, filters: Optional[Dict[str, Any]]) -> bool:
    if not filters:
        return True
    datasource = filters.get("datasource")
    if datasource and chunk.datasource != datasource:
        return False
    source_types = filters.get("source_types")
    if source_types and chunk.source_type not in source_types:
        return False
    object_type = filters.get("object_type")
    if object_type and chunk.object_type != object_type:
        return False
    demand_name = filters.get("demand_name")
    if demand_name and chunk.category != demand_name:
        return False
    return True


def _weighted_score(query_tokens: list[str], chunk) -> tuple[float, bool]:
    if not query_tokens:
        return 0.0, False
    title_text = knowledge_tools.normalize_text(chunk.title)
    object_text = knowledge_tools.normalize_text(chunk.object_name or "")
    category_text = knowledge_tools.normalize_text(chunk.category or "")
    path_text = knowledge_tools.normalize_text(chunk.path)
    snippet_text = knowledge_tools.normalize_text(chunk.snippet)
    content_text = knowledge_tools.normalize_text(chunk.content)

    direct_hit = False
    score = 0.0
    for token in set(query_tokens):
        if token in object_text:
            score += 6.0
            direct_hit = True
        elif token in title_text:
            score += 5.0
            direct_hit = True
        elif token in category_text:
            score += 3.5
        elif token in path_text:
            score += 2.5
        elif token in snippet_text:
            score += 1.8
        elif token in content_text:
            score += 1.0

    if chunk.source_type == "schema":
        score += 0.6
    elif chunk.source_type == "demand":
        score += 0.4
    elif chunk.source_type == "lineage":
        score += 0.3

    normalized = round(score / max(len(set(query_tokens)), 1), 4)
    return normalized, direct_hit


def _build_diagnostics(query: str, items: list[RetrievalItem]) -> RetrievalDiagnostics:
    related_entities = [
        RelatedEntity(
            name=item.object_name or item.title,
            entity_type=item.object_type or item.source_type,
            path=item.path,
            score=item.score,
        )
        for item in items[: min(6, len(items))]
    ]
    related_relations: list[RelatedRelation] = []
    query_tokens = set(_tokenize(query))
    for item in items:
        if not item.object_name:
            continue
        if query_tokens & set(_tokenize(item.object_name)):
            related_relations.append(
                RelatedRelation(
                    subject=item.object_name or item.title,
                    predicate="候选命中",
                    object=item.source_type,
                    path=item.path,
                    score=item.score,
                )
            )
        if len(related_relations) >= 4:
            break
    return RetrievalDiagnostics(
        related_entities=related_entities,
        related_relations=related_relations,
    )


def search(
    *,
    query: str,
    wiki_root: str | Path,
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = 8,
) -> SearchResult:
    index_manager.sync_changed_files(wiki_root)
    manifest = index_manager.get_manifest(wiki_root)
    query_tokens = _tokenize(query)
    explicit_object_names = {
        knowledge_tools.compact_text(name)
        for name in knowledge_tools.extract_query_object_names(
            query=query,
            wiki_root=wiki_root,
            datasource=str(filters.get("datasource")) if filters and filters.get("datasource") else None,
            limit=6,
        )
    }
    ranked: list[tuple[float, bool, object]] = []
    for chunk in manifest.chunks:
        if not _matches_filters(chunk, filters):
            continue
        score, direct_hit = _weighted_score(query_tokens, chunk)
        if chunk.object_name and knowledge_tools.compact_text(chunk.object_name) in explicit_object_names:
            score += 2.5
            direct_hit = True
        if chunk.title and knowledge_tools.compact_text(chunk.title) in explicit_object_names:
            score += 2.0
            direct_hit = True
        if score <= 0:
            continue
        ranked.append((score, direct_hit, chunk))

    ranked.sort(key=lambda item: (item[0], item[1], item[2].title, item[2].path), reverse=True)
    selected = ranked[:top_k]
    items = [
        RetrievalItem(
            chunk_id=chunk.chunk_id,
            score=score,
            title=chunk.title,
            path=chunk.path,
            source_type=chunk.source_type,
            datasource=chunk.datasource,
            object_type=chunk.object_type,
            object_name=chunk.object_name,
            snippet=chunk.snippet,
        )
        for score, _, chunk in selected
    ]
    retrieval = RetrievalSummary(
        matched_count=len(ranked),
        direct_hits=sum(1 for _, direct_hit, _ in selected if direct_hit),
        source_types=sorted({item.source_type for item in items}),
        top_k_used=top_k,
    )
    return SearchResult(items=items, retrieval=retrieval, diagnostics=_build_diagnostics(query, items))


def direct_lookup(
    *,
    query: str,
    wiki_root: str | Path,
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = 8,
) -> Optional[SearchResult]:
    datasource = str(filters.get("datasource")) if filters and filters.get("datasource") else None
    result = knowledge_tools.direct_lookup(
        query=query,
        wiki_root=wiki_root,
        datasource=datasource,
        top_k=top_k,
    )
    if result is None:
        return None
    if filters and filters.get("source_types"):
        allowed = set(filters["source_types"])
        result.items = [item for item in result.items if item.source_type in allowed]
        result.retrieval.source_types = sorted({item.source_type for item in result.items})
        result.retrieval.matched_count = len(result.items)
    return result if result.items else None


def rebuild_index(wiki_root: str | Path) -> Dict[str, Any]:
    return index_manager.rebuild_all_indexes(wiki_root)


def index_single_file(wiki_root: str | Path, path: str | Path) -> Dict[str, Any]:
    return index_manager.index_single_file(wiki_root, path)


def remove_deleted_file(wiki_root: str | Path, path: str) -> None:
    index_manager.remove_deleted_file(wiki_root, path)


def sync_changed_files(wiki_root: str | Path) -> Dict[str, int]:
    return index_manager.sync_changed_files(wiki_root)
