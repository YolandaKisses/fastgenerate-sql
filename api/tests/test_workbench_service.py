from app.models.schema import SchemaTable
from app.services.workbench_service import (
    normalize_note_name,
    note_hit_payload,
    validate_sql_candidate,
)


def test_validate_sql_candidate_rejects_multi_statement_write_sql():
    result = validate_sql_candidate("SELECT * FROM users; DELETE FROM users")

    assert result["status"] == "invalid"
    assert "禁止执行多条语句" in result["reasons"]
    assert any("DELETE" in reason for reason in result["reasons"])


def test_normalize_note_name_accepts_markdown_paths():
    assert normalize_note_name("tables/user_profiles.md") == "user_profiles"


def test_note_hit_payload_uses_table_comment_from_final_used_note():
    table = SchemaTable(
        id=1,
        datasource_id=1,
        name="user_profiles",
        original_comment="用户资料表",
    )

    payload = note_hit_payload("user_profiles", {"user_profiles": table})

    assert payload == {"note": "user_profiles", "comment": "用户资料表"}
