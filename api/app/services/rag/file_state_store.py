from __future__ import annotations

import json
from hashlib import sha1
from pathlib import Path

from app.services.rag.schemas import IndexManifest


def _storage_path(wiki_root: str | Path) -> Path:
    root_key = sha1(str(Path(wiki_root).resolve()).encode("utf-8")).hexdigest()[:12]
    storage_dir = Path(wiki_root).resolve() / ".rag"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir / f"{root_key}.json"


def load_manifest(wiki_root: str | Path) -> IndexManifest | None:
    path = _storage_path(wiki_root)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return IndexManifest.model_validate(data)


def save_manifest(wiki_root: str | Path, manifest: IndexManifest) -> None:
    path = _storage_path(wiki_root)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
