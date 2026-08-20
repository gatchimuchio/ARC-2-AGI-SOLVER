#!/usr/bin/env python3
"""Validate ARC2 repository operating-environment invariants."""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

NULL_WHEN_UNSELECTED = (
    "active_strategy",
    "spec_path",
    "roadmap_path",
    "roadmap_manifest_path",
    "current_task_path",
    "active_point",
    "active_instruction_path",
)

PATH_FIELDS = {
    "spec_path": "docs/strategy/",
    "roadmap_path": "docs/roadmap/",
    "roadmap_manifest_path": "control/",
    "current_task_path": "control/",
    "active_instruction_path": "docs/instructions/",
}

STABLE_SURFACES = (
    "AGENTS.md",
    "AUTHORITY_ORDER.md",
    "README.md",
    "docs/README.md",
    "docs/operations/REPOSITORY_OPERATING_MODEL.md",
    "control/README.md",
)


class EnvironmentError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EnvironmentError(f"missing JSON: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EnvironmentError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EnvironmentError(f"JSON root must be object: {path}")
    return data


def resolve_repo_path(root: Path, raw: Any, field: str, prefix: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise EnvironmentError(f"{field} must be a non-empty repository-relative path")
    if "\\" in raw:
        raise EnvironmentError(f"{field} must use POSIX separators: {raw}")
    posix = PurePosixPath(raw)
    if posix.is_absolute() or ".." in posix.parts:
        raise EnvironmentError(f"{field} escapes repository boundary: {raw}")
    if not raw.startswith(prefix):
        raise EnvironmentError(f"{field} must be under {prefix}: {raw}")
    if "history" in {part.lower() for part in posix.parts}:
        raise EnvironmentError(f"{field} selects historical content: {raw}")
    path = root.joinpath(*posix.parts)
    if not path.is_file():
        raise EnvironmentError(f"{field} does not resolve to a file: {raw}")
    return path


def same(label: str, left: Any, right: Any) -> None:
    if left != right:
        raise EnvironmentError(f"{label} mismatch: selector={left!r}, selected={right!r}")


def find_root(start: Path) -> Path:
    here = start.resolve()
    for candidate in (here, *here.parents):
        if (candidate / "control" / "CURRENT_SELECTOR.json").is_file():
            return candidate
    raise EnvironmentError("repository root not found")


def validate(root: Path) -> int:
    selector_path = root / "control" / "CURRENT_SELECTOR.json"
    selector = load_json(selector_path)
    status = selector.get("selection_status")
    checks = 1

    if status == "UNSELECTED":
        for field in NULL_WHEN_UNSELECTED:
            if selector.get(field) is not None:
                raise EnvironmentError(f"{field} must be null while UNSELECTED")
            checks += 1
        if selector.get("auto_advance_allowed") is not False:
            raise EnvironmentError("auto_advance_allowed must be false while UNSELECTED")
        checks += 1

    elif status == "SELECTED":
        if not isinstance(selector.get("active_strategy"), str) or not selector["active_strategy"]:
            raise EnvironmentError("active_strategy required while SELECTED")
        if not isinstance(selector.get("active_point"), str) or not selector["active_point"]:
            raise EnvironmentError("active_point required while SELECTED")
        checks += 2

        resolved: dict[str, Path] = {}
        for field, prefix in PATH_FIELDS.items():
            resolved[field] = resolve_repo_path(root, selector.get(field), field, prefix)
            checks += 1

        task = load_json(resolved["current_task_path"])
        manifest = load_json(resolved["roadmap_manifest_path"])
        same("strategy_id", selector["active_strategy"], task.get("strategy_id"))
        same("manifest strategy_id", selector["active_strategy"], manifest.get("strategy_id"))
        same("active_point", selector["active_point"], task.get("active_point"))
        same("active_instruction_path", selector["active_instruction_path"], task.get("active_instruction_path"))
        if "current_point" in manifest:
            same("manifest current_point", selector["active_point"], manifest.get("current_point"))
        if "auto_advance_allowed" in task:
            same("task auto_advance_allowed", selector.get("auto_advance_allowed"), task.get("auto_advance_allowed"))
        checks += 6
    else:
        raise EnvironmentError("selection_status must be UNSELECTED or SELECTED")

    mutable_tokens = tuple(
        value
        for key in ("active_strategy", "active_point")
        if isinstance((value := selector.get(key)), str) and value
    )
    for rel in STABLE_SURFACES:
        path = root / rel
        if not path.is_file():
            raise EnvironmentError(f"stable operating surface missing: {rel}")
        text = path.read_text(encoding="utf-8")
        for token in mutable_tokens:
            if token in text:
                raise EnvironmentError(f"{rel} duplicates mutable Current token: {token}")
            checks += 1

    print(json.dumps({"status": "PASS", "selection_status": status, "checks": checks}, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    try:
        return validate(find_root(Path.cwd()))
    except EnvironmentError as exc:
        print(f"REPOSITORY_ENVIRONMENT_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
