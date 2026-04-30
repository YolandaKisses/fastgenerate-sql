from __future__ import annotations

import json
import subprocess

from app.core.config import settings


def run_hermes_json(prompt: str, cwd: str | None = None) -> dict:
    command = [
        settings.HERMES_CLI_PATH,
        "-z",
        prompt,
        "--ignore-rules",
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Hermes CLI 不存在: {settings.HERMES_CLI_PATH}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        raise RuntimeError(stderr or stdout or "Hermes 调用失败") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Hermes 调用超时") from exc

    return parse_hermes_json_output(result.stdout)


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
