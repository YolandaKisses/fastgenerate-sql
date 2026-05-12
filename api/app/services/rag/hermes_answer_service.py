from __future__ import annotations

from app.services.hermes_service import run_deepseek_text
from app.services.rag.schemas import AssembledContext


def format_hermes_answer(raw_output: str) -> str:
    return raw_output.strip() or "当前证据不足以确认，请查看右侧召回证据后重试。"


def fallback_when_no_evidence(query: str, retrieval_summary) -> str:
    return (
        f"当前没有检索到足够证据来回答“{query}”。"
        f"已命中 {retrieval_summary.matched_count} 条候选，请尝试缩小范围或补充关键词。"
    )


def answer_with_hermes(
    query: str,
    context: AssembledContext,
    prompt_config: dict | None = None,
) -> dict[str, object]:
    if not context.sources:
        return {"answer": fallback_when_no_evidence(query, prompt_config["retrieval"]), "sources": []}

    prompt = context.prompt_text
    answer = run_deepseek_text(
        system_prompt=(
            "你是 FastGenerate SQL 的知识问答助手。"
            "只基于用户提供的证据回答，不得编造。"
        ),
        user_prompt=prompt,
        temperature=0.2,
        max_tokens=1200,
    )
    if prompt_config and prompt_config.get("diagnostics"):
        diagnostics = prompt_config["diagnostics"]
        if diagnostics.related_relations:
            answer = f"{answer}\n\n关联诊断：\n" + "\n".join(
                f"- {item.subject} {item.predicate} {item.object} ({item.path})"
                for item in diagnostics.related_relations[:3]
            )
    return {"answer": format_hermes_answer(answer), "sources": context.sources}
