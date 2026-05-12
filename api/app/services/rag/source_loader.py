from __future__ import annotations

from hashlib import sha1
from pathlib import Path

from app.services.rag.schemas import SourceDocument


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    raw = content[4:end]
    body = content[end + 5 :]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data, body


def _infer_source_type(relative_path: Path) -> tuple[str, str | None, str | None]:
    parts = relative_path.parts
    bucket = parts[1] if len(parts) > 1 else ""
    if bucket == "demand":
        category = parts[2] if len(parts) > 2 else None
        return "demand", "table", category
    if bucket in {"tables", "views", "routines"}:
        object_type = "table" if bucket == "tables" else bucket[:-1]
        return "schema", object_type, None
    if bucket in {"terms", "metrics"}:
        return "wiki", bucket[:-1], None
    if "lineage" in parts:
        return "lineage", "lineage", None
    if "log" in parts or "logs" in parts:
        return "log", "log", None
    return "wiki", "document", None


def _resolve_title(frontmatter: dict, path: Path) -> str:
    for key in ("title", "name", "object_name"):
        value = frontmatter.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return path.stem


def build_source_document(wiki_root: str | Path, file_path: str | Path) -> SourceDocument:
    root = Path(wiki_root).resolve()
    absolute_path = Path(file_path).resolve()
    relative_path = absolute_path.relative_to(root)
    content = absolute_path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(content)
    source_type, object_type, category = _infer_source_type(relative_path)
    title = _resolve_title(frontmatter, absolute_path)
    datasource = relative_path.parts[0] if relative_path.parts else "unknown"
    object_name = frontmatter.get("object_name") or frontmatter.get("table_name") or title
    stat = absolute_path.stat()

    return SourceDocument(
        path=relative_path.as_posix(),
        absolute_path=str(absolute_path),
        title=title,
        source_type=source_type,
        datasource=datasource,
        object_type=object_type,
        object_name=str(object_name) if object_name else None,
        category=category,
        content=body.strip() or content.strip(),
        content_hash=sha1(content.encode("utf-8")).hexdigest(),
        mtime=stat.st_mtime,
    )


def load_sources(wiki_root: str | Path) -> list[SourceDocument]:
    root = Path(wiki_root)
    if not root.exists():
        return []
    documents: list[SourceDocument] = []
    for file_path in sorted(root.rglob("*.md")):
        if ".vuepress" in file_path.parts:
            continue
        documents.append(build_source_document(root, file_path))
    return documents
