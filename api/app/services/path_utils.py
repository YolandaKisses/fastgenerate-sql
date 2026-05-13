import re


def sanitize_path_segment(value: str) -> str:
    # 替换非法字符，同时将空格和括号替换为连字符，确保在 Markdown 链接中能被正确解析
    cleaned = re.sub(r'[\\/:*?"<>| \(\)]+', "-", value).strip("-")
    return cleaned or "untitled"
