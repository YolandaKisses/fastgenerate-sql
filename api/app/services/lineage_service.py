from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models.datasource import DataSource
from app.models.routine import RoutineDefinition, RoutineSqlFact
from app.models.schema import SchemaTable
from app.models.view import ViewDefinition, ViewSqlFact
from app.services.routine_lineage_service import normalize_table_name


def _find_datasource(session: Session, datasource_id: int) -> DataSource | None:
    return session.get(DataSource, datasource_id)


def _table_name_map(session: Session, datasource_id: int) -> dict[str, str]:
    tables = session.exec(
        select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)
    ).all()
    return {
        normalize_table_name(table.name or ""): table.name
        for table in tables
        if table.name
    }


def get_table_lineage(
    session: Session,
    *,
    datasource_id: int,
    table_name: str,
) -> dict[str, object]:
    normalized = normalize_table_name(table_name)
    table_name_map = _table_name_map(session, datasource_id)
    actual_name = table_name_map.get(normalized, table_name)

    routine_defs = {
        routine.id: routine
        for routine in session.exec(
            select(RoutineDefinition).where(RoutineDefinition.datasource_id == datasource_id)
        ).all()
    }
    routine_facts = session.exec(
        select(RoutineSqlFact).where(RoutineSqlFact.datasource_id == datasource_id)
    ).all()
    view_defs = {
        view.id: view
        for view in session.exec(
            select(ViewDefinition).where(ViewDefinition.datasource_id == datasource_id)
        ).all()
    }
    view_facts = session.exec(
        select(ViewSqlFact).where(ViewSqlFact.datasource_id == datasource_id)
    ).all()

    related_routines: list[dict[str, object]] = []
    related_views: list[dict[str, object]] = []
    upstream_tables: set[str] = set()
    downstream_tables: set[str] = set()
    edges: list[dict[str, str]] = []

    routine_grouped: dict[int, list[RoutineSqlFact]] = defaultdict(list)
    for fact in routine_facts:
        routine_grouped[fact.routine_id].append(fact)

    for routine_id, facts in routine_grouped.items():
        matched = [fact for fact in facts if fact.normalized_table_name == normalized]
        if not matched:
            continue
        routine = routine_defs.get(routine_id)
        if not routine:
            continue
        usage_types = sorted({fact.usage_type for fact in matched})
        sibling_tables = {
            table_name_map.get(fact.normalized_table_name, fact.table_name)
            for fact in facts
            if fact.normalized_table_name != normalized
        }
        related_routines.append(
            {
                "name": f"{routine.owner}.{routine.name}",
                "routine_type": routine.routine_type,
                "usage_types": usage_types,
                "related_tables": sorted(sibling_tables),
            }
        )
        for fact in matched:
            edges.append(
                {
                    "from": f"{routine.owner}.{routine.name}",
                    "from_type": "routine",
                    "to": actual_name,
                    "to_type": "table",
                    "relation": fact.usage_type,
                }
            )
        for sibling in sibling_tables:
            if "read" in usage_types:
                upstream_tables.add(sibling)
            if "write" in usage_types:
                downstream_tables.add(sibling)

    view_grouped: dict[int, list[ViewSqlFact]] = defaultdict(list)
    for fact in view_facts:
        view_grouped[fact.view_id].append(fact)

    for view_id, facts in view_grouped.items():
        matched = [fact for fact in facts if fact.normalized_table_name == normalized]
        if not matched:
            continue
        view = view_defs.get(view_id)
        if not view:
            continue
        sibling_tables = {
            table_name_map.get(fact.normalized_table_name, fact.table_name)
            for fact in facts
            if fact.normalized_table_name != normalized
        }
        related_views.append(
            {
                "name": f"{view.owner}.{view.name}",
                "related_tables": sorted(sibling_tables),
            }
        )
        edges.append(
            {
                "from": f"{view.owner}.{view.name}",
                "from_type": "view",
                "to": actual_name,
                "to_type": "table",
                "relation": "read",
            }
        )
        upstream_tables.update(sibling_tables)

    return {
        "node": {"type": "table", "name": actual_name},
        "upstream_tables": sorted(upstream_tables),
        "downstream_tables": sorted(downstream_tables),
        "related_views": related_views,
        "related_routines": related_routines,
        "edges": edges,
    }


