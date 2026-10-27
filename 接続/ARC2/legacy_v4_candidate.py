"""Expose the recovered v4 solver as an input-only alternate candidate source."""

from __future__ import annotations

import os
import runpy
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

Grid = list[list[int]]

_LOAD_LOCK = threading.Lock()
_SOLVE_TASK: Callable[[dict[str, Any]], Any] | None = None
_RUNNER_NAMESPACE: dict[str, Any] | None = None


@contextmanager
def _cross_process_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def valid_grid(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    if any(not isinstance(row, list) or not row for row in value):
        return False
    width = len(value[0])
    if any(len(row) != width for row in value):
        return False
    return all(
        type(cell) is int and 0 <= cell <= 9
        for row in value
        for cell in row
    )


def _ensure_work_root() -> None:
    if os.environ.get("ARC2_WORK_ROOT"):
        return
    kaggle_work = Path("/kaggle/working")
    work_root = (
        kaggle_work
        if kaggle_work.is_dir()
        else Path(tempfile.gettempdir()) / "arc2-legacy-v4"
    )
    work_root.mkdir(parents=True, exist_ok=True)
    os.environ["ARC2_WORK_ROOT"] = str(work_root)


def _load_solver() -> Callable[[dict[str, Any]], Any]:
    global _RUNNER_NAMESPACE, _SOLVE_TASK
    if _SOLVE_TASK is not None:
        return _SOLVE_TASK
    with _LOAD_LOCK:
        if _SOLVE_TASK is not None:
            return _SOLVE_TASK
        _ensure_work_root()
        runner_path = Path(__file__).with_name("legacy_v4_solver.py")
        if not runner_path.is_file():
            raise FileNotFoundError("recovered v4 solver bundle is missing")
        work_root = Path(os.environ["ARC2_WORK_ROOT"])
        with _cross_process_lock(work_root / ".arc2-legacy-v4-extract.lock"):
            _RUNNER_NAMESPACE = runpy.run_path(
                str(runner_path), run_name="_arc2_recovered_v4_runner"
            )
            _RUNNER_NAMESPACE["_safe_extract_bundle"]()
            embedded_root = Path(_RUNNER_NAMESPACE["EMBEDDED_ROOT"]).resolve()
            if str(embedded_root) not in sys.path:
                sys.path.insert(0, str(embedded_root))
            from arc_agi_2_solver.solver_core import solve_task

            _SOLVE_TASK = solve_task
        return _SOLVE_TASK


def legacy_candidates(task: dict[str, Any]) -> list[dict[str, list[Grid]]]:
    """Return generic non-placeholder and placeholder predictions per test input."""
    result = _load_solver()(task)
    predictions = getattr(result, "predictions", [])
    if not isinstance(predictions, list):
        return []
    rows: list[dict[str, list[Grid]]] = []
    for prediction in predictions:
        real: list[Grid] = []
        fallback: list[Grid] = []
        attempts = getattr(prediction, "attempts", [])
        if isinstance(attempts, list):
            for attempt in attempts:
                output = getattr(attempt, "output", None)
                if not valid_grid(output):
                    continue
                if getattr(attempt, "source", None) == "placeholder_input":
                    fallback.append(output)
                else:
                    real.append(output)
        rows.append({"real": real, "fallback": fallback})
    return rows


def _unique_valid(values: object) -> list[Grid]:
    if not isinstance(values, (list, tuple)):
        return []
    unique: list[Grid] = []
    for value in values:
        if valid_grid(value) and value not in unique:
            unique.append(value)
    return unique


def _first_distinct(values: list[object], first: Grid) -> Grid | None:
    for value in values:
        if valid_grid(value) and value != first:
            return value
    return None


def merge_slots(
    legacy: object,
    hds_primary: object,
    hds_alternate: object,
    simple_transform: object,
    fallback_input: Grid,
) -> tuple[Grid, Grid]:
    """Use the recovered solver first and preserve HDS as its alternate."""
    row = legacy if isinstance(legacy, dict) else {}
    real = _unique_valid(row.get("real"))
    fallbacks = _unique_valid(row.get("fallback"))

    if real:
        first = real[0]
        second = _first_distinct(
            [hds_primary, hds_alternate, simple_transform, *real[1:], *fallbacks, fallback_input],
            first,
        )
        return first, second if second is not None else fallback_input

    first = hds_primary if valid_grid(hds_primary) else (fallbacks[0] if fallbacks else fallback_input)
    second = _first_distinct(
        [hds_alternate, simple_transform, *real, *fallbacks, fallback_input],
        first,
    )
    return first, second if second is not None else first
