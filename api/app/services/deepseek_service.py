from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from app.core.config import settings


DEEPSEEK_SYSTEM_PROMPT = (
    "你是一个数据库元数据分析助手。根据用户提供的元数据生成结构化知识卡片。"
    "只返回合法 JSON 对象，不要输出 markdown、代码块或任何额外内容。"
)


def run_deepseek_json(prompt: str) -> dict:
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置，请在环境变量或 .env 中设置")

    base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
    model = settings.DEEPSEEK_LLM_MODEL
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": DEEPSEEK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 3072,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8")[:500]
        except Exception:
            pass
        raise RuntimeError(f"DeepSeek API 返回错误 HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek API 连接失败: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"DeepSeek API 请求超时或网络错误: {exc}") from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"DeepSeek API 返回非 JSON: {body[:500]}") from exc

    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError("DeepSeek API 返回空 choices")

    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("DeepSeek API 返回空内容")

    return parse_llm_json_output(content)


def parse_llm_json_output(output: str) -> dict:
    cleaned = output.strip()
    if not cleaned:
        raise RuntimeError("LLM 返回为空")

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = _escape_newlines_inside_strings(cleaned)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            candidate = _last_json_object(cleaned)
            if candidate is not None:
                return candidate
            normalized = _normalize_json_like_text(cleaned)
            candidate = _last_json_object(normalized)
            if candidate is not None:
                return candidate
            candidate = _extract_json_like_result(cleaned)
            if candidate is not None:
                return candidate
            if len(cleaned) > 50:
                return {"message": cleaned[:2000]}
            raise RuntimeError(f"LLM 返回了非 JSON 内容: {cleaned[:500]}")


def _last_json_object(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            repaired = _escape_newlines_inside_strings(text[idx:])
            try:
                value, _ = decoder.raw_decode(repaired)
            except json.JSONDecodeError:
                continue
        if isinstance(value, dict) and value:
            candidates.append(value)
    return candidates[-1] if candidates else None


def _normalize_json_like_text(text: str) -> str:
    return (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def _extract_json_like_result(text: str) -> dict | None:
    normalized = _normalize_json_like_text(text)
    match = re.search(r"\{.*\}", normalized, re.S)
    if not match:
        return None
    candidate = _escape_newlines_inside_strings(match.group(0))
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) and value else None


def _escape_newlines_inside_strings(text: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False

    for ch in text:
        if escaped:
            result.append(ch)
            escaped = False
            continue
        if ch == "\\":
            result.append(ch)
            escaped = True
            continue
        if ch == '"':
            result.append(ch)
            in_string = not in_string
            continue
        if in_string and ch == "\n":
            result.append("\\n")
            continue
        if in_string and ch == "\r":
            continue
        result.append(ch)

    return "".join(result)
