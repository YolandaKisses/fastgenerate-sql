import re


def sanitize_path_segment(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value).strip()
    return cleaned or "untitled"
