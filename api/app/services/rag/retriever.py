from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.rag.backends import RAGBackend, build_rag_backend
from app.services.rag.schemas import SearchResult


@lru_cache(maxsize=4)
def _get_backend(backend_name: str) -> RAGBackend:
    return build_rag_backend(backend_name)


def _resolve_backend_name(backend_name: Optional[str]) -> str:
    return (backend_name or settings.RAG_RETRIEVAL_BACKEND or "local").strip().lower()


def search(
    *,
    query: str,
    wiki_root: str | Path,
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = 8,
    backend_name: Optional[str] = None,
) -> SearchResult:
    return _get_backend(_resolve_backend_name(backend_name)).search(
        query=query,
        wiki_root=wiki_root,
        filters=filters,
        top_k=top_k,
    )


def ask(
    *,
    query: str,
    wiki_root: str | Path,
    filters: Optional[Dict[str, Any]] = None,
    top_k: int = 8,
    backend_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return _get_backend(_resolve_backend_name(backend_name)).ask(
        query=query,
        wiki_root=wiki_root,
        filters=filters,
        top_k=top_k,
    )


def rebuild_index(wiki_root: str | Path, backend_name: Optional[str] = None) -> Dict[str, Any]:
    return _get_backend(_resolve_backend_name(backend_name)).rebuild_index(wiki_root)


def index_single_file(wiki_root: str | Path, path: str | Path, backend_name: Optional[str] = None) -> Dict[str, Any]:
    return _get_backend(_resolve_backend_name(backend_name)).index_single_file(wiki_root, path)


def remove_deleted_file(wiki_root: str | Path, path: str, backend_name: Optional[str] = None) -> None:
    _get_backend(_resolve_backend_name(backend_name)).remove_deleted_file(wiki_root, path)


def sync_changed_files(wiki_root: str | Path, backend_name: Optional[str] = None) -> Dict[str, int]:
    return _get_backend(_resolve_backend_name(backend_name)).sync_changed_files(wiki_root)
