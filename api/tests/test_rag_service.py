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
    from app.services.rag import index_manager

    seed_wiki(tmp_path)
    index_manager.rebuild_all_indexes(tmp_path)

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


def test_rag_ask_returns_answer_sources_and_retrieval(tmp_path: Path, monkeypatch):
    from app.services.rag import hermes_answer_service, index_manager

    seed_wiki(tmp_path)
    index_manager.rebuild_all_indexes(tmp_path)

    def fake_answer_with_hermes(query: str, context, prompt_config=None):
        return {
            "answer": f"根据证据，{query} 的关联键是 cust_id。",
            "sources": context.sources,
        }

    monkeypatch.setattr(hermes_answer_service, "answer_with_hermes", fake_answer_with_hermes)

    client = create_test_client(tmp_path)
    try:
        response = client.post(
            "/api/v1/rag/ask",
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
    assert "cust_id" in payload["answer"]
    assert payload["sources"]
    assert payload["retrieval"]["matched_count"] >= 1
    assert "diagnostics" in payload


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
    from app.services.rag import index_manager, retriever

    demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="east报送",
        parent_path="demand",
    )
    index_manager.rebuild_all_indexes(tmp_path)

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
    from app.services.rag import index_manager, retriever

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
    index_manager.rebuild_all_indexes(tmp_path)

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


def test_lightrag_backend_normalizes_remote_search_result(tmp_path: Path, monkeypatch):
    from app.core.config import settings
    from app.services.rag import retriever
    from app.services.rag.backends import LightRAGHTTPBackend

    seed_wiki(tmp_path)
    settings.RAG_RETRIEVAL_BACKEND = "lightrag"
    settings.LIGHTRAG_BASE_URL = "http://mock-lightrag"

    def fake_request(self, method, path, payload=None):
        assert path == settings.LIGHTRAG_SEARCH_PATH
        return {
            "results": [
                {
                    "id": "remote-1",
                    "score": 0.91,
                    "name": "ads_east_report_detail",
                    "file_path": "dd_etl/demand/east报送/ads_east_report_detail.md",
                    "content": "cust_id 作为关联键",
                    "metadata": {
                        "source_type": "demand",
                        "datasource": "dd_etl",
                        "object_type": "table",
                    },
                }
            ],
            "retrieval": {
                "matched_count": 1,
                "direct_hits": 1,
                "source_types": ["demand"],
                "top_k_used": 5,
            },
        }

    monkeypatch.setattr(LightRAGHTTPBackend, "_request", fake_request)
    result = retriever.search(
        query="cust_id",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl", "source_types": ["demand"]},
        top_k=5,
        backend_name="lightrag",
    )

    assert result.items[0].title == "ads_east_report_detail"
    assert result.items[0].path == "dd_etl/demand/east报送/ads_east_report_detail.md"
    assert result.retrieval.direct_hits == 1


def test_lightrag_backend_supports_remote_ask_passthrough(tmp_path: Path, monkeypatch):
    from app.core.config import settings
    from app.services.rag import retriever
    from app.services.rag.backends import LightRAGHTTPBackend

    seed_wiki(tmp_path)
    settings.RAG_RETRIEVAL_BACKEND = "lightrag"
    settings.LIGHTRAG_BASE_URL = "http://mock-lightrag"
    settings.LIGHTRAG_ENABLE_REMOTE_ASK = True

    def fake_request(self, method, path, payload=None):
        assert path == settings.LIGHTRAG_ASK_PATH
        return {
            "answer": "远端 LightRAG 返回：关联键是 cust_id。",
            "items": [
                {
                    "chunk_id": "remote-ask-1",
                    "score": 0.95,
                    "title": "ads_east_report_detail",
                    "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
                    "source_type": "demand",
                    "datasource": "dd_etl",
                    "snippet": "cust_id 作为关联键",
                }
            ],
            "retrieval": {
                "matched_count": 1,
                "direct_hits": 1,
                "source_types": ["demand"],
                "top_k_used": 5,
            },
        }

    monkeypatch.setattr(LightRAGHTTPBackend, "_request", fake_request)
    result = retriever.ask(
        query="cust_id",
        wiki_root=tmp_path,
        filters={"datasource": "dd_etl", "source_types": ["demand"]},
        top_k=5,
        backend_name="lightrag",
    )

    assert result is not None
    assert "cust_id" in result["answer"]
    assert result["sources"][0]["title"] == "ads_east_report_detail"


