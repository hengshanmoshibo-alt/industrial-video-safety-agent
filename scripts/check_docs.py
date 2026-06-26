"""Check local Markdown links without external dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "data:")


def iter_markdown_files() -> list[Path]:
    ignored_parts = {".git", ".venv", ".venv-test", "node_modules", "dist", "__pycache__"}
    return [
        path
        for path in ROOT.rglob("*.md")
        if not any(part in ignored_parts for part in path.parts)
    ]


def normalize_target(raw_target: str) -> str:
    target = raw_target.strip()
    if not target or target.startswith(SKIP_PREFIXES):
        return ""
    if " " in target and not target.startswith("<"):
        target = target.split(" ", 1)[0]
    target = target.strip("<>")
    return target.split("#", 1)[0]


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(text):
        target = normalize_target(match.group(1))
        if not target:
            continue
        if target.startswith(SKIP_PREFIXES):
            continue
        resolved = (path.parent / unquote(target)).resolve()
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            errors.append(f"{path.relative_to(ROOT)}: link escapes repository: {target}")
            continue
        if not resolved.exists():
            errors.append(f"{path.relative_to(ROOT)}: missing link target: {target}")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in iter_markdown_files():
        errors.extend(check_file(path))
    if errors:
        print("Markdown link check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Markdown link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
