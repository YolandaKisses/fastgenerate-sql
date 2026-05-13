from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import Any

from app.services.path_utils import sanitize_path_segment

DEMAND_ROOT_NAME = "demand"


def _validate_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空")
    return normalized


def _get_datasource_root(wiki_root: str | Path, datasource_name: str) -> Path:
    root = Path(wiki_root) / sanitize_path_segment(_validate_required_text(datasource_name, "数据源名称"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _get_demand_root(wiki_root: str | Path, datasource_name: str) -> Path:
    root = _get_datasource_root(wiki_root, datasource_name) / DEMAND_ROOT_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_demand_category_path(category_path: str) -> str:
    normalized = _validate_required_text(category_path, "需求分类路径")
    if normalized == DEMAND_ROOT_NAME:
        return ""
    prefix = f"{DEMAND_ROOT_NAME}/"
    if normalized.startswith(prefix):
        return normalized[len(prefix):]
    return normalized


def _resolve_category_path(demand_root: Path, category_path: str) -> Path:
    normalized = normalize_demand_category_path(category_path)
    if not normalized:
        return demand_root
    target = (demand_root / normalized).resolve()
    if not str(target).startswith(str(demand_root.resolve())):
        raise ValueError("非法的需求分类路径")
    return target


def _build_category_node(path: Path, demand_root: Path) -> dict[str, Any]:
    relative = path.relative_to(demand_root).as_posix()
    children = sorted([child for child in path.iterdir() if child.is_dir()], key=lambda item: item.name)
    return {
        "label": path.name,
        "key": relative,
        "children": [_build_category_node(child, demand_root) for child in children],
    }


def ensure_demand_root(wiki_root: str | Path, datasource_name: str) -> Path:
    return _get_demand_root(wiki_root, datasource_name)


def list_demand_categories(wiki_root: str | Path, datasource_name: str) -> dict[str, Any]:
    demand_root = ensure_demand_root(wiki_root, datasource_name)
    children = sorted([child for child in demand_root.iterdir() if child.is_dir()], key=lambda item: item.name)
    return {
        "tree": {
            "label": DEMAND_ROOT_NAME,
            "key": DEMAND_ROOT_NAME,
            "disabled": True,
            "children": [_build_category_node(child, demand_root) for child in children],
        },
        "root_key": DEMAND_ROOT_NAME,
        "root_label": DEMAND_ROOT_NAME,
        "default_key": children[0].name if children else None,
    }


def create_demand_category(
    *,
    wiki_root: str | Path,
    datasource_name: str,
    name: str,
    parent_path: str | None,
) -> dict[str, Any]:
    demand_root = ensure_demand_root(wiki_root, datasource_name)
    normalized_name = sanitize_path_segment(_validate_required_text(name, "需求分类名称"))
    parent_dir = demand_root if not parent_path else _resolve_category_path(demand_root, parent_path)
    target_dir = parent_dir / normalized_name
    if target_dir.exists():
        raise ValueError("需求分类已存在")
    target_dir.mkdir(parents=True, exist_ok=False)
    return _build_category_node(target_dir, demand_root)


def rename_demand_category(
    *,
    wiki_root: str | Path,
    datasource_name: str,
    path: str,
    new_name: str,
) -> dict[str, Any]:
    demand_root = ensure_demand_root(wiki_root, datasource_name)
    target_dir = _resolve_category_path(demand_root, path)
    if not target_dir.exists() or not target_dir.is_dir():
        raise ValueError("需求分类不存在")
    normalized_new_name = sanitize_path_segment(_validate_required_text(new_name, "新需求分类名称"))
    new_dir = target_dir.parent / normalized_new_name
    if new_dir.exists():
        raise ValueError("目标需求分类已存在")
    target_dir.rename(new_dir)
    return _build_category_node(new_dir, demand_root)


def delete_demand_category(
    *,
    wiki_root: str | Path,
    datasource_name: str,
    path: str,
) -> None:
    demand_root = ensure_demand_root(wiki_root, datasource_name)
    target_dir = _resolve_category_path(demand_root, path)
    if target_dir == demand_root:
        raise ValueError("不允许删除根分类")
    if not target_dir.exists() or not target_dir.is_dir():
        raise ValueError("需求分类不存在")
    shutil.rmtree(target_dir)


def _normalize_field(field: dict[str, Any]) -> dict[str, str]:
    name = _validate_required_text(str(field.get("name", "")), "字段名")
    field_type = _validate_required_text(str(field.get("type", "")), "字段类型")
    return {
        "name": name,
        "type": field_type,
        "original_comment": str(field.get("original_comment", "") or "").strip(),
        "supplementary_comment": str(field.get("supplementary_comment", "") or "").strip(),
    }


def _parse_demand_document(file_path: Path, wiki_root: Path) -> dict[str, Any]:
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    table_name = file_path.stem
    table_comment = ""
    related_tables: list[str] = []
    related_table_details: dict[str, str] = {}
    fields: list[dict[str, str]] = []

    in_related = False
    in_schema = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- 表备注："):
            table_comment = stripped.replace("- 表备注：", "", 1).strip()
            if table_comment == "无":
                table_comment = ""
            continue

        if stripped == "## 关联表":
            in_related = True
            in_schema = False
            continue
        if stripped == "## 表结构":
            in_related = False
            in_schema = True
            continue

        if in_related and stripped.startswith("- "):
            relation_text = stripped[2:]
            if relation_text == "无":
                continue
            table_ref, detail = relation_text.split("：", 1) if "：" in relation_text else (relation_text, "")
            table_ref = table_ref.strip()
            related_tables.append(table_ref)
            related_table_details[table_ref] = detail.strip()
            continue

        if in_schema and stripped.startswith("|") and not stripped.startswith("| ---") and "字段名" not in stripped:
            parts = [part.strip() for part in stripped.strip("|").split("|")]
            if len(parts) >= 4:
                fields.append(
                    {
                        "name": parts[0],
                        "type": parts[1],
                        "original_comment": parts[2],
                        "supplementary_comment": parts[3],
                    }
                )

    return {
        "id": file_path.relative_to(wiki_root).as_posix(),
        "name": table_name,
        "comment": table_comment,
        "related_tables": related_tables,
        "related_table_details": related_table_details,
        "saved_path": file_path.relative_to(wiki_root).as_posix(),
        "fields": fields,
    }


def list_demand_documents(
    *,
    wiki_root: str | Path,
    datasource_name: str,
    demand_name: str,
) -> list[dict[str, Any]]:
    wiki_root_path = Path(wiki_root)
    demand_root = ensure_demand_root(wiki_root_path, datasource_name)
    category_dir = _resolve_category_path(demand_root, demand_name)
    if not category_dir.exists() or not category_dir.is_dir():
        return []

    files = sorted(category_dir.glob("*.md"))
    return [_parse_demand_document(file_path, wiki_root_path) for file_path in files]


def render_demand_document(
    *,
    datasource_name: str,
    demand_name: str,
    table_name: str,
    table_comment: str = "",
    related_tables: list[dict[str, Any]] | None = None,
    fields: list[dict[str, Any]],
) -> str:
    normalized_datasource_name = _validate_required_text(datasource_name, "数据源名称")
    normalized_demand_name = _validate_required_text(demand_name, "需求名称")
    normalized_table_name = _validate_required_text(table_name, "表名")
    normalized_table_comment = str(table_comment or "").strip()
    normalized_related_tables = related_tables or []
    if not fields:
        raise ValueError("字段列表不能为空")

    normalized_fields = [_normalize_field(field) for field in fields]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "---",
        f"title: {normalized_table_name}",
        f"demand_name: {normalized_demand_name}",
        f"datasource: {normalized_datasource_name}",
        f"generated_at: {generated_at}",
        "---",
        "",
        f"# {normalized_table_name}",
        "",
        f"- 需求分类：{normalized_demand_name}",
        f"- 数据源：{normalized_datasource_name}",
        f"- 表备注：{normalized_table_comment or '无'}",
        "",
        "## 关联表",
        "",
    ]

    if normalized_related_tables:
        for item in normalized_related_tables:
            table_ref = _validate_required_text(str(item.get("table_name", "")), "关联表名称")
            relation_detail = str(item.get("relation_detail", "") or "").strip()
            lines.append(f"- {table_ref}：{relation_detail or '未补充关系说明'}")
    else:
        lines.append("- 无")

    lines.extend([
        "",
        "## 表结构",
        "",
        "| 字段名 | 类型 | 原始备注 | 本地补充备注 |",
        "| --- | --- | --- | --- |",
    ])

    for field in normalized_fields:
        lines.append(
            f"| {field['name']} | {field['type']} | {field['original_comment']} | {field['supplementary_comment']} |"
        )

    lines.append("")
    return "\n".join(lines)


def save_demand_document(
    *,
    wiki_root: str | Path,
    datasource_name: str,
    demand_name: str,
    table_name: str,
    table_comment: str = "",
    related_tables: list[dict[str, Any]] | None = None,
    fields: list[dict[str, Any]],
    original_saved_path: str | None = None,
) -> dict[str, str]:
    normalized_demand_name = _validate_required_text(demand_name, "需求名称")
    normalized_table_name = _validate_required_text(table_name, "表名")
    content = render_demand_document(
        datasource_name=datasource_name,
        demand_name=normalized_demand_name,
        table_name=normalized_table_name,
        table_comment=table_comment,
        related_tables=related_tables,
        fields=fields,
    )

    root = Path(wiki_root)
    ensure_demand_root(root, datasource_name)
    normalized_category_path = normalize_demand_category_path(normalized_demand_name)
    if not normalized_category_path:
        raise ValueError("请选择具体项目分类，不能直接保存到 demand 根目录")
    category_segments = [
        sanitize_path_segment(segment)
        for segment in normalized_category_path.split("/")
        if segment.strip()
    ]
    relative_dir = Path(sanitize_path_segment(datasource_name)) / DEMAND_ROOT_NAME / Path().joinpath(*category_segments)
    relative_path = relative_dir / f"{sanitize_path_segment(normalized_table_name)}.md"
    absolute_path = root / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)

    old_relative_path = str(original_saved_path or "").strip()
    if old_relative_path and old_relative_path != relative_path.as_posix():
        old_absolute_path = (root / old_relative_path).resolve()
        if str(old_absolute_path).startswith(str(root.resolve())) and old_absolute_path.exists():
            old_absolute_path.unlink()

    absolute_path.write_text(content, encoding="utf-8")

    return {
        "relative_path": relative_path.as_posix(),
        "absolute_path": str(absolute_path),
        "content": content,
    }


def delete_demand_document(
    *,
    wiki_root: str | Path,
    saved_path: str,
) -> None:
    root = Path(wiki_root).resolve()
    target = (root / saved_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("非法的文档路径")
    if not target.exists() or not target.is_file():
        raise ValueError("需求文档不存在")
    target.unlink()
