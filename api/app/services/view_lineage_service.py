from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, delete

from app.models.view import ViewDefinition, ViewSqlFact
from app.services.routine_lineage_service import parse_statement_tables, normalize_table_name


def rebuild_view_sql_facts(
    session: Session,
    *,
    datasource_id: int,
    views: list[ViewDefinition],
) -> None:
    session.exec(delete(ViewSqlFact).where(ViewSqlFact.datasource_id == datasource_id))

    now = datetime.now()
    for view in views:
        definition_text = (view.definition_text or "").strip()
        fact_count = 0
        parser_names: set[str] = set()

        if definition_text:
            read_tables, _write_tables, parser_name = parse_statement_tables(definition_text)
            parser_names.add(parser_name)

            for table_name in sorted(read_tables):
                normalized = normalize_table_name(table_name)
                if not normalized:
                    continue
                session.add(
                    ViewSqlFact(
                        datasource_id=datasource_id,
                        view_id=view.id,
                        statement_text=definition_text,
                        table_name=normalized,
                        normalized_table_name=normalized,
                        usage_type="read",
                        parser_name=parser_name,
                        created_at=now,
                        updated_at=now,
                    )
                )
                fact_count += 1

        view.lineage_updated_at = now
        if fact_count > 0:
            view.lineage_status = "parsed"
            view.lineage_message = f"解析出 {fact_count} 条视图依赖事实（{', '.join(sorted(parser_names))}）"
        elif definition_text:
            view.lineage_status = "no_table_fact"
            view.lineage_message = "已抽取视图 SQL，但未识别出明确底层表关系"
        else:
            view.lineage_status = "no_sql"
            view.lineage_message = "视图定义为空"
        session.add(view)