def test_rag_ask_route_prefers_remote_lightrag_when_enabled(tmp_path: Path, monkeypatch):
    from app.core.config import settings
    from app.services.rag import retriever

    seed_wiki(tmp_path)
    settings.RAG_RETRIEVAL_BACKEND = "lightrag"
    settings.LIGHTRAG_ENABLE_REMOTE_ASK = True

    def fake_remote_ask(**kwargs):
        return {
            "answer": "远端优先答案：关联键是 cust_id。",
            "sources": [
                {
                    "chunk_id": "remote-1",
                    "score": 0.99,
                    "title": "ads_east_report_detail",
                    "path": "dd_etl/demand/east报送/ads_east_report_detail.md",
                    "source_type": "demand",
                    "datasource": "dd_etl",
                    "snippet": "cust_id 作为关联键",
                }
            ],
            "retrieval": {
                "matched_count": 1,
                "direct_hits": 1,
                "source_types": ["demand"],
                "top_k_used": 5,
            },
            "diagnostics": {
                "related_entities": [],
                "related_relations": [],
            },
        }

    monkeypatch.setattr(retriever, "ask", fake_remote_ask)

    client = create_test_client(tmp_path)
    try:
        response = client.post(
            "/api/v1/rag/ask",
            json={
                "query": "east 报送明细表和账户资料表的关联键是什么",
                "datasource": "dd_etl",
                "source_types": ["demand"],
                "top_k": 5,
            },
        )
    finally:
        cleanup_test_client(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"].startswith("远端优先答案")
    assert payload["sources"][0]["title"] == "ads_east_report_detail"


def test_lightrag_backend_rebuild_index_reports_remote_result(tmp_path: Path, monkeypatch):
    from app.core.config import settings
    from app.services.rag import retriever
    from app.services.rag.backends import LightRAGHTTPBackend

    seed_wiki(tmp_path)
    settings.RAG_RETRIEVAL_BACKEND = "lightrag"
    settings.LIGHTRAG_BASE_URL = "http://mock-lightrag"
    settings.LIGHTRAG_ENABLE_REMOTE_REBUILD = True

    def fake_request(self, method, path, payload=None):
        assert path == settings.LIGHTRAG_REBUILD_PATH
        return {"status": "ok", "indexed_files": 2}

    monkeypatch.setattr(LightRAGHTTPBackend, "_request", fake_request)
    result = retriever.rebuild_index(tmp_path, backend_name="lightrag")

    assert result["backend"] == "lightrag"
    assert result["mode"] == "hybrid"
    assert result["remote"]["status"] == "ok"


def test_lightrag_backend_propagates_upsert_and_delete_calls(tmp_path: Path, monkeypatch):
    from app.core.config import settings
    from app.services.rag import retriever
    from app.services.rag.backends import LightRAGHTTPBackend

    seed_wiki(tmp_path)
    settings.RAG_RETRIEVAL_BACKEND = "lightrag"
    settings.LIGHTRAG_BASE_URL = "http://mock-lightrag"
    settings.LIGHTRAG_ENABLE_REMOTE_REBUILD = True
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(self, method, path, payload=None):
        calls.append((method, path, payload))
        return {"status": "ok"}

    monkeypatch.setattr(LightRAGHTTPBackend, "_request", fake_request)

    retriever.index_single_file(
        tmp_path,
        "dd_etl/demand/east报送/ads_east_report_detail.md",
        backend_name="lightrag",
    )
    retriever.remove_deleted_file(
        tmp_path,
        "dd_etl/demand/east报送/ads_east_report_detail.md",
        backend_name="lightrag",
    )

    assert any(path == settings.LIGHTRAG_UPSERT_PATH for _, path, _ in calls)
    assert any(path == settings.LIGHTRAG_DELETE_PATH for _, path, _ in calls)
