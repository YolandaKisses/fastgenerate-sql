from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.services.rag import index_manager
from app.services.rag.lightrag_client import LocalLightRAGClient
from app.services.rag.schemas import RetrievalDiagnostics, RetrievalItem, RetrievalSummary, SearchResult


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())


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


def _score_chunk(query: str, query_tokens: List[str], chunk) -> Tuple[float, bool]:
    if not query_tokens:
        return 0.0, False
    overlap = sum(1 for token in query_tokens if token in chunk.tokens)
    query_text = query.lower()
    direct_hit = False
    if chunk.title.lower() in query_text or (chunk.object_name and chunk.object_name.lower() in query_text):
        overlap += 3
        direct_hit = True
    if any(token in chunk.title.lower() for token in query_tokens):
        overlap += 1
    if any(token in chunk.snippet.lower() for token in query_tokens):
        overlap += 0.5
    normalized = overlap / max(len(set(query_tokens)), 1)
    return round(normalized, 4), direct_hit


class RAGBackend(ABC):
    backend_name: str

    @abstractmethod
    def search(
        self,
        *,
        query: str,
        wiki_root: str | Path,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8,
    ) -> SearchResult:
        raise NotImplementedError

    def ask(
        self,
        *,
        query: str,
        wiki_root: str | Path,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8,
    ) -> Optional[Dict[str, Any]]:
        return None

    @abstractmethod
    def rebuild_index(self, wiki_root: str | Path) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def index_single_file(self, wiki_root: str | Path, path: str | Path) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def remove_deleted_file(self, wiki_root: str | Path, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def sync_changed_files(self, wiki_root: str | Path) -> Dict[str, int]:
        raise NotImplementedError


class LocalFallbackBackend(RAGBackend):
    backend_name = "local"

    def __init__(self) -> None:
        self._client = LocalLightRAGClient()

    def search(
        self,
        *,
        query: str,
        wiki_root: str | Path,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8,
    ) -> SearchResult:
        self.sync_changed_files(wiki_root)
        query_tokens = _tokenize(query)
        ranked: List[Tuple[float, bool, object]] = []
        for chunk in self._client.search_chunks(str(wiki_root), query):
            if not _matches_filters(chunk, filters):
                continue
            score, direct_hit = _score_chunk(query, query_tokens, chunk)
            if score <= 0:
                continue
            ranked.append((score, direct_hit, chunk))
        ranked.sort(key=lambda item: (item[0], item[1], item[2].title), reverse=True)
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
        diagnostics = RetrievalDiagnostics(
            related_entities=self._client.get_related_entities(str(wiki_root), query),
            related_relations=self._client.get_related_relations(str(wiki_root), query),
        )
        retrieval = RetrievalSummary(
            matched_count=len(ranked),
            direct_hits=sum(1 for _, direct_hit, _ in selected if direct_hit),
            source_types=sorted({item.source_type for item in items}),
            top_k_used=top_k,
        )
        return SearchResult(items=items, retrieval=retrieval, diagnostics=diagnostics)

    def rebuild_index(self, wiki_root: str | Path) -> Dict[str, Any]:
        return index_manager.rebuild_all_indexes(wiki_root)

    def index_single_file(self, wiki_root: str | Path, path: str | Path) -> Dict[str, Any]:
        return index_manager.index_single_file(wiki_root, path)

    def remove_deleted_file(self, wiki_root: str | Path, path: str) -> None:
        index_manager.remove_deleted_file(wiki_root, path)

    def sync_changed_files(self, wiki_root: str | Path) -> Dict[str, int]:
        return index_manager.sync_changed_files(wiki_root)


class LightRAGHTTPBackend(RAGBackend):
    backend_name = "lightrag"

    def __init__(self) -> None:
        self._fallback = LocalFallbackBackend()

    def _is_configured(self) -> bool:
        return bool(settings.LIGHTRAG_BASE_URL.strip())

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.LIGHTRAG_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LIGHTRAG_API_KEY}"
        return headers

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._is_configured():
            raise RuntimeError("LIGHTRAG_BASE_URL 未配置")
        base_url = settings.LIGHTRAG_BASE_URL.rstrip("/")
        with httpx.Client(timeout=settings.LIGHTRAG_TIMEOUT_SECONDS) as client:
            response = client.request(
                method,
                f"{base_url}{path}",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    def _normalize_search_result(self, data: Dict[str, Any], top_k: int) -> SearchResult:
        raw_items = data.get("items") or data.get("results") or data.get("chunks") or []
        items: List[RetrievalItem] = []
        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                continue
            path = (
                item.get("path")
                or item.get("source_path")
                or item.get("file_path")
                or item.get("metadata", {}).get("path")
                or ""
            )
            source_type = (
                item.get("source_type")
                or item.get("metadata", {}).get("source_type")
                or "wiki"
            )
            datasource = (
                item.get("datasource")
                or item.get("metadata", {}).get("datasource")
                or "unknown"
            )
            items.append(
                RetrievalItem(
                    chunk_id=str(item.get("chunk_id") or item.get("id") or f"remote-{idx}"),
                    score=float(item.get("score") or item.get("similarity") or 0),
                    title=str(item.get("title") or item.get("name") or item.get("metadata", {}).get("title") or Path(path).stem or f"result-{idx}"),
                    path=str(path),
                    source_type=str(source_type),
                    datasource=str(datasource),
                    object_type=item.get("object_type") or item.get("metadata", {}).get("object_type"),
                    object_name=item.get("object_name") or item.get("metadata", {}).get("object_name"),
                    snippet=str(item.get("snippet") or item.get("content") or item.get("text") or ""),
                )
            )

        raw_retrieval = data.get("retrieval") or {}
        retrieval = RetrievalSummary(
            matched_count=int(raw_retrieval.get("matched_count") or len(raw_items)),
            direct_hits=int(raw_retrieval.get("direct_hits") or 0),
            source_types=list(raw_retrieval.get("source_types") or sorted({item.source_type for item in items})),
            top_k_used=int(raw_retrieval.get("top_k_used") or top_k),
        )
        raw_diagnostics = data.get("diagnostics") or {}
        diagnostics = RetrievalDiagnostics.model_validate(
            {
                "related_entities": raw_diagnostics.get("related_entities") or [],
                "related_relations": raw_diagnostics.get("related_relations") or [],
            }
        )
        return SearchResult(items=items, retrieval=retrieval, diagnostics=diagnostics)

    def _normalize_remote_ask_result(self, data: Dict[str, Any], top_k: int) -> Dict[str, Any]:
        search_result = self._normalize_search_result(data, top_k)
        answer = str(data.get("answer") or data.get("response") or data.get("message") or "").strip()
        return {
            "answer": answer,
            "sources": [item.model_dump() for item in search_result.items],
            "retrieval": search_result.retrieval.model_dump(),
            "diagnostics": search_result.diagnostics.model_dump(),
        }

    def search(
        self,
        *,
        query: str,
        wiki_root: str | Path,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8,
    ) -> SearchResult:
        self.sync_changed_files(wiki_root)
        try:
            payload = {
                "query": query,
                "filters": filters or {},
                "top_k": top_k,
                "wiki_root": str(Path(wiki_root).resolve()),
            }
            data = self._request("POST", settings.LIGHTRAG_SEARCH_PATH, payload)
            return self._normalize_search_result(data, top_k)
        except Exception:
            return self._fallback.search(query=query, wiki_root=wiki_root, filters=filters, top_k=top_k)

    def ask(
        self,
        *,
        query: str,
        wiki_root: str | Path,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8,
    ) -> Optional[Dict[str, Any]]:
        if not settings.LIGHTRAG_ENABLE_REMOTE_ASK:
            return None
        try:
            payload = {
                "query": query,
                "filters": filters or {},
                "top_k": top_k,
                "wiki_root": str(Path(wiki_root).resolve()),
            }
            data = self._request("POST", settings.LIGHTRAG_ASK_PATH, payload)
            return self._normalize_remote_ask_result(data, top_k)
        except Exception:
            return None

    def rebuild_index(self, wiki_root: str | Path) -> Dict[str, Any]:
        local_result = self._fallback.rebuild_index(wiki_root)
        if not settings.LIGHTRAG_ENABLE_REMOTE_REBUILD:
            return {"backend": self.backend_name, "mode": "local-only", **local_result}
        try:
            remote = self._request(
                "POST",
                settings.LIGHTRAG_REBUILD_PATH,
                {"wiki_root": str(Path(wiki_root).resolve())},
            )
            return {"backend": self.backend_name, "mode": "hybrid", "local": local_result, "remote": remote}
        except Exception as exc:
            return {"backend": self.backend_name, "mode": "fallback", "local": local_result, "remote_error": str(exc)}

    def index_single_file(self, wiki_root: str | Path, path: str | Path) -> Dict[str, Any]:
        local_result = self._fallback.index_single_file(wiki_root, path)
        if not settings.LIGHTRAG_ENABLE_REMOTE_REBUILD:
            return local_result
        try:
            root = Path(wiki_root).resolve()
            absolute_path = Path(path)
            if not absolute_path.is_absolute():
                absolute_path = (root / absolute_path).resolve()
            relative_path = absolute_path.relative_to(root).as_posix()
            self._request(
                "POST",
                settings.LIGHTRAG_UPSERT_PATH,
                {
                    "wiki_root": str(Path(wiki_root).resolve()),
                    "path": relative_path,
                },
            )
        except Exception:
            pass
        return local_result

    def remove_deleted_file(self, wiki_root: str | Path, path: str) -> None:
        self._fallback.remove_deleted_file(wiki_root, path)
        if not settings.LIGHTRAG_ENABLE_REMOTE_REBUILD:
            return
        try:
            self._request(
                "POST",
                settings.LIGHTRAG_DELETE_PATH,
                {
                    "wiki_root": str(Path(wiki_root).resolve()),
                    "path": path,
                },
            )
        except Exception:
            pass

    def sync_changed_files(self, wiki_root: str | Path) -> Dict[str, int]:
        return self._fallback.sync_changed_files(wiki_root)


def build_rag_backend(backend_name: Optional[str]) -> RAGBackend:
    normalized = (backend_name or settings.RAG_RETRIEVAL_BACKEND or "local").strip().lower()
    if normalized == "lightrag":
        return LightRAGHTTPBackend()
    return LocalFallbackBackend()
