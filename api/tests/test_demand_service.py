from pathlib import Path

from app.services import demand_service


def test_list_demand_categories_bootstraps_default_category(tmp_path: Path):
    tree = demand_service.list_demand_categories(tmp_path, "dd_etl")

    assert tree["tree"]["key"] == "demand"
    assert tree["tree"]["label"] == "demand"
    assert tree["tree"]["disabled"] is True
    assert tree["tree"]["children"] == []
    assert tree["default_key"] is None
    assert (tmp_path / "dd_etl" / "demand").is_dir()


def test_manage_demand_categories_supports_create_rename_delete(tmp_path: Path):
    demand_service.list_demand_categories(tmp_path, "dd_etl")

    created = demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="人行报送",
        parent_path="demand",
    )
    assert created["key"] == "人行报送"
    assert (tmp_path / "dd_etl" / "demand" / "人行报送").is_dir()

    renamed = demand_service.rename_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        path="人行报送",
        new_name="人行报送二期",
    )
    assert renamed["key"] == "人行报送二期"
    assert (tmp_path / "dd_etl" / "demand" / "人行报送二期").is_dir()

    demand_service.delete_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        path="人行报送二期",
    )
    assert not (tmp_path / "dd_etl" / "demand" / "人行报送二期").exists()


def test_save_demand_document_supports_root_demand_path(tmp_path: Path):
    try:
        demand_service.save_demand_document(
            wiki_root=tmp_path,
            datasource_name="监管ODS",
            demand_name="demand",
            table_name="ads_root_table",
            fields=[
                {
                    "name": "id",
                    "type": "varchar(32)",
                    "original_comment": "主键",
                    "supplementary_comment": "",
                }
            ],
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "请选择具体项目分类，不能直接保存到 demand 根目录"


def test_save_demand_document_writes_markdown_file(tmp_path: Path):
    demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="east报送",
        parent_path="demand",
    )
    result = demand_service.save_demand_document(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
        table_name="ads_east_report_detail",
        table_comment="EAST 明细报送表",
        related_tables=[
            {
                "table_name": "ads_east_report_summary",
                "relation_detail": "detail.report_id = summary.report_id",
            }
        ],
        fields=[
            {
                "name": "report_date",
                "type": "date",
                "original_comment": "报送日期",
                "supplementary_comment": "按自然日出数",
            },
            {
                "name": "org_code",
                "type": "varchar(64)",
                "original_comment": "机构号",
                "supplementary_comment": "",
            },
        ],
    )

    expected_path = tmp_path / "dd_etl" / "demand" / "east报送" / "ads_east_report_detail.md"
    assert Path(result["absolute_path"]) == expected_path
    assert result["relative_path"] == "dd_etl/demand/east报送/ads_east_report_detail.md"
    assert expected_path.exists()

    content = expected_path.read_text(encoding="utf-8")
    assert "title: ads_east_report_detail" in content
    assert "demand_name: east报送" in content
    assert "datasource: dd_etl" in content
    assert "- 表备注：EAST 明细报送表" in content
    assert "## 关联表" in content
    assert "- ads_east_report_summary：detail.report_id = summary.report_id" in content
    assert "| 字段名 | 类型 | 原始备注 | 本地补充备注 |" in content
    assert "| report_date | date | 报送日期 | 按自然日出数 |" in content


def test_save_demand_document_renames_existing_saved_file_and_updates_index(tmp_path: Path):
    demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="east报送",
        parent_path="demand",
    )
    first = demand_service.save_demand_document(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
        table_name="ads_old_name",
        fields=[
            {
                "name": "id",
                "type": "varchar(32)",
                "original_comment": "主键",
                "supplementary_comment": "",
            }
        ],
    )
    second = demand_service.save_demand_document(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
        table_name="ads_new_name",
        original_saved_path=first["relative_path"],
        fields=[
            {
                "name": "id",
                "type": "varchar(32)",
                "original_comment": "主键",
                "supplementary_comment": "",
            }
        ],
    )

    assert not (tmp_path / first["relative_path"]).exists()
    assert (tmp_path / second["relative_path"]).exists()


def test_list_demand_documents_returns_saved_tables(tmp_path: Path):
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
                "table_name": "ads_east_report_summary",
                "relation_detail": "detail.report_id = summary.report_id",
            }
        ],
        fields=[
            {
                "name": "report_date",
                "type": "date",
                "original_comment": "报送日期",
                "supplementary_comment": "按自然日出数",
            },
            {
                "name": "org_code",
                "type": "varchar(64)",
                "original_comment": "机构号",
                "supplementary_comment": "",
            },
        ],
    )

    documents = demand_service.list_demand_documents(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
    )

    assert len(documents) == 1
    document = documents[0]
    assert document["name"] == "ads_east_report_detail"
    assert document["comment"] == "EAST 明细报送表"
    assert document["related_tables"] == ["ads_east_report_summary"]
    assert document["related_table_details"]["ads_east_report_summary"] == "detail.report_id = summary.report_id"
    assert len(document["fields"]) == 2
    assert document["fields"][0]["name"] == "report_date"
    assert document["fields"][0]["type"] == "date"


def test_save_demand_document_rejects_empty_fields(tmp_path: Path):
    try:
        demand_service.save_demand_document(
            wiki_root=tmp_path,
            datasource_name="监管ODS",
            demand_name="east报送",
            table_name="ads_east_report_detail",
            fields=[],
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "字段列表不能为空"


def test_delete_demand_document_removes_markdown_file(tmp_path: Path):
    demand_service.create_demand_category(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        name="east报送",
        parent_path="demand",
    )
    result = demand_service.save_demand_document(
        wiki_root=tmp_path,
        datasource_name="dd_etl",
        demand_name="east报送",
        table_name="ads_east_report_detail",
        fields=[
            {
                "name": "id",
                "type": "varchar(32)",
                "original_comment": "主键",
                "supplementary_comment": "",
            }
        ],
    )

    demand_service.delete_demand_document(
        wiki_root=tmp_path,
        saved_path=result["relative_path"],
    )

    assert not (tmp_path / result["relative_path"]).exists()
