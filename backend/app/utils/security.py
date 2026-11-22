from typing import Any

def sanitize_csv_cell(value: Any) -> str:
    """
    Prevents CSV Formula Injection (CSV Injection / Formula Injection).
    If a cell starts with '=', '+', '-', '@', '\t', or '\r', prefixes it with a single quote (').
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s
