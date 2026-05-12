from __future__ import annotations

from app.services.rag.schemas import AssembledContext


SYSTEM_PROMPT = (
    "你是 FastGenerate SQL 的知识问答助手。"
    "你只能依据提供的检索证据回答问题。"
    "不得编造不存在的表、字段、血缘关系或需求说明。"
    "如果证据不足，请明确说明“当前证据不足以确认”。"
)


def build_prompt(context: AssembledContext) -> str:
    lines = [
        SYSTEM_PROMPT,
        "",
        "[用户问题]",
        context.query,
        "",
        "[检索证据]",
        context.prompt_context,
        "",
        "[回答要求]",
        "1. 先给出结论。",
        "2. 再说明依据。",
        "3. 引用关键来源路径。",
        "4. 如果证据冲突或不足，请明确指出。",
    ]
    return "\n".join(lines)
