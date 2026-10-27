"""Matched public-training LOO on the current main source snapshot.

The v61 bundle supplies only the payload file set and public training assets. Tracked
files are replaced with exact HEAD blobs; payload-only public training files are
retained, while non-training files absent from HEAD are removed. Only the candidate
copy's HDS family list is instrumented. Held-out outputs are scored after both
prediction streams return and never reach either solver.
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
OUTPUT = ROOT / "出力/検証/ARC2-current-main-candidate-tie-break-matched-loo-20261028.json"
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


def read_head_payload(manifest: dict, revision: str) -> dict[str, bytes]:
    tracked_raw = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", "--name-only", revision], cwd=ROOT
    )
    tracked = {item.decode("utf-8") for item in tracked_raw.split(b"\0") if item}
    paths = [record["path"] for record in manifest["files"] if record["path"] in tracked]
    archive_bytes = subprocess.check_output(
        ["git", "archive", "--format=zip", revision, *paths], cwd=ROOT
    )
    with zipfile.ZipFile(__import__("io").BytesIO(archive_bytes)) as archive:
        files = {
            name: archive.read(name)
            for name in archive.namelist()
            if not name.endswith("/")
        }
    if set(files) != set(paths):
        raise RuntimeError("HEAD payload archive omitted tracked bundle members")
    return files


def materialize_head_snapshot(root: Path, manifest: dict, head_files: dict[str, bytes]) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    retained_public_training = 0
    removed_absent_from_head = 0
    for record in manifest["files"]:
        relpath = record["path"]
        target = root.joinpath(*Path(relpath).parts)
        if relpath in head_files:
            content = head_files[relpath]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        elif relpath.startswith("入力/公式ソース/ARC-AGI-2/data/training/"):
            # Preserve a public training asset present in the exact Kaggle payload.
            if not target.is_file():
                raise RuntimeError("bundle-only public training asset is missing")
            content = target.read_bytes()
            retained_public_training += 1
        else:
            target.unlink(missing_ok=True)
            content = b"<absent-from-main>"
            removed_absent_from_head += 1
        digest.update(relpath.encode("utf-8") + b"\0" + sha256(content).encode("ascii") + b"\n")
    return digest.hexdigest(), retained_public_training, removed_absent_from_head


def patch_candidate_hds(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    family_anchor = "    記録群 = [候補機構を学習(機械, 課題, 教材, 境界, 候補器)\n"
    if source.count(family_anchor) != 1:
        raise RuntimeError("current-main HDS family-list anchor did not match exactly")
    insertion = (
        "    from .物体抽出候補 import ObjectExtractionCandidate\n"
        '    物体抽出HDS候補器 = ObjectExtractionCandidate(課題["train"])\n'
        '    機構群 = (*機構群, ("ARC物体抽出・切出しHDS", '
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
    env["PYTHONIOENCODING"] = "utf-8"
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
        return candidate_pair[0], candidate_pair[1]

    first = row.get("answer")
    first = first if adapter.格子か(first) else None
    anchor = first if first is not None else query
    records = row.get("candidate_predictions")
    records = list(records) if isinstance(records, list) else []

    composite_model = composite.CompositeGeometryCandidate(teachers)
    composite_grid, _ = composite_model.候補(query, {})
    if adapter.格子か(composite_grid) and composite_grid != anchor:
        records.append({"family": "ARC背景crop複合幾何変換", "answer": composite_grid})

    panel_model, _ = panel.fit_candidate(teachers)
    panel_grid = None
    if panel_model is not None:
        panel_grid, _ = panel.predict_candidate(query, panel_model)

    second = adapter._一意な別候補を選ぶ(records, anchor)
    if adapter.格子か(panel_grid) and panel_grid != anchor:
        second = adapter._一意な別候補を選ぶ(
            [*records, {"family": "ARC反復見本パネル照合候補", "answer": panel_grid}], anchor
        )

    simple_grid = simple.unique_candidate(teachers, query)
    if not adapter.格子か(second) or second == anchor:
        second = simple_grid if adapter.格子か(simple_grid) and simple_grid != anchor else None

    local_model = local.LocalCellContextCandidate(teachers)
    local_grid, _ = local_model.候補(query, {})
    if (not adapter.格子か(second) or second == anchor) and adapter.格子か(local_grid) and local_grid != anchor:
        second = local_grid

    if not adapter.格子か(second) or second == anchor:
        object_model = object_class(teachers)
        object_candidates = []
        for index, (kind, method) in enumerate((
            ("object", object_model.candidate),
            ("outlier", object_model.outlier_candidate),
            ("palette", object_model.palette_candidate),
        )):
            grid, details = method(query)
            if adapter.格子か(grid) and grid != anchor:
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
    second = second if adapter.格子か(second) and second != anchor else None
    return first, second


def _grid_change_cost(source: list, target: list) -> int:
    """Count cell edits plus dimensions changed, using no task metadata."""
    source_height = len(source)
    target_height = len(target)
    source_width = len(source[0])
    target_width = len(target[0])
    overlap_height = min(source_height, target_height)
    overlap_width = min(source_width, target_width)
    edits = sum(
        source[row][column] != target[row][column]
        for row in range(overlap_height)
        for column in range(overlap_width)
    )
    unmatched = source_height * source_width + target_height * target_width
    unmatched -= 2 * overlap_height * overlap_width
    return edits + unmatched + abs(source_height - target_height) + abs(source_width - target_width)


def tie_break_submission_pair(result, query, teachers, modules):
    """Fill only an empty second slot from tied, train-derived HDS candidates."""
    first, second = submission_pair(result, query, teachers, modules)
    if valid_grid(second) and second != (first if valid_grid(first) else query):
        return first, second, False
    rows = result.get("results", []) if isinstance(result, dict) else []
    row = rows[0] if rows and isinstance(rows[0], dict) else {}
    anchor = first if valid_grid(first) else query
    records = row.get("candidate_predictions")
    if not isinstance(records, list):
        return first, second, False
    votes: Counter[tuple[tuple[int, ...], ...]] = Counter()
    grids: dict[tuple[tuple[int, ...], ...], list] = {}
    families: dict[tuple[tuple[int, ...], ...], set[str]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        grid = record.get("answer")
        if not valid_grid(grid) or grid == anchor:
            continue
        key = tuple(tuple(row) for row in grid)
        votes[key] += 1
        grids[key] = grid
        family = record.get("family")
        if isinstance(family, str):
            families.setdefault(key, set()).add(family)
    if not votes:
        return first, second, False
    best_votes = max(votes.values())
    tied = [key for key, count in votes.items() if count == best_votes]
    chosen = min(
        tied,
        key=lambda key: (
            _grid_change_cost(query, grids[key]),
            tuple(sorted(families.get(key, set()))),
            key,
        ),
    )
    return first, grids[chosen], True

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

    source_revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="arc2-current-main-object-hds-loo-") as temp_name:
        temp = Path(temp_name)
        baseline_root, candidate_root = temp / "baseline", temp / "candidate"
        baseline_root.mkdir()
        candidate_root.mkdir()
        manifest, manifest_sha = extract_bundle(bundle_bytes, baseline_root)
        extract_bundle(bundle_bytes, candidate_root)
        head_payload_files = read_head_payload(manifest, source_revision)
        baseline_snapshot_sha, retained_training_count, removed_path_count = materialize_head_snapshot(
            baseline_root, manifest, head_payload_files
        )
        candidate_snapshot_sha, retained_candidate_training_count, removed_candidate_path_count = materialize_head_snapshot(
            candidate_root, manifest, head_payload_files
        )
        if (baseline_snapshot_sha != candidate_snapshot_sha
                or retained_training_count != retained_candidate_training_count
                or removed_path_count != removed_candidate_path_count):
            raise RuntimeError("baseline and candidate current-main snapshots diverged before the patch")
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
        # Held-out outputs are first read here, after both prediction streams returned.
        paired_count = previous_primary = current_primary = previous_pair = current_pair = 0
        tie_pair = tie_gains = tie_regressions = tie_fills = 0
        gains = regressions = 0
        previous_fallbacks = current_fallbacks = 0
        for (teachers, heldout, _proposed), old_result, new_result in zip(cases, baseline_results, candidate_results):
            old_first, old_second = submission_pair(old_result, heldout["input"], teachers, pair_modules) if old_result else (None, None)
            new_first, new_second = submission_pair(new_result, heldout["input"], teachers, pair_modules) if new_result else (None, None)
            tie_first, tie_second, tie_filled = tie_break_submission_pair(
                new_result, heldout["input"], teachers, pair_modules
            ) if new_result else (None, None, False)
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
            tie_pair_ok = (
                (tie_first is not None and tie_first == target)
                or (tie_second is not None and tie_second == target)
            )
            paired_count += 1
            previous_primary += int(old_primary_ok)
            current_primary += int(new_primary_ok)
            previous_pair += int(old_pair_ok)
            current_pair += int(new_pair_ok)
            gains += int(new_pair_ok and not old_pair_ok)
            regressions += int(old_pair_ok and not new_pair_ok)
            tie_pair += int(tie_pair_ok)
            tie_gains += int(tie_pair_ok and not new_pair_ok)
            tie_regressions += int(new_pair_ok and not tie_pair_ok)
            tie_fills += int(tie_filled)

        output = {
            "schema": "arc2-current-main-candidate-tie-break-matched-loo-v1",
            "run_id": "ARC2-current-main-candidate-tie-break-matched-loo-20261028",
            "evaluation_script_sha256": sha256(Path(__file__).read_bytes()),
            "status": "COMPLETE" if paired_count == len(cases) else "COMPLETE_WITH_WORKER_ERRORS",
            "track": "ARC2",
            "current_main_revision": source_revision,
            "current_main_payload_manifest_sha256": baseline_snapshot_sha,
            "seed_bundle_sha256": bundle_sha,
            "seed_bundle_manifest_sha256": manifest_sha,
            "payload_member_count": len(manifest["files"]),
            "bundle_only_public_training_file_count_retained": retained_training_count,
            "bundle_paths_absent_from_main_removed": removed_path_count,
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
            "current_candidate_pair_exact_before_tie_break": current_pair,
            "current_candidate_pair_exact_after_tie_break": tie_pair,
            "tie_break_pair_delta": tie_pair - current_pair,
            "tie_break_gains": tie_gains,
            "tie_break_regressions": tie_regressions,
            "tie_break_filled_empty_second_slots": tie_fills,
            "previous_fallbacks": previous_fallbacks,
            "current_fallbacks": current_fallbacks,
            "fallback_counted_correct": False,
            "fallback_policy": "missing primary or secondary prediction is None and excluded from exact scoring; input-copy fallback is never credited",
            "selection_method": "Preserve current pair; only fill an empty secondary slot from tied HDS candidate_predictions by highest family vote, then minimal cell/dimension edit from input, then stable family/grid ordering. Scored in-memory after both solver streams return.",
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
        print(json.dumps(output, ensure_ascii=True, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
