from __future__ import annotations

from datetime import datetime

import sqlalchemy
from sqlmodel import Session, select

from app.models.datasource import DataSource
from app.models.view import ViewDefinition
from app.services.datasource_service import build_connect_args, build_database_url
from app.services.view_lineage_service import rebuild_view_sql_facts


ORACLE_VIEW_SQL = """
SELECT owner, view_name, text
FROM all_views
WHERE owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')
ORDER BY owner, view_name
"""

ORACLE_VIEW_COMMENT_SQL = """
SELECT owner, table_name, comments
FROM all_tab_comments
WHERE owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')
  AND table_type = 'VIEW'
"""


def _fetch_oracle_views(ds: DataSource) -> tuple[list[tuple[str, str, str]], dict[tuple[str, str], str]]:
    url = build_database_url(ds)
    engine = sqlalchemy.create_engine(url, connect_args=build_connect_args(ds, 10))
    try:
        with engine.connect() as conn:
            view_rows = conn.execute(sqlalchemy.text(ORACLE_VIEW_SQL)).fetchall()
            comment_rows = conn.execute(sqlalchemy.text(ORACLE_VIEW_COMMENT_SQL)).fetchall()
        views = [
            (
                str(row[0]),
                str(row[1]),
                "" if row[2] is None else str(row[2]),
            )
            for row in view_rows
        ]
        comments = {
            (str(row[0]), str(row[1])): "" if row[2] is None else str(row[2])
            for row in comment_rows
        }
        return views, comments
    finally:
        engine.dispose()


def sync_views_for_datasource(session: Session, ds: DataSource) -> dict:
    if ds.db_type != "oracle":
        return {"success": False, "message": "当前仅支持 Oracle 视图同步"}

    try:
        rows, comments = _fetch_oracle_views(ds)
        existing = session.exec(
            select(ViewDefinition).where(ViewDefinition.datasource_id == ds.id)
        ).all()
        existing_map = {(item.owner, item.name): item for item in existing}
        current_keys = {(owner, name) for owner, name, _text in rows}

        for obsolete in existing:
            key = (obsolete.owner, obsolete.name)
            if key not in current_keys:
                session.delete(obsolete)

        now = datetime.now()
        views_to_rebuild: list[ViewDefinition] = []
        for owner, name, definition_text in rows:
            key = (owner, name)
            item = existing_map.get(key)
            if item:
                item.definition_text = definition_text
                item.original_comment = comments.get(key)
                item.updated_at = now
            else:
                item = ViewDefinition(
                    datasource_id=ds.id,
                    owner=owner,
                    name=name,
                    definition_text=definition_text,
                    original_comment=comments.get(key),
                    created_at=now,
                    updated_at=now,
                )
            session.add(item)
            views_to_rebuild.append(item)

        session.flush()
        rebuild_view_sql_facts(
            session,
            datasource_id=ds.id,
            views=views_to_rebuild,
        )
        session.commit()
        return {
            "success": True,
            "message": f"Oracle 视图已同步 {len(rows)} 个对象",
            "count": len(rows),
        }
    except Exception as exc:
        session.rollback()
        return {"success": False, "message": str(exc)}


def get_views(session: Session, datasource_id: int) -> list[ViewDefinition]:
    return session.exec(
        select(ViewDefinition)
        .where(ViewDefinition.datasource_id == datasource_id)
        .order_by(ViewDefinition.owner, ViewDefinition.name)
    ).all()
