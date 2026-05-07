from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Generator

from app.core.config import settings


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _run_hermes_cli(
    command: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 120,
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


def run_hermes_json(prompt: str, cwd: str | None = None, hermes_cli_path: str | None = None) -> dict:
    cli_path = hermes_cli_path or settings.HERMES_CLI_PATH
    command = [
        cli_path,
        "-z",
        prompt,
        "--ignore-rules",
    ]
    return parse_hermes_json_output(_run_hermes_cli(command, cwd=cwd))


def run_hermes_session_json(
    prompt: str,
    cwd: str | None = None,
    hermes_cli_path: str | None = None,
    session_id: str | None = None,
) -> tuple[dict, dict | None, str | None]:
    cli_path = hermes_cli_path or settings.HERMES_CLI_PATH
    previous_session_ids = _list_hermes_session_ids(cli_path) if not session_id else set()
    command = [
        cli_path,
        "chat",
        "-q",
        prompt,
        "-Q",
        "-t",
        "file",
        "--source",
        "fastgenerate-sql",
        "--ignore-rules",
    ]
    if session_id:
        command.extend(["--resume", session_id])

    output = _run_hermes_cli(command, cwd=cwd)
    next_session_id = parse_hermes_session_id(output)
    if not next_session_id:
        next_session_id = session_id or _find_new_hermes_session_id(cli_path, previous_session_ids)
    return parse_hermes_json_output(output), extract_raw_hermes_result(output), next_session_id


def iter_hermes_session_json(
    prompt: str,
    cwd: str | None = None,
    hermes_cli_path: str | None = None,
    session_id: str | None = None,
) -> Generator[dict, None, None]:
    cli_path = hermes_cli_path or settings.HERMES_CLI_PATH
    previous_session_ids = _list_hermes_session_ids(cli_path) if not session_id else set()
    command = [
        cli_path,
        "chat",
        "-q",
        prompt,
        "-t",
        "file",
        "-v",
        "--source",
        "fastgenerate-sql",
        "--ignore-rules",
    ]
    if session_id:
        command.extend(["--resume", session_id])

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Hermes CLI 不存在: {command[0]}") from exc

    output_parts: list[str] = []
    if process.stdout is not None:
        try:
            for raw_line in process.stdout:
                output_parts.append(raw_line)
                trace_message = hermes_trace_message_from_line(raw_line)
                if trace_message:
                    yield {"type": "trace", "message": trace_message}
        finally:
            process.stdout.close()

    try:
        return_code = process.wait(timeout=120)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        raise RuntimeError("Hermes CLI 执行超时，请检查服务可用性") from exc
    output = "".join(output_parts)
    if return_code != 0:
        raise RuntimeError(output.strip() or "Hermes 调用失败")

    next_session_id = parse_hermes_session_id(output)
    if not next_session_id:
        next_session_id = session_id or _find_new_hermes_session_id(cli_path, previous_session_ids)

    yield {
        "type": "result",
        "result": parse_hermes_json_output(output),
        "raw_result": extract_raw_hermes_result(output),
        "session_id": next_session_id,
    }


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


def _find_new_hermes_session_id(cli_path: str, previous_session_ids: set[str]) -> str | None:
    current_session_ids = _list_hermes_session_ids(cli_path)
    for session_id in current_session_ids:
        if session_id not in previous_session_ids:
            return session_id
    return None


def _list_hermes_session_ids(cli_path: str, limit: int = 10) -> set[str]:
    command = [cli_path, "sessions", "list", "--limit", str(limit)]
    try:
        output = _run_hermes_cli(command, timeout=10)
    except RuntimeError:
        return set()
    return parse_hermes_session_ids_from_list(output)


def parse_hermes_session_ids_from_list(output: str) -> set[str]:
    session_ids: set[str] = set()
    for line in output.splitlines():
        for candidate in re.findall(r"\b\d{8}_\d{6}_[A-Za-z0-9]+\b", line):
            if _looks_like_session_id(candidate):
                session_ids.add(candidate)
    return session_ids


def parse_hermes_session_id(output: str) -> str | None:
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            data = None

        if isinstance(data, dict):
            for key in ("session_id", "sessionId", "id"):
                value = data.get(key)
                if isinstance(value, str) and _looks_like_session_id(value):
                    return value

        patterns = [
            r"^session[_\s-]*id\s*[:=]\s*([A-Za-z0-9_.:-]{8,128})\s*$",
            r"^session\s*[:=]\s*([A-Za-z0-9_.:-]{8,128})\s*$",
        ]
        for pattern in patterns:
            match = re.search(pattern, line, flags=re.I)
            if match:
                candidate = match.group(1).strip()
                if _looks_like_session_id(candidate):
                    return candidate
    return None


def _looks_like_session_id(value: str) -> bool:
    if not SESSION_ID_PATTERN.fullmatch(value):
        return False
    return bool(re.search(r"[\d_.:-]", value))


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

        if (
            isinstance(value, dict)
            and value.get("type") in {"clarification", "sql_candidate"}
            and not _is_prompt_example_result(value)
        ):
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

    if explicit_out_of_scope:
        message_lines = [
            "这个问题似乎不在当前数据库查询范围内，请选择最符合您需求的选项：",
            "A) 改为查询当前数据源中的业务数据",
            "B) 补充要查询的表、字段或业务对象",
            "C) 补充筛选条件、时间范围或统计口径",
            "D) 取消本次 SQL 生成",
        ]
    else:
        message_lines = [
            "当前问题还需要进一步澄清，请选择最符合您需求的选项：",
            "A) 我补充要查询的表、字段或业务对象",
            "B) 我补充筛选条件、时间范围或统计口径",
            "C) 请基于当前候选 Schema 重新判断并继续生成",
            "D) 取消本次 SQL 生成",
        ]

    return {
        "type": "clarification",
        "message": "\n".join(message_lines),
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
