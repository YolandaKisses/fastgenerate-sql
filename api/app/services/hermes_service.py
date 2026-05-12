from __future__ import annotations

import json
import re
import subprocess
from typing import Generator

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
        r'^"(?:type|sql|explanation|message|used_notes|candidates|sql_candidates|dataSource|dbType|purpose|limitations|additionalTablesFound)"\s*[:：]',
        r'^\s*[{}[\],]\s*$',
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
            
            # 兜底：如果完全无法解析 JSON，但包含大量文字，尝试封装成 clarification
            if len(cleaned) > 50:
                return {
                    "type": "clarification",
                    "message": cleaned[:2000],
                    "used_notes": []
                }
                
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
        r'"type"\s*:\s*"sql_candidate".*?(?:"sql"\s*:\s*"(?P<sql>.*?)"\s*,\s*"explanation"\s*:\s*"(?P<explanation>.*?)"|"candidates"\s*:\s*\[(?P<candidates>.*?)\])',
        flags=re.S,
    )
    for match in sql_pattern.finditer(normalized):
        if match.group("candidates"):
            # If it has candidates, we try to extract the first one
            cand_text = match.group("candidates")
            # Simple extraction of first sql/explanation pair in the candidates array
            s_match = re.search(r'"sql"\s*:\s*"(?P<sql>.*?)"', cand_text, re.S)
            e_match = re.search(r'"explanation"\s*:\s*"(?P<explanation>.*?)"', cand_text, re.S)
            sql = s_match.group("sql").replace('\\"', '"').replace("\\n", "\n").strip() if s_match else ""
            explanation = e_match.group("explanation").replace('\\"', '"').replace("\\n", "\n").strip() if e_match else ""
        else:
            sql = match.group("sql").replace('\\"', '"').replace("\\n", "\n").strip()
            explanation = match.group("explanation").replace('\\"', '"').replace("\\n", "\n").strip()
        
        candidate = {
            "type": "sql_candidate",
            "sql": sql,
            "explanation": explanation,
            "used_notes": [],
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


SESSION_ID_PATTERN = re.compile(r"session_id:\s*([A-Za-z0-9._:-]+)")
SESSION_LIST_ROW_PATTERN = re.compile(
    r"^(?P<title>.+?)\s{2,}(?P<preview>.+?)\s{2,}(?P<last_active>(?:just now|\d+[mhdy] ago|\d+\s*[分钟小时天周月年]前|.+?ago))\s{2,}(?P<id>\d{8}_\d{6}_[A-Za-z0-9]+)$"
)


def parse_hermes_session_id(output: str) -> str | None:
    match = SESSION_ID_PATTERN.search(output)
    if match:
        return match.group(1).strip()
    return None


def run_hermes_session_json(
    prompt: str,
    *,
    hermes_cli_path: str | None = None,
    session_id: str | None = None,
) -> tuple[dict, str | None]:
    cli_path = hermes_cli_path or settings.HERMES_CLI_PATH
    command = [cli_path, "chat", "-q", prompt, "-Q", "-v", "--source", "tool"]
    if session_id:
        command.extend(["--resume", session_id])
    output = _run_hermes_cli(command, timeout=300, failure_message="Hermes 会话调用失败")
    parsed = parse_hermes_json_output(output)
    resolved_session_id = parse_hermes_session_id(output) or session_id
    return parsed, resolved_session_id


def iter_hermes_session_json(
    prompt: str,
    *,
    hermes_cli_path: str | None = None,
    session_id: str | None = None,
) -> Generator[dict, None, None]:
    cli_path = hermes_cli_path or settings.HERMES_CLI_PATH
    command = [cli_path, "chat", "-q", prompt, "-Q", "-v", "--source", "tool"]
    if session_id:
        command.extend(["--resume", session_id])

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=None,
    )
    assert process.stdout is not None
    lines: list[str] = []
    try:
        for line in process.stdout:
            lines.append(line)
            
            # 提前捕获并抛出 Session ID 事件
            if not session_id:
                potential_id = parse_hermes_session_id(line)
                if potential_id:
                    session_id = potential_id
                    yield {"type": "session_id", "session_id": session_id}

            trace = hermes_trace_message_from_line(line)
            if trace:
                yield {"type": "trace", "message": trace}
        return_code = process.wait(timeout=300)
        output = "".join(lines)
        if return_code != 0:
            raise RuntimeError(output.strip() or "Hermes 流式会话失败")
        result = parse_hermes_json_output(output)
        resolved_session_id = parse_hermes_session_id(output) or session_id
        yield {"type": "result", "result": result, "session_id": resolved_session_id}
    finally:
        if process.stdout:
            process.stdout.close()