def get_routine_lineage(
    session: Session,
    *,
    datasource_id: int,
    routine_name: str,
) -> dict[str, object]:
    owner, _, name = routine_name.partition(".")
    statement = select(RoutineDefinition).where(RoutineDefinition.datasource_id == datasource_id)
    if name:
        statement = statement.where(RoutineDefinition.owner == owner, RoutineDefinition.name == name)
    else:
        statement = statement.where(RoutineDefinition.name == owner)
    routine = session.exec(statement).first()
    if not routine:
        raise ValueError("未找到对应存储过程")

    facts = session.exec(
        select(RoutineSqlFact)
        .where(RoutineSqlFact.datasource_id == datasource_id, RoutineSqlFact.routine_id == routine.id)
        .order_by(RoutineSqlFact.statement_index, RoutineSqlFact.id)
    ).all()

    reads = sorted({fact.table_name for fact in facts if fact.usage_type == "read"})
    writes = sorted({fact.table_name for fact in facts if fact.usage_type == "write"})
    edges = [
        {
            "from": f"{routine.owner}.{routine.name}",
            "from_type": "routine",
            "to": fact.table_name,
            "to_type": "table",
            "relation": fact.usage_type,
        }
        for fact in facts
    ]
    return {
        "node": {"type": "routine", "name": f"{routine.owner}.{routine.name}"},
        "reads": reads,
        "writes": writes,
        "edges": edges,
        "lineage_status": routine.lineage_status,
        "lineage_message": routine.lineage_message,
    }


def get_view_lineage(
    session: Session,
    *,
    datasource_id: int,
    view_name: str,
) -> dict[str, object]:
    owner, _, name = view_name.partition(".")
    statement = select(ViewDefinition).where(ViewDefinition.datasource_id == datasource_id)
    if name:
        statement = statement.where(ViewDefinition.owner == owner, ViewDefinition.name == name)
    else:
        statement = statement.where(ViewDefinition.name == owner)
    view = session.exec(statement).first()
    if not view:
        raise ValueError("未找到对应视图")

    facts = session.exec(
        select(ViewSqlFact)
        .where(ViewSqlFact.datasource_id == datasource_id, ViewSqlFact.view_id == view.id)
        .order_by(ViewSqlFact.id)
    ).all()
    reads = sorted({fact.table_name for fact in facts})
    edges = [
        {
            "from": f"{view.owner}.{view.name}",
            "from_type": "view",
            "to": fact.table_name,
            "to_type": "table",
            "relation": "read",
        }
        for fact in facts
    ]
    return {
        "node": {"type": "view", "name": f"{view.owner}.{view.name}"},
        "reads": reads,
        "edges": edges,
        "lineage_status": view.lineage_status,
        "lineage_message": view.lineage_message,
    }


def build_table_lineage_markdown_section(lineage: dict[str, object]) -> str:
    upstream = lineage.get("upstream_tables") or []
    downstream = lineage.get("downstream_tables") or []
    related_views = lineage.get("related_views") or []
    related_routines = lineage.get("related_routines") or []

    lines = [
        "",
        "## 🧭 血缘关系",
        "",
        "### ⬆️ 上游表",
    ]
    if upstream:
        for item in upstream:
            lines.append(f"- {item}")
    else:
        lines.append("*暂无明确上游表*")

    lines.extend([
        "",
        "### ⬇️ 下游表",
    ])
    if downstream:
        for item in downstream:
            lines.append(f"- {item}")
    else:
        lines.append("*暂无明确下游表*")

    lines.extend([
        "",
        "### 👁️ 相关视图",
    ])
    if related_views:
        for item in related_views:
            related_tables = ", ".join(item.get("related_tables") or []) or "无"
            lines.append(f"- {item['name']} · 相关表: {related_tables}")
    else:
        lines.append("*暂无命中视图*")

    lines.extend([
        "",
        "### 🛠️ 相关存储过程",
    ])
    if related_routines:
        for item in related_routines:
            usages = "/".join(item.get("usage_types") or []) or "unknown"
            related_tables = ", ".join(item.get("related_tables") or []) or "无"
            lines.append(f"- {item['name']} · 读写: {usages} · 相关表: {related_tables}")
    else:
        lines.append("*暂无命中过程*")

    return "\n".join(lines)
