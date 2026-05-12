from __future__ import annotations

from collections import defaultdict

from app.services.rag.prompt_builder import build_prompt
from app.services.rag.schemas import AssembledContext, ContextBucket, RetrievalItem, SearchResult


def assemble_context(query: str, search_result: SearchResult) -> AssembledContext:
    deduped: list[RetrievalItem] = []
    seen_paths: set[str] = set()
    for item in search_result.items:
        if item.path in seen_paths:
            continue
        seen_paths.add(item.path)
        deduped.append(item)

    grouped: dict[str, list[RetrievalItem]] = defaultdict(list)
    for item in deduped:
        if item.source_type == "demand":
            label = "需求/术语说明"
        elif item.source_type == "schema":
            label = "直接命中对象"
        elif item.source_type == "lineage":
            label = "血缘/过程证据"
        else:
            label = "关联对象"
        grouped[label].append(item)

    buckets = [ContextBucket(label=label, items=items) for label, items in grouped.items()]
    evidence_lines: list[str] = []
    for bucket in buckets:
        evidence_lines.append(f"## {bucket.label}")
        for item in bucket.items:
            evidence_lines.append(
                f"- 来源: {item.path} ({item.source_type})\n  标题: {item.title}\n  片段: {item.snippet}"
            )
        evidence_lines.append("")

    context = AssembledContext(
        query=query,
        sources=deduped,
        buckets=buckets,
        prompt_context="\n".join(evidence_lines).strip(),
    )
    context.prompt_text = build_prompt(context)
    return context
