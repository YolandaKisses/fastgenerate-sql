from __future__ import annotations

import json
import re
import subprocess

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
) -> tuple[dict, str | None]:
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
    return parse_hermes_json_output(output), next_session_id


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

    # Some Hermes responses are almost-JSON but contain raw newlines
    # inside string values. Extract the object body and repair those
    # newlines conservatively before parsing.
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = _escape_newlines_inside_strings(cleaned)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Hermes 返回了非 JSON 内容: {cleaned[:500]}") from exc


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
