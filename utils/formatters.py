"""Shared formatting utilities."""
from typing import Generator


MAX_TELEGRAM_MSG = 4096


def split_message(text: str, max_len: int = MAX_TELEGRAM_MSG) -> list[str]:
    """Split a long message into chunks that fit in Telegram's limit."""
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        # Try to split at a newline near the limit
        chunk = text[:max_len]
        split_at = chunk.rfind("\n")
        if split_at == -1 or split_at < max_len // 2:
            split_at = max_len
        parts.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return parts


def format_large_number(v: float | None) -> str:
    if v is None:
        return "N/A"
    av = abs(v)
    if av >= 1e12:
        return f"${v/1e12:.2f}T"
    if av >= 1e9:
        return f"${v/1e9:.2f}B"
    if av >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"


def pct_arrow(v: float) -> str:
    arrow = "▲" if v >= 0 else "▼"
    sign = "+" if v >= 0 else ""
    return f"{arrow} {sign}{v:.2f}%"
