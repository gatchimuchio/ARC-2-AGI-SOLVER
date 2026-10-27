"""Matched public-training LOO for routing the generic object candidate through HDS admission.

The frozen v61 bundle is copied to temporary roots. Only the candidate copy's HDS
family list and aggregate diagnostic are instrumented. Held-out outputs are never
passed to either solver and are inspected only after both predictions return.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BUNDLE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026/bundle.zip"
OUTPUT = ROOT / "出力/検証/ARC2-v61-object-candidate-hds-admission-matched-loo-20261027.json"
EXPECTED_BUNDLE_SHA256 = "06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee"
EXPECTED_TRAINING_MANIFEST_SHA256 = "10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8"
TASK_TIMEOUT_SECONDS = 90


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_grid(grid) -> bool:
    return (
        isinstance(grid, list) and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list) and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def prior_source_ids(root: Path) -> set[str]:
    manifest = json.loads(
        (root / "接続/ARC2/テンプレート充填教材.json").read_text(encoding="utf-8")
    )
    return {row["課題ID"] for row in manifest["教材"]}


def extract_bundle(bundle_bytes: bytes, root: Path) -> tuple[dict, str]:
    with zipfile.ZipFile(__import__("io").BytesIO(bundle_bytes)) as archive:
        names = archive.namelist()
        manifest_bytes = archive.read("__arc2_bundle_manifest__.json")
        manifest = json.loads(manifest_bytes)
        expected = {row["path"]: row for row in manifest["files"]}
        if not names or set(names[1:]) != set(expected):
            raise RuntimeError("frozen bundle manifest and members differ")
        for name in names[1:]:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise RuntimeError("unsafe frozen bundle member")
            content = archive.read(name)
            record = expected[name]
            if len(content) != record["size"] or sha256(content) != record["sha256"]:
                raise RuntimeError("frozen bundle member checksum mismatch")
            target = root.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return manifest, sha256(manifest_bytes)


def patch_candidate_hds(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    import_anchor = "from .有限例外光線教材 import 有限例外光線教材\n"
    family_anchor = "    記録群 = []\n"
    if source.count(import_anchor) != 1 or source.count(family_anchor) != 1:
        raise RuntimeError("frozen HDS insertion anchors did not match exactly")
    source = source.replace(
        import_anchor,
        import_anchor + "from .物体抽出候補 import ObjectExtractionCandidate\n",
        1,
    )
    insertion = (
        '    物体抽出HDS候補器 = ObjectExtractionCandidate(課題["train"])\n'
        '    機構群.append(("ARC物体抽出・切出しHDS", '
        'lambda grid, _expected: 物体抽出HDS候補器.candidate(grid), ()))\n'
    )
    source = source.replace(family_anchor, insertion + family_anchor, 1)
    path.write_text(source, encoding="utf-8", newline="\n")
    return sha256(source.encode("utf-8"))


def purge_arc_modules() -> None:
    for name in list(sys.modules):
        if name == "接続" or name.startswith("接続.") or name == "hds学習系統" or name.startswith("hds学習系統."):
            del sys.modules[name]


def load_object_candidate(root: Path):
    purge_arc_modules()
    sys.path[:] = [str(root), str(root / "HDS/学習系統/v0.4.2")] + [
        item for item in sys.path
        if item not in {str(root), str(root / "HDS/学習系統/v0.4.2")}
    ]
    return importlib.import_module("接続.ARC2.物体抽出候補").ObjectExtractionCandidate


def run_worker(driver: Path, root: Path, task: dict) -> tuple[dict | None, str | None]:
    env = os.environ.copy()
    env["ARC2_PAYLOAD_ROOT"] = str(root)
    env["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"
    try:
        process = subprocess.run(
            [sys.executable, str(driver)],
            input=json.dumps(task, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=TASK_TIMEOUT_SECONDS,
            cwd=root,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "task_wall_timeout"
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    if process.returncode != 0 or not lines:
        return None, "worker_error"
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None, "invalid_worker_json"
    if "error" in result or not isinstance(result.get("results"), list):
        return None, "worker_error"
    return result, None


def score_pair(result: dict | None, query: list) -> tuple[list | None, list | None]:
    if result is None:
        return None, None
    rows = result.get("results", [])
    row = rows[0] if rows and isinstance(rows[0], dict) else {}
    first = row.get("answer")
    second = row.get("second_answer")
    first = first if valid_grid(first) and first != query else None
    second = second if valid_grid(second) and second != query else None
    return first, second


def submission_pair(result, query, teachers, modules):
    adapter, simple, panel, composite, local, object_class = modules
    rows = result.get("results", []) if isinstance(result, dict) else []
    row = rows[0] if rows and isinstance(rows[0], dict) else {}
    candidate_pair = row.get("candidate_attempts")
    if (
        isinstance(candidate_pair, list) and len(candidate_pair) == 2
        and all(adapter.格子か(grid) for grid in candidate_pair)
        and candidate_pair[0] != candidate_pair[1]
    ):
        first, second = candidate_pair
        return first, second

    first = row.get("answer")
    if not adapter.格子か(first):
        first = query
    records = list(row.get("candidate_predictions", []))

    composite_model = composite.CompositeGeometryCandidate(teachers)
    composite_grid, _ = composite_model.候補(query, {})
    if adapter.格子か(composite_grid) and composite_grid != first:
        records.append({"family": "ARC背景crop複合幾何変換", "answer": composite_grid})

    panel_model, _ = panel.fit_candidate(teachers)
    panel_grid = None
    if panel_model is not None:
        panel_grid, _ = panel.predict_candidate(query, panel_model)

    second = adapter._一意な別候補を選ぶ(records, first)
    if adapter.格子か(panel_grid) and panel_grid != first:
        second = adapter._一意な別候補を選ぶ(
            [*records, {"family": "ARC反復見本パネル照合候補", "answer": panel_grid}], first
        )

    simple_grid = simple.unique_candidate(teachers, query)
    if not adapter.格子か(second) or second == first:
        second = simple_grid if adapter.格子か(simple_grid) and simple_grid != first else None

    local_model = local.LocalCellContextCandidate(teachers)
    local_grid, _ = local_model.候補(query, {})
    if (not adapter.格子か(second) or second == first) and adapter.格子か(local_grid) and local_grid != first:
        second = local_grid

    if not adapter.格子か(second) or second == first:
        object_model = object_class(teachers)
        object_candidates = []
        for index, (kind, method) in enumerate((
            ("object", object_model.candidate),
            ("outlier", object_model.outlier_candidate),
            ("palette", object_model.palette_candidate),
        )):
            grid, details = method(query)
            if adapter.格子か(grid) and grid != first:
                object_candidates.append((index, kind, grid, details))
        if object_candidates:
            _, _, second, _ = max(
                object_candidates,
                key=lambda item: (
                    int(item[3].get("top_votes", 0))
                    / max(1, int(item[3].get("applicable_models", 0))),
                    int(item[3].get("top_votes", 0)),
                    -item[0],
                ),
            )
    return first, second if adapter.格子か(second) and second != first else query


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    bundle_bytes = BUNDLE.read_bytes()
    bundle_sha = sha256(bundle_bytes)
    if bundle_sha != EXPECTED_BUNDLE_SHA256:
        raise RuntimeError("frozen v61 bundle checksum mismatch")
    training_files = sorted(TRAINING.glob("*.json"))
    training_digest = hashlib.sha256()
    for path in training_files:
        raw = path.read_bytes()
        training_digest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
    if training_digest.hexdigest() != EXPECTED_TRAINING_MANIFEST_SHA256:
        raise RuntimeError("public training manifest differs from the recorded LOO cohort")

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="arc2-v61-object-hds-loo-") as temp_name:
        temp = Path(temp_name)
        baseline_root, candidate_root = temp / "baseline", temp / "candidate"
        baseline_root.mkdir()
        candidate_root.mkdir()
        manifest, manifest_sha = extract_bundle(bundle_bytes, baseline_root)
        extract_bundle(bundle_bytes, candidate_root)
        candidate_hds_sha = patch_candidate_hds(candidate_root / "接続/ARC2/HDS接続.py")
        candidate_wrapper_sha = sha256((candidate_root / "接続/ARC2/Kaggle提出.py").read_bytes())
        baseline_hds_sha = sha256((baseline_root / "接続/ARC2/HDS接続.py").read_bytes())
        baseline_wrapper_sha = sha256((baseline_root / "接続/ARC2/Kaggle提出.py").read_bytes())
        prior_ids = prior_source_ids(baseline_root)

        driver = temp / "run_worker.py"
        driver.write_text(
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "root = Path(os.environ['ARC2_PAYLOAD_ROOT'])\n"
            "sys.path[:0] = [str(root), str(root / 'HDS/学習系統/v0.4.2')]\n"
            "from 接続.ARC2.HDS接続 import 課題を解く, 事前教材を読む\n"
            "task = json.load(sys.stdin)\n"
            "result = 課題を解く(task, 事前教材を読む(), 候補収集=True, 観測診断=True)\n"
            "print(json.dumps(result, ensure_ascii=False), flush=True)\n",
            encoding="utf-8",
            newline="\n",
        )

        ObjectCandidate = load_object_candidate(baseline_root)
        adapter = importlib.import_module("接続.ARC2.Kaggle提出")
        simple = importlib.import_module("接続.ARC2.単純変換候補")
        panel = importlib.import_module("接続.ARC2.埋込見本一致候補")
        composite = importlib.import_module("接続.ARC2.複合幾何変換候補")
        local = importlib.import_module("接続.ARC2.局所近傍変換候補")
        pair_modules = (adapter, simple, panel, composite, local, ObjectCandidate)
        cases = []
        scanned_folds = 0
        excluded_tasks = 0
        for path in training_files:
            if path.stem in prior_ids:
                excluded_tasks += 1
                continue
            examples = json.loads(path.read_text(encoding="utf-8")).get("train", [])
            if len(examples) < 3:
                continue
            for heldout_index, heldout in enumerate(examples):
                teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
                selector = ObjectCandidate(teachers)
                proposed, _ = selector.candidate(heldout["input"])
                scanned_folds += 1
                if valid_grid(proposed) and proposed != heldout["input"]:
                    # Store the held-out pair only in memory. The worker receives input and teachers only.
                    cases.append((teachers, heldout, proposed))
        if not cases:
            raise RuntimeError("the frozen object candidate produced no eligible LOO folds")

        baseline_results = []
        candidate_results = []
        baseline_errors: Counter[str] = Counter()
        candidate_errors: Counter[str] = Counter()
        admission: Counter[str] = Counter()
        for teachers, heldout, _proposed in cases:
            task = {"train": teachers, "test": [{"input": heldout["input"]}]}
            result, error = run_worker(driver, baseline_root, task)
            baseline_errors[error] += int(error is not None)
            baseline_results.append(result)
            result, error = run_worker(driver, candidate_root, task)
            candidate_errors[error] += int(error is not None)
            candidate_results.append(result)
            if result is not None:
                diag = result.get("aggregate_diagnostics", {}).get("hds_object_extraction_admission", {})
                if diag.get("fit_eligible") and diag.get("equality_admitted"):
                    admission["jointly_admitted"] += 1
                elif diag.get("fit_eligible"):
                    admission["fit_only"] += 1
                elif diag:
                    admission[str(diag.get("state", "other"))] += 1
                else:
                    admission["diagnostic_missing"] += 1

        # Held-out outputs are first read here, after both prediction streams returned.
        paired_count = previous_primary = current_primary = previous_pair = current_pair = 0
        gains = regressions = 0
        previous_fallbacks = current_fallbacks = 0
        for (teachers, heldout, _proposed), old_result, new_result in zip(cases, baseline_results, candidate_results):
            old_first, old_second = submission_pair(old_result, heldout["input"], teachers, pair_modules) if old_result else (None, None)
            new_first, new_second = submission_pair(new_result, heldout["input"], teachers, pair_modules) if new_result else (None, None)
            if new_result is not None:
                family = next((
                    item for item in new_result.get("families", [])
                    if item.get("境界") == "ARC物体抽出・切出しHDS"
                ), {})
                if family.get("採用可") and family.get("同値採用"):
                    admission["jointly_admitted"] += 1
                elif family.get("採用可"):
                    admission["fit_only"] += 1
                else:
                    admission[str(family.get("状態", "family_record_missing"))] += 1
            previous_fallbacks += int(old_first is None)
            current_fallbacks += int(new_first is None)
            if old_result is None or new_result is None:
                continue
            target = heldout["output"]
            old_primary_ok = old_first is not None and old_first == target
            new_primary_ok = new_first is not None and new_first == target
            old_pair_ok = old_primary_ok or (old_second is not None and old_second == target)
            new_pair_ok = new_primary_ok or (new_second is not None and new_second == target)
            paired_count += 1
            previous_primary += int(old_primary_ok)
            current_primary += int(new_primary_ok)
            previous_pair += int(old_pair_ok)
            current_pair += int(new_pair_ok)
            gains += int(new_pair_ok and not old_pair_ok)
            regressions += int(old_pair_ok and not new_pair_ok)

        output = {
            "schema": "arc2-v61-object-candidate-hds-admission-matched-loo-v1",
            "status": "COMPLETE" if paired_count == len(cases) else "COMPLETE_WITH_WORKER_ERRORS",
            "track": "ARC2",
            "frozen_bundle_sha256": bundle_sha,
            "bundle_manifest_sha256": manifest_sha,
            "bundle_member_count": len(manifest["files"]),
            "baseline_hds_sha256": baseline_hds_sha,
            "baseline_wrapper_sha256": baseline_wrapper_sha,
            "candidate_hds_sha256": candidate_hds_sha,
            "candidate_wrapper_sha256": candidate_wrapper_sha,
            "training_manifest_sha256": training_digest.hexdigest(),
            "training_task_files": len(training_files),
            "excluded_static_prior_task_count": excluded_tasks,
            "eligible_folds_scanned": scanned_folds,
            "candidate_folds_evaluated": len(cases),
            "task_timeout_seconds": TASK_TIMEOUT_SECONDS,
            "baseline_worker_errors": dict(baseline_errors),
            "candidate_worker_errors": dict(candidate_errors),
            "hds_object_candidate_admission": dict(admission),
            "paired_folds_scored": paired_count,
            "previous_primary_exact": previous_primary,
            "current_primary_exact": current_primary,
            "delta_primary_exact": current_primary - previous_primary,
            "previous_pair_exact": previous_pair,
            "current_pair_exact": current_pair,
            "delta_pair_exact": current_pair - previous_pair,
            "paired_gains": gains,
            "paired_regressions": regressions,
            "previous_fallbacks": previous_fallbacks,
            "current_fallbacks": current_fallbacks,
            "fallback_counted_correct": False,
            "selection_method": "matched v61 candidate-source emulation over HDS predictions, simple transforms, repeated-panel, composite geometry, local context, and object extraction/outlier/palette; worker process wrapper omitted for runtime",
            "heldout_output_passed_to_solver": False,
            "heldout_outputs_scored_after_both_workers_return": True,
            "task_ids_or_raw_grids_persisted": False,
            "hidden_or_evaluation_solutions_read": False,
            "production_source_changed": False,
            "official_submission_performed": False,
            "official_score": None,
            "runtime_seconds": round(time.perf_counter() - started, 3),
        }
        OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(output, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
