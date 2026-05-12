from __future__ import annotations

import json
import re
import subprocess

from app.core.config import settings

import urllib.request
import urllib.error




def _run_hermes_cli(
    command: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 300,
    timeout_message: str = "Hermes CLI 执行超时，请检查服务可用性",
    failure_message: str = "Hermes 调用失败",
) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Hermes CLI 不存在: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(timeout_message) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        raise RuntimeError(stderr or stdout or failure_message) from exc

    return result.stdout


DEEPSEEK_SYSTEM_PROMPT = (
    "你是一个数据库元数据分析助手。根据用户提供的元数据生成结构化知识卡片。"
    "只返回合法 JSON 对象，不要输出 markdown、代码块或任何额外内容。"
)


def run_deepseek_json(prompt: str) -> dict:
    """直连 DeepSeek API，跳过 hermes CLI 开销。"""
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
    except json.JSONDecodeError:
        raise RuntimeError(f"DeepSeek API 返回非 JSON: {body[:500]}")

    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError("DeepSeek API 返回空 choices")

    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("DeepSeek API 返回空内容")

    return parse_hermes_json_output(content)


def run_deepseek_text(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> str:
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置，请在环境变量或 .env 中设置")

    base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
    model = settings.DEEPSEEK_LLM_MODEL
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
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
    return content.strip()




def hermes_trace_message_from_line(line: str) -> str | None:
    cleaned = line.strip()
    if not cleaned:
        return None
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return None
    if parse_hermes_session_id(cleaned):
        return None

    lowered = cleaned.lower()
    blocked_terms = ("chain of thought", "reasoning trace", "hidden reasoning")
    if any(term in lowered for term in blocked_terms):
        return None

    noisy_patterns = [
        r"^initializing agent",
        r"\b(?:debug|info|warning|error)\b",
        r"\brun_agent\b",
        r"\bopenai client\b",
        r"^###\s*",
        r"^执行要求[:：]",
        r"^返回格式",
        r"^-\s*sql[:：]",
    ]
    if any(re.search(pattern, cleaned, flags=re.I) for pattern in noisy_patterns):
        return None

    return cleaned[:300]




def parse_hermes_json_output(output: str) -> dict:
    cleaned = output.strip()
    if not cleaned:
        raise RuntimeError("Hermes 返回为空")

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
            candidate = _last_result_json_object(cleaned)
            if candidate is not None:
                return candidate
            normalized = _normalize_json_like_text(cleaned)
            candidate = _last_result_json_object(normalized)
            if candidate is not None:
                return candidate
            extracted_result = _extract_json_like_result(cleaned)
            if extracted_result is not None:
                return extracted_result
            clarification = _clarification_from_text(cleaned)
            if clarification is not None:
                return clarification
            raise RuntimeError(f"Hermes 返回了非 JSON 内容: {cleaned[:500]}")


def extract_raw_hermes_result(output: str) -> dict | None:
    cleaned = output.strip()
    if not cleaned:
        return None

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        value = json.loads(cleaned)
        if (
            isinstance(value, dict)
            and value.get("type") in {"clarification", "sql_candidate"}
            and not _is_prompt_example_result(value)
        ):
            return value
    except json.JSONDecodeError:
        pass

    repaired = _escape_newlines_inside_strings(cleaned)
    try:
        value = json.loads(repaired)
        if (
            isinstance(value, dict)
            and value.get("type") in {"clarification", "sql_candidate"}
            and not _is_prompt_example_result(value)
        ):
            return value
    except json.JSONDecodeError:
        pass

    candidate = _last_result_json_object(cleaned)
    if candidate is not None:
        return candidate

    normalized = _normalize_json_like_text(cleaned)
    candidate = _last_result_json_object(normalized)
    if candidate is not None:
        return candidate

    return _extract_json_like_result(cleaned)


def _last_result_json_object(text: str) -> dict | None:
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

        # 优先匹配包含知识库常用的字段（如 purpose）
        if isinstance(value, dict) and "purpose" in value:
            candidates.append(value)
        # 兜底：只要是字典且不是空的，也不是示例
        elif isinstance(value, dict) and value and not _is_prompt_example_result(value):
            candidates.append(value)

    return candidates[-1] if candidates else None


def _is_prompt_example_result(value: dict) -> bool:
    used_notes = value.get("used_notes")
    if isinstance(used_notes, list) and "已读取的笔记文件名" in used_notes:
        return True
    if value.get("type") == "sql_candidate" and value.get("sql") == "SELECT ...":
        return True
    message = value.get("message")
    if isinstance(message, str) and ("A) ..." in message or "B) ..." in message):
        return True
    return False


def _normalize_json_like_text(text: str) -> str:
    return (
        text
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def _extract_json_like_result(text: str) -> dict | None:
    """从非严格 JSON 的输出中提取最后一条真实结果，跳过 prompt 示例。"""
    normalized = _normalize_json_like_text(text)
    candidates: list[dict] = []

    clarification_pattern = re.compile(
        r'"type"\s*:\s*"clarification".*?"message"\s*:\s*"(?P<message>.*?)"\s*,\s*"used_notes"\s*:\s*\[(?P<notes>.*?)\]',
        flags=re.S,
    )
    for match in clarification_pattern.finditer(normalized):
        message = match.group("message").replace('\\"', '"').replace("\\n", "\n").strip()
        used_notes = re.findall(r'"([^"]+)"', match.group("notes"))
        candidate = {
            "type": "clarification",
            "message": message,
            "used_notes": used_notes,
        }
        if message and not _is_prompt_example_result(candidate):
            candidates.append(candidate)

    sql_pattern = re.compile(
        r'"type"\s*:\s*"sql_candidate".*?"sql"\s*:\s*"(?P<sql>.*?)"\s*,\s*"explanation"\s*:\s*"(?P<explanation>.*?)"\s*,\s*"used_notes"\s*:\s*\[(?P<notes>.*?)\]',
        flags=re.S,
    )
    for match in sql_pattern.finditer(normalized):
        sql = match.group("sql").replace('\\"', '"').replace("\\n", "\n").strip()
        explanation = match.group("explanation").replace('\\"', '"').replace("\\n", "\n").strip()
        used_notes = re.findall(r'"([^"]+)"', match.group("notes"))
        candidate = {
            "type": "sql_candidate",
            "sql": sql,
            "explanation": explanation,
            "used_notes": used_notes,
        }
        if sql and not _is_prompt_example_result(candidate):
            candidates.append(candidate)

    return candidates[-1] if candidates else None


def _clarification_from_text(text: str) -> dict | None:
    if not re.search(r"澄清|无法与\s*SQL\s*生成关联|不在.*数据库.*范围|无关", text, flags=re.I):
        return None

    explicit_out_of_scope = bool(
        re.search(r"不在.*数据库.*范围|当前数据库查询范围", text, flags=re.I)
    )

    message = (
        "抱歉，该问题超出了当前数据库的知识范围。" if explicit_out_of_scope 
        else "抱歉，我不确定您的意图，请提供更具体的信息。"
    )

    return {
        "type": "clarification",
        "message": message,
        "used_notes": [],
    }


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
