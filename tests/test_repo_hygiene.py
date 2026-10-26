"""Text-mode file I/O must name its encoding (Windows defaults to cp1252)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _files() -> list[Path]:
    files = sorted(ROOT.glob("*.py"))
    for d in ("src", "scripts"):
        files += sorted((ROOT / d).rglob("*.py"))
    return files


def _mode(call: ast.Call, pos: int = 1) -> str | None:
    node = call.args[pos] if len(call.args) > pos else None
    for kw in call.keywords:
        if kw.arg == "mode":
            node = kw.value
    if node is None:
        return "r"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None  # dynamic mode: treat as text


def _is_violation(node: ast.Call) -> bool:
    f = node.func
    # os.open returns a binary file descriptor; it has no text encoding argument.
    if (isinstance(f, ast.Attribute) and f.attr == "open"
            and isinstance(f.value, ast.Name) and f.value.id == "os"):
        return False
    is_open = isinstance(f, ast.Name) and f.id == "open"
    is_rw = isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text")
    is_path_open = isinstance(f, ast.Attribute) and f.attr == "open"  # Path.open(mode, ...)
    if not (is_open or is_rw or is_path_open):
        return False
    if is_open or is_path_open:
        mode = _mode(node, 1 if is_open else 0)
        if mode is not None and "b" in mode:
            return False
    return not any(kw.arg == "encoding" or kw.arg is None for kw in node.keywords)


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        f"{path.relative_to(ROOT).as_posix()}:{n.lineno}"
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and _is_violation(n)
    ]


def test_text_io_specifies_encoding():
    bad = [v for p in _files() for v in _violations(p)]
    assert not bad, f"{len(bad)} text-mode I/O calls without encoding=:\n" + "\n".join(bad)


def test_encoding_check_distinguishes_descriptors_from_text_streams():
    assert not _is_violation(ast.parse("os.open(path, os.O_RDONLY)").body[0].value)
    assert _is_violation(ast.parse("path.open('r')").body[0].value)
    assert _is_violation(ast.parse("open(path, 'w')").body[0].value)
    assert not _is_violation(ast.parse("path.open('r', encoding='utf-8')").body[0].value)
