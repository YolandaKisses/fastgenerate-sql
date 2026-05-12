from __future__ import annotations

from collections import Counter
import re
from typing import List, Tuple

from app.services.rag import index_manager
from app.services.rag.schemas import IndexedChunk, RelatedEntity, RelatedRelation


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())


def _split_cjk_terms(query: str) -> List[str]:
    candidates = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    return [item for item in candidates if item.strip()]


def _match_score(query_tokens: List[str], text: str, base_tokens: List[str]) -> float:
    if not query_tokens:
        return 0.0
    token_counts = Counter(base_tokens)
    overlap = sum(1 for token in query_tokens if token in token_counts)
    lowered = text.lower()
    cjk_bonus = sum(1 for term in _split_cjk_terms(" ".join(query_tokens)) if term in lowered)
    return round((overlap + cjk_bonus) / max(len(set(query_tokens)), 1), 4)


def _extract_relations(chunk: IndexedChunk) -> List[Tuple[str, str, str]]:
    relations: List[Tuple[str, str, str]] = []
    title = chunk.object_name or chunk.title
    if not title:
        return relations
    lines = [line.strip() for line in chunk.content.splitlines() if line.strip()]
    patterns = [
        (r"(.+?)关联(.+)", "关联"),
        (r"(.+?)依赖(.+)", "依赖"),
        (r"(.+?)来源于(.+)", "来源于"),
        (r"(.+?)使用(.+)", "使用"),
        (r"(.+?)JOIN\s+(.+)", "join"),
    ]
    for line in lines:
        for pattern, predicate in patterns:
            match = re.search(pattern, line, flags=re.IGNORECASE)
            if not match:
                continue
            left = match.group(1).strip(" -:：")
            right = match.group(2).strip(" -:：")
            if predicate == "join":
                left = title
            if left and right:
                relations.append((left, predicate, right[:120]))
            break
    return relations


class LocalLightRAGClient:
    def search_chunks(self, wiki_root: str, query: str) -> List[IndexedChunk]:
        manifest = index_manager.get_manifest(wiki_root)
        query_tokens = _tokenize(query)
        ranked: List[Tuple[float, IndexedChunk]] = []
        for chunk in manifest.chunks:
            score = _match_score(query_tokens, f"{chunk.title}\n{chunk.content}", chunk.tokens)
            if score > 0:
                ranked.append((score, chunk))
        ranked.sort(key=lambda item: (item[0], item[1].title), reverse=True)
        return [chunk for _, chunk in ranked]

    def get_related_entities(self, wiki_root: str, query: str, limit: int = 8) -> List[RelatedEntity]:
        manifest = index_manager.get_manifest(wiki_root)
        query_tokens = _tokenize(query)
        ranked: List[RelatedEntity] = []
        seen: set[tuple[str, str]] = set()
        for chunk in manifest.chunks:
            entity_name = chunk.object_name or chunk.title
            if not entity_name:
                continue
            score = _match_score(query_tokens, entity_name, _tokenize(entity_name))
            if score <= 0:
                continue
            dedupe_key = (entity_name, chunk.path)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            ranked.append(
                RelatedEntity(
                    name=entity_name,
                    entity_type=chunk.object_type or chunk.source_type,
                    path=chunk.path,
                    score=score,
                )
            )
        ranked.sort(key=lambda item: (item.score, item.name), reverse=True)
        return ranked[:limit]

    def get_related_relations(self, wiki_root: str, query: str, limit: int = 8) -> List[RelatedRelation]:
        manifest = index_manager.get_manifest(wiki_root)
        query_tokens = _tokenize(query)
        ranked: List[RelatedRelation] = []
        seen: set[tuple[str, str, str, str]] = set()
        for chunk in manifest.chunks:
            for subject, predicate, obj in _extract_relations(chunk):
                text = f"{subject} {predicate} {obj}"
                score = _match_score(query_tokens, text, _tokenize(text))
                if score <= 0:
                    continue
                dedupe_key = (subject, predicate, obj, chunk.path)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                ranked.append(
                    RelatedRelation(
                        subject=subject,
                        predicate=predicate,
                        object=obj,
                        path=chunk.path,
                        score=score,
                    )
                )
        ranked.sort(key=lambda item: (item.score, item.subject), reverse=True)
        return ranked[:limit]
