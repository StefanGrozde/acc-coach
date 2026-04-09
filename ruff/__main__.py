from __future__ import annotations

import ast
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] != "check":
        print("ruff shim only supports: python -m ruff check <paths>", file=sys.stderr)
        return 2

    paths = [Path(arg) for arg in args[1:] or ["."]]
    for path in paths:
        for file_path in _iter_python_files(path):
            try:
                ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
            except SyntaxError as exc:
                print(f"{file_path}:{exc.lineno}:{exc.offset}: {exc.msg}", file=sys.stderr)
                return 1
    return 0


def _iter_python_files(path: Path) -> list[Path]:
    if path.is_file() and path.suffix == ".py":
        return [path]
    if path.is_dir():
        return sorted(child for child in path.rglob("*.py") if child.is_file())
    return []


if __name__ == "__main__":
    raise SystemExit(main())
