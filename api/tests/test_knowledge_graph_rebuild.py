from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

from app.models.datasource import DataSource
from app.models.routine import RoutineDefinition, RoutineSqlFact
from app.models.schema import SchemaTable
from app.models.view import ViewDefinition, ViewSqlFact
from app.services.knowledge_graph_rebuild import rebuild_datasource_graph_artifacts


def test_rebuild_datasource_graph_artifacts_uses_metadata_and_existing_wiki(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'graph-rebuild.db'}")
    SQLModel.metadata.create_all(engine)

    wiki_root = tmp_path / "wiki"
    output_dir = wiki_root / "dd_etl"
    (output_dir / "tables").mkdir(parents=True)
    (output_dir / "terms").mkdir(parents=True)

    (output_dir / "tables" / "cr_export_config.md").write_text(
        """---
summary: 导出配置
related:
  - cr_export_fund
source_tables:
  - cr_export_config
  - CR_EXPORT_FUND
---

# cr_export_config
""",
        encoding="utf-8",
    )
    (output_dir / "tables" / "cr_export_fund.md").write_text(
        """---
summary: 导出产品
source_tables:
  - cr_export_fund
---

# cr_export_fund
""",
        encoding="utf-8",
    )
    (output_dir / "terms" / "导出配置.md").write_text("# 导出配置\n", encoding="utf-8")

    with Session(engine) as session:
        session.add(
            DataSource(
                id=1,
                name="dd_etl",
                db_type="oracle",
                host="localhost",
                port=1521,
                database="orcl",
                username="system",
                password="secret",
                user_id="user-1",
            )
        )
        session.add(SchemaTable(id=1, datasource_id=1, name="cr_export_config"))
        session.add(SchemaTable(id=2, datasource_id=1, name="cr_export_fund"))
        session.add(
            ViewDefinition(
                id=1,
                datasource_id=1,
                owner="APP",
                name="VW_EXPORT",
                definition_text="select * from cr_export_config",
            )
        )
        session.add(
            ViewSqlFact(
                datasource_id=1,
                view_id=1,
                statement_text="select * from cr_export_config",
                table_name="cr_export_config",
                normalized_table_name="cr_export_config",
            )
        )
        session.add(
            RoutineDefinition(
                id=1,
                datasource_id=1,
                owner="APP",
                name="P_EXPORT",
                routine_type="PROCEDURE",
                definition_text="select * from cr_export_fund",
            )
        )
        session.add(
            RoutineSqlFact(
                datasource_id=1,
                routine_id=1,
                statement_index=0,
                statement_text="select * from cr_export_fund",
                table_name="cr_export_fund",
                normalized_table_name="cr_export_fund",
                usage_type="read",
            )
        )
        session.commit()

        result = rebuild_datasource_graph_artifacts(
            session,
            datasource_name="dd_etl",
            wiki_root=wiki_root,
        )

    graph = json.loads((output_dir / "knowledge_graph.json").read_text(encoding="utf-8"))
    html = (output_dir / "knowledge_graph.html").read_text(encoding="utf-8")

    assert result["datasource"] == "dd_etl"
    assert result["output_dir"] == str(output_dir)
    assert result["graph_path"] == str(output_dir / "knowledge_graph.json")
    assert result["html_path"] == str(output_dir / "knowledge_graph.html")
    assert '<script src="https://unpkg.com/force-graph@1.49.3/dist/force-graph.min.js"></script>' in html
    assert {"id": "cr_export_config", "type": "table", "path": "tables/cr_export_config.md"} in graph["nodes"]
    assert {"id": "APP.VW_EXPORT", "type": "view", "path": "views/APP.VW_EXPORT.md"} in graph["nodes"]
    assert {"id": "APP.P_EXPORT", "type": "routine", "path": "routines/APP.P_EXPORT.md"} in graph["nodes"]
    assert {"id": "导出配置", "type": "term", "path": "terms/导出配置.md"} in graph["nodes"]
    assert {
        "source": "cr_export_config",
        "target": "cr_export_fund",
        "relation": "documented_related",
        "source_type": "table",
        "confidence": "medium",
        "reason": "来自现有 wiki 文档",
        "join_hint": "",
    } in graph["edges"]
