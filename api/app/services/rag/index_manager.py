from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from app.services.rag import file_state_store, source_loader
from app.services.rag.schemas import IndexManifest, IndexedChunk


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", lowered)
    return [token for token in tokens if token.strip()]


def _chunk_document(content: str) -> list[str]:
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    sections = re.split(r"\n(?=#)", normalized)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= 900:
            chunks.append(section)
            continue
        paragraphs = [part.strip() for part in section.split("\n\n") if part.strip()]
        current = ""
        for paragraph in paragraphs:
            if not current:
                current = paragraph
                continue
            candidate = f"{current}\n\n{paragraph}"
            if len(candidate) > 900:
                chunks.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            chunks.append(current)
    return chunks


def _build_chunks(wiki_root: str | Path, document) -> list[IndexedChunk]:
    chunks: list[IndexedChunk] = []
    for index, chunk_content in enumerate(_chunk_document(document.content)):
        snippet = re.sub(r"\s+", " ", chunk_content).strip()[:240]
        tokens = _tokenize(" ".join([document.title, document.object_name or "", chunk_content]))
        chunks.append(
            IndexedChunk(
                chunk_id=f"{document.path}#{index}",
                path=document.path,
                absolute_path=document.absolute_path,
                title=document.title,
                source_type=document.source_type,
                datasource=document.datasource,
                object_type=document.object_type,
                object_name=document.object_name,
                category=document.category,
                snippet=snippet,
                content=chunk_content,
                content_hash=document.content_hash,
                mtime=document.mtime,
                tokens=tokens,
            )
        )
    return chunks


def rebuild_all_indexes(wiki_root: str | Path) -> dict[str, int | str]:
    documents = source_loader.load_sources(wiki_root)
    chunks: list[IndexedChunk] = []
    file_states: dict[str, dict[str, float | str]] = {}
    for document in documents:
        chunks.extend(_build_chunks(wiki_root, document))
        file_states[document.path] = {
            "mtime": document.mtime,
            "content_hash": document.content_hash,
        }

    manifest = IndexManifest(
        wiki_root=str(Path(wiki_root).resolve()),
        indexed_at=datetime.now().isoformat(),
        chunks=chunks,
        file_states=file_states,
    )
    file_state_store.save_manifest(wiki_root, manifest)
    return {"indexed_files": len(documents), "indexed_chunks": len(chunks)}


def _load_or_rebuild(wiki_root: str | Path) -> IndexManifest:
    manifest = file_state_store.load_manifest(wiki_root)
    if manifest is not None:
        return manifest
    rebuild_all_indexes(wiki_root)
    manifest = file_state_store.load_manifest(wiki_root)
    assert manifest is not None
    return manifest


def get_manifest(wiki_root: str | Path) -> IndexManifest:
    return _load_or_rebuild(wiki_root)


def detect_changed_files(wiki_root: str | Path) -> dict[str, list[str]]:
    manifest = _load_or_rebuild(wiki_root)
    current_documents = source_loader.load_sources(wiki_root)
    current_states = {
        document.path: {
            "mtime": document.mtime,
            "content_hash": document.content_hash,
        }
        for document in current_documents
    }
    changed = [
        path
        for path, state in current_states.items()
        if manifest.file_states.get(path) != state
    ]
    deleted = [path for path in manifest.file_states if path not in current_states]
    return {"changed": changed, "deleted": deleted}


def remove_deleted_file(wiki_root: str | Path, path: str) -> None:
    manifest = _load_or_rebuild(wiki_root)
    manifest.chunks = [chunk for chunk in manifest.chunks if chunk.path != path]
    manifest.file_states.pop(path, None)
    manifest.indexed_at = datetime.now().isoformat()
    file_state_store.save_manifest(wiki_root, manifest)


def index_single_file(wiki_root: str | Path, path: str | Path) -> dict[str, int | str]:
    manifest = _load_or_rebuild(wiki_root)
    root = Path(wiki_root).resolve()
    absolute_path = Path(path)
    if not absolute_path.is_absolute():
        absolute_path = (root / absolute_path).resolve()

    if not absolute_path.exists():
        relative = absolute_path.relative_to(root).as_posix()
        remove_deleted_file(wiki_root, relative)
        return {"indexed_files": 0, "indexed_chunks": 0}

    document = source_loader.build_source_document(root, absolute_path)
    manifest.chunks = [chunk for chunk in manifest.chunks if chunk.path != document.path]
    new_chunks = _build_chunks(wiki_root, document)
    manifest.chunks.extend(new_chunks)
    manifest.file_states[document.path] = {
        "mtime": document.mtime,
        "content_hash": document.content_hash,
    }
    manifest.indexed_at = datetime.now().isoformat()
    file_state_store.save_manifest(wiki_root, manifest)
    return {"indexed_files": 1, "indexed_chunks": len(new_chunks)}


def sync_changed_files(wiki_root: str | Path) -> dict[str, int]:
    changes = detect_changed_files(wiki_root)
    updated = 0
    removed = 0
    root = Path(wiki_root).resolve()
    for relative_path in changes["changed"]:
        index_single_file(root, relative_path)
        updated += 1
    for relative_path in changes["deleted"]:
        remove_deleted_file(root, relative_path)
        removed += 1
    return {"updated": updated, "removed": removed}