def list_hermes_sessions(*, hermes_cli_path: str | None = None) -> list[dict]:
    cli_path = hermes_cli_path or settings.HERMES_CLI_PATH
    output = _run_hermes_cli([cli_path, "sessions", "list"], timeout=60, failure_message="读取 Hermes 会话列表失败")
    sessions: list[dict] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("Title") or stripped.startswith("─"):
            continue
        match = SESSION_LIST_ROW_PATTERN.match(stripped)
        if not match:
            continue
        title = match.group("title").strip()
        preview = match.group("preview").strip()
        sessions.append(
            {
                "title": "" if title == "—" else title,
                "preview": preview,
                "last_active": match.group("last_active").strip(),
                "session_id": match.group("id").strip(),
            }
        )
    return sessions


def get_hermes_session_messages(session_id: str, *, hermes_cli_path: str | None = None) -> list[dict]:
    cli_path = hermes_cli_path or settings.HERMES_CLI_PATH
    command = [cli_path, "sessions", "export", "--session-id", session_id, "-"]
    output = _run_hermes_cli(command, timeout=60, failure_message=f"读取 Hermes 会话 {session_id} 详情失败")
    
    raw_messages: list[dict] = []
    
    # Aggressive JSON object extraction
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(output):
        # Find potential start of a JSON object or array
        start = output.find("{", pos)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(output[start:])
            if isinstance(obj, dict):
                if "role" in obj and "content" in obj:
                    raw_messages.append(obj)
                elif "messages" in obj and isinstance(obj["messages"], list):
                    raw_messages.extend(obj["messages"])
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        if "role" in item and "content" in item:
                            raw_messages.append(item)
                        elif "messages" in item and isinstance(item["messages"], list):
                            raw_messages.extend(item["messages"])
            pos = start + end
        except json.JSONDecodeError:
            pos = start + 1

    messages: list[dict] = []
    # Deduplicate by ID if present, or just keep all
    seen_ids = set()
    for record in raw_messages:
        msg_id = record.get("id")
        if msg_id is not None:
            if msg_id in seen_ids: continue
            seen_ids.add(msg_id)
            
        role = record.get("role")
        content = record.get("content")
        if not role or not content:
            continue
            
        msg = {
            "role": role,
            "content": content,
            "kind": "text"
        }
        
        if role == "assistant":
            if isinstance(content, dict):
                result = content
            else:
                result = extract_raw_hermes_result(content)
                
            if result:
                if result.get("type") == "sql_candidate":
                    msg["kind"] = "sql"
                    # 兼容多候选格式
                    if not result.get("sql") and result.get("sql_candidates"):
                        cands = result.get("sql_candidates", [])
                        if cands:
                            msg["sql"] = cands[0].get("sql")
                            msg["content"] = cands[0].get("explanation") or msg["content"]
                    else:
                        msg["sql"] = result.get("sql")
                        msg["content"] = result.get("explanation") or msg["content"]
                elif result.get("type") == "clarification":
                    msg["kind"] = "clarification"
                    msg["content"] = result.get("message") or msg["content"]
        
        messages.append(msg)
    
    # Clean up the initial system/context injection message
    if messages and messages[0]["role"] == "user":
        content = messages[0]["content"]
        if "你是一个专业的数据库研发人员" in content or "Schema Context" in content:
            # Try to extract the actual user question
            # Look for common headers used in our prompt builder
            question_match = re.search(r"### 用户问题\s*\n(.*?)(?:\n###|$)", content, re.DOTALL)
            if question_match:
                extracted = question_match.group(1).strip()
                # If the question is repeated (sometimes happens in prompt construction), take the first part
                lines = extracted.splitlines()
                if len(lines) > 1 and lines[0].strip() == lines[1].strip():
                    extracted = lines[0].strip()
                messages[0]["content"] = extracted
            else:
                # If we can't find a clear question header, and it's a huge message, it might be better to keep it 
                # but it's "ugly". For now, let's just keep the last 200 chars as a fallback or don't pop it.
                pass
        
    return messages
