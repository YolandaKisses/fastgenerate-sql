from __future__ import annotations

from pathlib import Path
import re
from typing import Dict, List, Optional

from app.services.rag import index_manager, source_loader
from app.services.rag.schemas import RelatedEntity, RelatedRelation, RetrievalDiagnostics, RetrievalItem, RetrievalSummary, SearchResult, SourceDocument


def normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    lowered = lowered.replace("（", "(").replace("）", ")")
    return lowered


def compact_text(text: str) -> str:
    normalized = normalize_text(text)
    return re.sub(r"[\s_\-./]+", "", normalized)


def tokenize(text: str) -> List[str]:
    lowered = normalize_text(text)
    latin_tokens = re.findall(r"[a-z0-9_]+", lowered)
    cjk_words = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    return [token for token in latin_tokens + cjk_words + cjk_chars if token.strip()]


def _ngram_cjk(text: str) -> List[str]:
    chars = re.findall(r"[\u4e00-\u9fff]", normalize_text(text))
    return ["".join(chars[index : index + 2]) for index in range(max(len(chars) - 1, 0))]


def _load_documents(wiki_root: str | Path) -> List[SourceDocument]:
    return source_loader.load_sources(wiki_root)


def _matches_datasource(document: SourceDocument, datasource: Optional[str]) -> bool:
    return not datasource or document.datasource == datasource


def find_explicit_documents(
    *,
    query: str,
    wiki_root: str | Path,
    datasource: Optional[str] = None,
    limit: int = 6,
) -> List[SourceDocument]:
    normalized_query = normalize_text(query)
    compact_query = compact_text(query)
    query_tokens = set(tokenize(query) + _ngram_cjk(query))
    matches: List[tuple[int, SourceDocument]] = []
    for document in _load_documents(wiki_root):
        if not _matches_datasource(document, datasource):
            continue
        score = 0
        candidates = [document.title, document.object_name or "", document.category or "", Path(document.path).stem]
        for candidate in candidates:
            normalized_candidate = normalize_text(candidate)
            compact_candidate = compact_text(candidate)
            if not normalized_candidate:
                continue
            candidate_tokens = set(tokenize(candidate) + _ngram_cjk(candidate))
            if normalized_candidate and normalized_candidate in normalized_query:
                score += 8
            if compact_candidate and compact_candidate in compact_query:
                score += 9
            if query_tokens & candidate_tokens:
                score += 3
        if document.object_name and compact_text(document.object_name) in compact_query:
            score += 6
        if score > 0:
            matches.append((score, document))
    matches.sort(key=lambda item: (item[0], item[1].title, item[1].path), reverse=True)
    deduped: List[SourceDocument] = []
    seen_paths: set[str] = set()
    for _, document in matches:
        if document.path in seen_paths:
            continue
        seen_paths.add(document.path)
        deduped.append(document)
        if len(deduped) >= limit:
            break
    return deduped


def search_lineage_documents(
    *,
    entity_names: List[str],
    wiki_root: str | Path,
    datasource: Optional[str] = None,
    limit: int = 4,
) -> List[SourceDocument]:
    entity_terms = [normalize_text(item) for item in entity_names if item.strip()]
    if not entity_terms:
        return []
    matches: List[tuple[int, SourceDocument]] = []
    for document in _load_documents(wiki_root):
        if document.source_type != "lineage" or not _matches_datasource(document, datasource):
            continue
        content = normalize_text(document.content)
        score = 0
        for term in entity_terms:
            if term and term in content:
                score += 4
        if score > 0:
            matches.append((score, document))
    matches.sort(key=lambda item: (item[0], item[1].title), reverse=True)
    return [document for _, document in matches[:limit]]


def read_document(document: SourceDocument) -> RetrievalItem:
    snippet = re.sub(r"\s+", " ", document.content).strip()[:240]
    return RetrievalItem(
        chunk_id=f"{document.path}#doc",
        score=1.0,
        title=document.title,
        path=document.path,
        source_type=document.source_type,
        datasource=document.datasource,
        object_type=document.object_type,
        object_name=document.object_name,
        snippet=snippet,
    )


def direct_lookup(
    *,
    query: str,
    wiki_root: str | Path,
    datasource: Optional[str] = None,
    top_k: int = 8,
) -> Optional[SearchResult]:
    explicit_docs = find_explicit_documents(query=query, wiki_root=wiki_root, datasource=datasource, limit=max(top_k, 4))
    if not explicit_docs:
        return None

    entity_names = [document.object_name or document.title for document in explicit_docs]
    lineage_docs = search_lineage_documents(
        entity_names=entity_names,
        wiki_root=wiki_root,
        datasource=datasource,
        limit=max(1, min(3, top_k // 2 or 1)),
    )
    ordered_docs = explicit_docs + [document for document in lineage_docs if document.path not in {item.path for item in explicit_docs}]
    items = [read_document(document) for document in ordered_docs[:top_k]]
    diagnostics = RetrievalDiagnostics(
        related_entities=[
            RelatedEntity(
                name=document.object_name or document.title,
                entity_type=document.object_type or document.source_type,
                path=document.path,
                score=1.0,
            )
            for document in explicit_docs[:top_k]
        ],
        related_relations=[
            RelatedRelation(
                subject=document.title,
                predicate="命中",
                object=document.object_name or document.title,
                path=document.path,
                score=1.0,
            )
            for document in lineage_docs[:3]
        ],
    )
    retrieval = RetrievalSummary(
        matched_count=len(items),
        direct_hits=len(explicit_docs[:top_k]),
        source_types=sorted({item.source_type for item in items}),
        top_k_used=top_k,
    )
    return SearchResult(items=items, retrieval=retrieval, diagnostics=diagnostics)


def get_manifest_documents(wiki_root: str | Path) -> Dict[str, SourceDocument]:
    documents = _load_documents(wiki_root)
    return {document.path: document for document in documents}


def extract_query_object_names(
    *,
    query: str,
    wiki_root: str | Path,
    datasource: Optional[str] = None,
    limit: int = 4,
) -> List[str]:
    compact_query = compact_text(query)
    normalized_query = normalize_text(query)
    matches: List[tuple[int, str]] = []
    seen: set[str] = set()
    for document in _load_documents(wiki_root):
        if not _matches_datasource(document, datasource):
            continue
        object_name = document.object_name or document.title
        if not object_name or object_name in seen:
            continue
        score = 0
        if compact_text(object_name) and compact_text(object_name) in compact_query:
            score += 10
        if normalize_text(object_name) in normalized_query:
            score += 8
        title = document.title
        if title and compact_text(title) in compact_query:
            score += 8
        if score > 0:
            matches.append((score, object_name))
            seen.add(object_name)
    matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [name for _, name in matches[:limit]]
