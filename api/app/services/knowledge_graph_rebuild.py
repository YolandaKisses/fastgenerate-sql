from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.models.datasource import DataSource
from app.models.schema import SchemaTable
from app.services import knowledge_service, setting_service


def _existing_wiki_table_summary_map(
    *,
    output_dir: Path,
    table_names: set[str],
) -> dict[str, dict[str, object]]:
    tables_dir = output_dir / "tables"
    if not tables_dir.exists():
        return {}

    canonical_table_names = {name.lower(): name for name in table_names if name}
    summary_map: dict[str, dict[str, object]] = {}

    for file_path in sorted(tables_dir.glob("*.md")):
        table_name = canonical_table_names.get(file_path.stem.lower())
        if not table_name:
            continue

        frontmatter = knowledge_service._read_frontmatter(file_path)
        candidates = []
        for key in ("related", "source_tables"):
            value = frontmatter.get(key, [])
            if isinstance(value, list):
                candidates.extend(str(item).strip() for item in value if str(item).strip())
            elif isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        graph_links: list[dict[str, str]] = []
        seen_targets: set[str] = set()
        for raw_target in candidates:
            canonical_target = canonical_table_names.get(raw_target.lower())
            if not canonical_target or canonical_target == table_name or canonical_target in seen_targets:
                continue
            seen_targets.add(canonical_target)
            graph_links.append(
                {
                    "target_table": canonical_target,
                    "relation_type": "documented_related",
                    "confidence": "medium",
                    "reason": "来自现有 wiki 文档",
                    "join_hint": "",
                }
            )

        summary_map[table_name] = {"graph_links": graph_links}

    return summary_map


def rebuild_datasource_graph_artifacts(
    session: Session,
    *,
    datasource_name: str,
    wiki_root: str | Path | None = None,
) -> dict[str, Any]:
    datasource = session.exec(
        select(DataSource).where(DataSource.name == datasource_name)
    ).first()
    if not datasource:
        raise ValueError(f"未找到数据源: {datasource_name}")

    resolved_wiki_root = Path(
        wiki_root
        if wiki_root is not None
        else setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    )
    output_dir = resolved_wiki_root / knowledge_service.sanitize_path_segment(datasource.name)
    if not output_dir.exists():
        raise ValueError(f"知识库目录不存在: {output_dir}")

    all_tables = session.exec(
        select(SchemaTable).where(SchemaTable.datasource_id == datasource.id)
    ).all()
    table_names = {table.name for table in all_tables if table.name}

    view_map = knowledge_service.build_view_table_map(
        session,
        datasource_id=datasource.id,
        tables=all_tables,
    )
    routine_map = knowledge_service.build_routine_table_map(
        session,
        datasource_id=datasource.id,
        tables=all_tables,
    )
    term_names = {
        file_path.stem for file_path in (output_dir / "terms").glob("*.md")
    } if (output_dir / "terms").exists() else set()
    table_summary_map = _existing_wiki_table_summary_map(
        output_dir=output_dir,
        table_names=table_names,
    )

    graph_data = knowledge_service.build_knowledge_graph(
        output_dir=output_dir,
        all_tables=all_tables,
        view_map=view_map,
        routine_map=routine_map,
        term_names=term_names,
        table_summary_map=table_summary_map,
    )

    graph_path = output_dir / "knowledge_graph.json"
    html_path = output_dir / "knowledge_graph.html"
    graph_path.write_text(
        json.dumps(graph_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    html_path.write_text(
        knowledge_service.render_knowledge_graph_html(),
        encoding="utf-8",
    )

    return {
        "datasource": datasource.name,
        "output_dir": str(output_dir),
        "graph_path": str(graph_path),
        "html_path": str(html_path),
        "table_count": len(all_tables),
        "view_count": len(view_map),
        "routine_count": len(routine_map),
        "term_count": len(term_names),
    }
