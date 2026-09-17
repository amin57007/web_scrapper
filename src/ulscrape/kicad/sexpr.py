"""Minimal KiCad s-expression helpers used to merge symbols and rewrite properties."""

from __future__ import annotations

import re
from collections.abc import Iterator


def skip_string(text: str, index: int) -> int:
    """Return the index just after a double-quoted string starting at index."""
    if index >= len(text) or text[index] != '"':
        return index
    i = index + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    return len(text)


def matching_paren(text: str, start: int) -> int:
    """Index of the closing paren that matches text[start] == '('."""
    if start >= len(text) or text[start] != "(":
        raise ValueError("matching_paren must start on '('")
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == '"':
            i = skip_string(text, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced s-expression")


def top_level_forms(text: str, head: str) -> Iterator[tuple[int, int, str]]:
    """Yield (start, end_inclusive, form_text) for every `(head ...)` at depth 1 of root."""
    stripped = text.lstrip()
    offset = len(text) - len(stripped)
    if not stripped.startswith("("):
        return
    root_end = matching_paren(text, offset)
    i = offset + 1
    while i < root_end:
        if text[i] == '"':
            i = skip_string(text, i)
            continue
        if text[i] == "(":
            end = matching_paren(text, i)
            form = text[i : end + 1]
            if _form_head(form) == head:
                yield i, end, form
            i = end + 1
            continue
        i += 1


def _form_head(form: str) -> str:
    body = form[1:].lstrip()
    match = re.match(r"[A-Za-z0-9_-]+", body)
    return match.group(0) if match else ""


def quoted_atom(form: str, position: int = 0) -> str | None:
    """Return the position-th quoted string in an s-expression form."""
    seen = 0
    i = 0
    while i < len(form):
        if form[i] == '"':
            end = skip_string(form, i)
            if seen == position:
                return _unescape(form[i + 1 : end - 1])
            seen += 1
            i = end
            continue
        i += 1
    return None


def replace_property(symbol: str, key: str, value: str) -> str:
    """Replace `(property "key" "old")` inside a symbol form, or append it."""
    pattern = re.compile(
        rf'(\(property\s+"{re.escape(key)}"\s+)"([^"]*)"',
        re.IGNORECASE,
    )
    if pattern.search(symbol):
        return pattern.sub(rf'\1"{value}"', symbol, count=1)
    insert = f'    (property "{key}" "{value}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
    end = matching_paren(symbol, 0)
    return symbol[:end] + insert + symbol[end:]


def replace_model_path(footprint: str, model_path: str) -> str:
    """Point a footprint's `(model "...")` at model_path, adding a block if missing."""
    pattern = re.compile(r'(\(model\s+)"[^"]*"')
    if pattern.search(footprint):
        return pattern.sub(rf'\1"{model_path}"', footprint, count=1)
    block = (
        f'\t(model "{model_path}"\n'
        "\t\t(offset (xyz 0 0 0))\n"
        "\t\t(scale (xyz 1 1 1))\n"
        "\t\t(rotate (xyz 0 0 0))\n"
        "\t)\n"
    )
    end = matching_paren(footprint, 0)
    return footprint[:end] + block + footprint[end:]


def _unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")
