from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.api.deps import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.datasource import DataSource
from app.models.user import AppUser
from app.services import demand_service, setting_service


def override_current_user() -> AppUser:
    return AppUser(
        id=1,
        user_id="test-admin",
        name="Test Admin",
        account="admin",
        password_hash="unused",
        password_salt="unused",
        role="admin",
        is_active=True,
    )


def create_test_client(tmp_path: Path) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            DataSource(
                id=1,
                name="dd_etl",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="demo",
                username="root",
                password="secret",
                user_id="test-admin",
            )
        )
        session.commit()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_session] = override_session

    original_get_setting = setting_service.get_setting
    setting_service.get_setting = (
        lambda session, key, default=None: str(tmp_path) if key == "wiki_root" else original_get_setting(session, key, default)
    )

    client = TestClient(app)
    client._rag_original_get_setting = original_get_setting  # type: ignore[attr-defined]
    return client


def cleanup_test_client(client: TestClient) -> None:
    original_get_setting = client._rag_original_get_setting  # type: ignore[attr-defined]
    setting_service.get_setting = original_get_setting
    app.dependency_overrides.clear()
    client.close()


def seed_wiki(tmp_path: Path) -> None:
    demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="east报送",
        parent_path="demand",
    )
    demand_service.save_demand_document(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
        table_name="ads_east_report_detail",
        table_comment="EAST 明细报送表",
        related_tables=[
            {
                "table_name": "accountinfo_zs",
                "relation_detail": "cust_id 关联账户客户号",
            }
        ],
        fields=[
            {
                "name": "cust_id",
                "type": "varchar(32)",
                "original_comment": "客户号",
                "supplementary_comment": "与账户资料表关联",
            }
        ],
    )
    tables_dir = tmp_path / "dd_etl" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    (tables_dir / "accountinfo_zs.md").write_text(
        "\n".join(
            [
                "---",
                "title: accountinfo_zs",
                "---",
                "",
                "# accountinfo_zs",
                "",
                "账户资料表，主键为 cust_id。",
                "用于和 ads_east_report_detail 通过 cust_id 关联。",
            ]
        ),
        encoding="utf-8",
    )


def test_rag_search_returns_ranked_hits(tmp_path: Path):
    from app.services.rag import retriever

    seed_wiki(tmp_path)
    retriever.rebuild_index(tmp_path)

    client = create_test_client(tmp_path)
    try:
        response = client.post(
            "/api/v1/rag/search",
            json={
                "query": "east 报送明细表和账户资料表的关联键是什么",
                "datasource": "dd_etl",
                "source_types": ["demand", "schema"],
                "top_k": 5,
            },
        )
    finally:
        cleanup_test_client(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["retrieval"]["matched_count"] >= 1
    assert payload["retrieval"]["top_k_used"] == 5
    assert any(item["title"] == "ads_east_report_detail" for item in payload["items"])
    assert "diagnostics" in payload
    assert payload["diagnostics"]["related_entities"]


def test_rag_rebuild_endpoint_indexes_latest_wiki_documents(tmp_path: Path):
    client = create_test_client(tmp_path)
    try:
        seed_wiki(tmp_path)
        rebuild_response = client.post("/api/v1/rag/index/rebuild")
        search_response = client.post(
            "/api/v1/rag/search",
            json={
                "query": "cust_id",
                "datasource": "dd_etl",
                "top_k": 3,
            },
        )
    finally:
        cleanup_test_client(client)

    assert rebuild_response.status_code == 200
    assert rebuild_response.json()["indexed_files"] >= 2
    assert search_response.status_code == 200
    assert search_response.json()["items"]


def test_save_demand_document_updates_rag_index_incrementally(tmp_path: Path):
    from app.services.rag import retriever

    demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="east报送",
        parent_path="demand",
    )
    retriever.rebuild_index(tmp_path)

    demand_service.save_demand_document(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
        table_name="ads_east_report_detail",
        table_comment="EAST 明细报送表",
        fields=[
            {
                "name": "cust_id",
                "type": "varchar(32)",
                "original_comment": "客户号",
                "supplementary_comment": "作为关联键",
            }
        ],
    )

    result = retriever.search(
        query="cust_id 关联键",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl", "source_types": ["demand"]},
        top_k=5,
    )

    assert any(item.title == "ads_east_report_detail" for item in result.items)


def test_category_rename_and_delete_refresh_rag_index(tmp_path: Path):
    from app.services.rag import retriever

    demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="east报送",
        parent_path="demand",
    )
    saved = demand_service.save_demand_document(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
        table_name="ads_east_report_detail",
        fields=[
            {
                "name": "cust_id",
                "type": "varchar(32)",
                "original_comment": "客户号",
                "supplementary_comment": "作为关联键",
            }
        ],
    )
    retriever.rebuild_index(tmp_path)

    demand_service.rename_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        path="east报送",
        new_name="east报送二期",
    )
    renamed = retriever.search(
        query="ads_east_report_detail",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl", "source_types": ["demand"]},
        top_k=5,
    )
    assert any("east报送二期" in item.path for item in renamed.items)

    demand_service.delete_demand_document(
        wiki_root=tmp_path,
        saved_path=saved["relative_path"].replace("east报送", "east报送二期"),
    )
    removed = retriever.search(
        query="ads_east_report_detail",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl", "source_types": ["demand"]},
        top_k=5,
    )
    assert removed.retrieval.matched_count == 0


def test_direct_lookup_prefers_exact_object_documents(tmp_path: Path):
    from app.services.rag import retriever

    seed_wiki(tmp_path)
    retriever.rebuild_index(tmp_path)

    result = retriever.direct_lookup(
        query="ads_east_report_detail 和 accountinfo_zs 的关联键是什么",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl"},
        top_k=5,
    )

    assert result is not None
    assert any(item.title == "ads_east_report_detail" for item in result.items)
    assert any(item.title == "accountinfo_zs" for item in result.items)


def test_keyword_search_supports_category_and_content_hits(tmp_path: Path):
    from app.services.rag import retriever

    seed_wiki(tmp_path)
    retriever.rebuild_index(tmp_path)

    result = retriever.search(
        query="east报送 cust_id",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl"},
        top_k=5,
    )

    assert result.items
    assert result.items[0].title == "ads_east_report_detail"


def test_direct_lookup_matches_compact_object_name_variants(tmp_path: Path):
    from app.services.rag import retriever

    seed_wiki(tmp_path)
    retriever.rebuild_index(tmp_path)

    result = retriever.direct_lookup(
        query="adseastreportdetail 和 accountinfozs 之间怎么关联",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl"},
        top_k=5,
    )

    assert result is not None
    titles = {item.title for item in result.items}
    assert "ads_east_report_detail" in titles
    assert "accountinfo_zs" in titles
