from sqlmodel import SQLModel, Session, create_engine

from app.models.datasource import DataSource
from app.models.routine import RoutineDefinition, RoutineSqlFact
from app.models.schema import SchemaTable
from app.models.view import ViewDefinition, ViewSqlFact
from app.services import lineage_service


def test_get_table_lineage_collects_views_routines_and_edges():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(DataSource(id=1, name="demo", db_type="oracle", host="localhost", port=1521, database="orcl", username="system", password="secret", user_id="u1"))
        session.add(SchemaTable(id=1, datasource_id=1, name="users"))
        session.add(SchemaTable(id=2, datasource_id=1, name="orders"))
        session.add(
            ViewDefinition(
                id=1,
                datasource_id=1,
                owner="APP",
                name="VW_USER_ORDER",
                definition_text="select * from users join orders",
            )
        )
        session.add(
            RoutineDefinition(
                id=1,
                datasource_id=1,
                owner="APP",
                name="P_SYNC_USERS",
                routine_type="PROCEDURE",
                definition_text="insert into users select * from orders",
            )
        )
        session.add_all(
            [
                ViewSqlFact(datasource_id=1, view_id=1, statement_text="select * from users join orders", table_name="users", normalized_table_name="users"),
                ViewSqlFact(datasource_id=1, view_id=1, statement_text="select * from users join orders", table_name="orders", normalized_table_name="orders"),
                RoutineSqlFact(datasource_id=1, routine_id=1, statement_index=0, statement_text="insert into users select * from orders", table_name="users", normalized_table_name="users", usage_type="write", parser_name="sqllineage"),
                RoutineSqlFact(datasource_id=1, routine_id=1, statement_index=0, statement_text="insert into users select * from orders", table_name="orders", normalized_table_name="orders", usage_type="read", parser_name="sqllineage"),
            ]
        )
        session.commit()

        lineage = lineage_service.get_table_lineage(session, datasource_id=1, table_name="users")

    assert lineage["node"]["name"] == "users"
    assert lineage["upstream_tables"] == ["orders"]
    assert lineage["related_views"][0]["name"] == "APP.VW_USER_ORDER"
    assert lineage["related_routines"][0]["name"] == "APP.P_SYNC_USERS"
    assert len(lineage["edges"]) == 2
