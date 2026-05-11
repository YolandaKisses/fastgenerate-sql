from __future__ import annotations

from datetime import datetime

import sqlalchemy
from sqlmodel import Session, select

from app.models.datasource import DataSource, DataSourceStatus
from app.models.routine import RoutineDefinition
from app.services.datasource_service import build_connect_args, build_database_url
from app.services.routine_lineage_service import rebuild_routine_sql_facts


ORACLE_ROUTINE_SQL = """
SELECT owner, name, type, line, text
FROM all_source
WHERE owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')
  AND type IN ('PROCEDURE', 'FUNCTION')
ORDER BY owner, name, type, line
"""


def _normalize_routine_text(lines: list[str]) -> str:
    return "\n".join(line.rstrip("\r\n") for line in lines).strip()


def _fetch_oracle_routine_rows(ds: DataSource) -> list[tuple[str, str, str, int, str]]:
    url = build_database_url(ds)
    engine = sqlalchemy.create_engine(url, connect_args=build_connect_args(ds, 10))
    try:
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy.text(ORACLE_ROUTINE_SQL)).fetchall()
        return [
            (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                int(row[3]),
                "" if row[4] is None else str(row[4]),
            )
            for row in rows
        ]
    finally:
        engine.dispose()


def sync_routines_for_datasource(session: Session, ds: DataSource) -> dict:
    if ds.db_type != "oracle":
        return {"success": False, "message": "当前仅支持 Oracle 存储过程/函数同步"}

    try:
        rows = _fetch_oracle_routine_rows(ds)
        grouped: dict[tuple[str, str, str], list[str]] = {}
        for owner, name, routine_type, _line, text in rows:
            grouped.setdefault((owner, name, routine_type), []).append(text)

        existing = session.exec(
            select(RoutineDefinition).where(RoutineDefinition.datasource_id == ds.id)
        ).all()
        existing_map = {
            (item.owner, item.name, item.routine_type): item
            for item in existing
        }
        current_keys = set(grouped)

        for obsolete in existing:
            key = (obsolete.owner, obsolete.name, obsolete.routine_type)
            if key not in current_keys:
                session.delete(obsolete)

        now = datetime.now()
        routines_to_rebuild: list[RoutineDefinition] = []
        for key, text_lines in grouped.items():
            owner, name, routine_type = key
            definition_text = _normalize_routine_text(text_lines)
            item = existing_map.get(key)
            if item:
                item.definition_text = definition_text
                item.updated_at = now
            else:
                item = RoutineDefinition(
                    datasource_id=ds.id,
                    owner=owner,
                    name=name,
                    routine_type=routine_type,
                    definition_text=definition_text,
                    created_at=now,
                    updated_at=now,
                )
            session.add(item)
            routines_to_rebuild.append(item)

        session.flush()
        rebuild_routine_sql_facts(
            session,
            datasource_id=ds.id,
            routines=routines_to_rebuild,
        )

        ds.status = DataSourceStatus.CONNECTION_OK
        ds.last_sync_message = f"Oracle 存储过程/函数已同步 {len(grouped)} 个对象"
        ds.updated_at = now
        session.add(ds)
        session.commit()
        return {
            "success": True,
            "message": ds.last_sync_message,
            "count": len(grouped),
        }
    except Exception as exc:
        session.rollback()
        ds.last_sync_message = f"Oracle 存储过程/函数同步失败: {exc}"
        ds.updated_at = datetime.now()
        session.add(ds)
        session.commit()
        return {"success": False, "message": str(exc)}


def get_routines(session: Session, datasource_id: int) -> list[RoutineDefinition]:
    return session.exec(
        select(RoutineDefinition)
        .where(RoutineDefinition.datasource_id == datasource_id)
        .order_by(RoutineDefinition.owner, RoutineDefinition.routine_type, RoutineDefinition.name)
    ).all()
