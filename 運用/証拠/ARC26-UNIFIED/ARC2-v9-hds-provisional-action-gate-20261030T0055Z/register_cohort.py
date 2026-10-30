#!/usr/bin/env python3
"""Register a label-free ARC2 public-training cohort before making predictions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[4]
RUN_DIR = Path(__file__).resolve().parent
TRAIN_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
SYMBOLIC_PREREG = (
    ROOT
    / "運用/証拠/ARC26-UNIFIED/"
    / "ARC2-v9-symbolic-program-integration-20261029T2222Z/preregistration.json"
)
FIXED_COHORT = Path(os.environ["TEMP"]) / "arc2-v9-independent-holdout-20261029/cohort.json"
SEED = "ARC2-v9-provisional-action-gate-20261030T0055Z"
EXPECTED_TRAIN_TASKS = 1000
EXPECTED_PRIOR_EXCLUSIONS = 596
SELECTED_TASKS = 100


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def task_signature(task: object) -> str | None:
    if not isinstance(task, dict):
        return None
    train = task.get("train")
    tests = task.get("test")
    if not isinstance(train, list) or not isinstance(tests, list):
        return None
    try:
        normalized_train = []
        for pair in train:
            if not isinstance(pair, dict) or not {"input", "output"} <= pair.keys():
                return None
            normalized_train.append({"input": pair["input"], "output": pair["output"]})
        normalized_test = []
        for pair in tests:
            if not isinstance(pair, dict) or "input" not in pair:
                return None
            normalized_test.append({"input": pair["input"]})
    except (KeyError, TypeError):
        return None
    payload = {"train": normalized_train, "test": normalized_test}
    return hashlib.sha256(canonical(payload)).hexdigest()


def walk(value: object):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk(nested)


def parse_documents(raw: bytes) -> list[object]:
    try:
        return [json.loads(raw)]
    except (UnicodeDecodeError, json.JSONDecodeError):
        documents = []
        for line in raw.splitlines():
            try:
                documents.append(json.loads(line))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return documents


def referenced_task_ids(document: object, known_ids: set[str]) -> set[str]:
    found: set[str] = set()
    def visit(value: object, key: str | None = None) -> None:
        if isinstance(value, str):
            if value in known_ids:
                found.add(value)
            if key in {"path", "file", "source_file"} and value.lower().endswith(".json"):
                normalized = value.replace("\\", "/")
                stem = Path(normalized).stem
                if stem in known_ids and (
                    "/training/" in normalized.lower() or key == "source_file"
                ):
                    found.add(stem)
        elif isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, child_key)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    return found


def read_source_tasks() -> tuple[dict[str, dict], dict[str, str], str]:
    files = sorted(TRAIN_DIR.glob("*.json"))
    if len(files) != EXPECTED_TRAIN_TASKS:
        raise SystemExit(f"expected {EXPECTED_TRAIN_TASKS} training tasks, found {len(files)}")
    tasks: dict[str, dict] = {}
    file_hashes: dict[str, str] = {}
    for path in files:
        raw = path.read_bytes()
        task = json.loads(raw)
        if not isinstance(task, dict) or not task.get("train") or not task.get("test"):
            raise SystemExit(f"invalid ARC2 training task: {path.name}")
        if any(not isinstance(pair, dict) or "input" not in pair for pair in task["test"]):
            raise SystemExit(f"training task lacks a test input: {path.name}")
        tasks[path.stem] = task
        file_hashes[path.name] = hashlib.sha256(raw).hexdigest()
    inventory_sha = hashlib.sha256(canonical(file_hashes)).hexdigest()
    return tasks, file_hashes, inventory_sha


def main() -> None:
    for output in ("challenge_input.json", "selection_manifest.json", "preregistration.json"):
        if (RUN_DIR / output).exists():
            raise SystemExit(f"refusing to overwrite existing cohort artifact: {output}")

    tasks, source_hashes, source_inventory_sha = read_source_tasks()
    known_ids = set(tasks)
    signature_to_ids: dict[str, set[str]] = defaultdict(set)
    signatures: dict[str, str] = {}
    for task_id, task in tasks.items():
        signature = task_signature(task)
        if signature is None:
            raise SystemExit(f"could not build input-only signature: {task_id}")
        signatures[task_id] = signature
        signature_to_ids[signature].add(task_id)

    symbolic = json.loads(SYMBOLIC_PREREG.read_text(encoding="utf-8"))
    manifest = symbolic["cohort"]["exclusion_evidence_manifest"]
    id_hits: set[str] = set()
    content_hits: set[str] = set()
    path_hits: set[str] = set()
    mismatches = []
    missing = []
    undercounts = []
    parsed_paths = []

    for item in manifest:
        evidence_path = (ROOT / Path(item["path"])).resolve()
        if not evidence_path.is_relative_to(ROOT.resolve()):
            raise SystemExit("registered evidence path escaped repository")
        if not evidence_path.is_file():
            missing.append(item["path"])
            continue
        raw = evidence_path.read_bytes()
        current_sha = hashlib.sha256(raw).hexdigest()
        if current_sha != item["sha256"]:
            mismatches.append(
                {
                    "path": item["path"],
                    "registered_sha256": item["sha256"],
                    "current_sha256": current_sha,
                }
            )
        direct: set[str] = set()
        signatures_found: set[str] = set()
        paths_found: set[str] = set()
        for document in parse_documents(raw):
            parsed_paths.append(item["path"])
            direct.update(referenced_task_ids(document, known_ids))
            for node in walk(document):
                signature = task_signature(node)
                if signature is not None:
                    signatures_found.update(signature_to_ids.get(signature, set()))
            paths_found.update(referenced_task_ids(document, known_ids))
        found = direct | signatures_found | paths_found
        expected = item.get("matched_public_task_ids", 0)
        if len(found) < expected:
            undercounts.append(
                {"path": item["path"], "registered": expected, "reconstructed": len(found)}
            )
        id_hits.update(direct)
        content_hits.update(signatures_found)
        path_hits.update(paths_found)

    if missing or undercounts:
        raise SystemExit(
            "prior exposure evidence is incomplete: "
            + json.dumps({"missing": missing, "undercounts": undercounts}, ensure_ascii=False)
        )

    fixed_raw = FIXED_COHORT.read_bytes()
    fixed_sha = hashlib.sha256(fixed_raw).hexdigest()
    fixed_doc = json.loads(fixed_raw)
    fixed_ids = referenced_task_ids(fixed_doc, known_ids)
    fixed_signatures: set[str] = set()
    for node in walk(fixed_doc):
        signature = task_signature(node)
        if signature is not None:
            fixed_signatures.update(signature_to_ids.get(signature, set()))

    previous_ids = set(symbolic["cohort"]["selected_public_training_task_ids"])
    if len(previous_ids) != 100 or not previous_ids <= known_ids:
        raise SystemExit("previous symbolic cohort is incomplete or outside the training inventory")
    previous_signatures = {signatures[task_id] for task_id in previous_ids if task_id in signatures}
    previous_aliases = set().union(*(signature_to_ids[s] for s in previous_signatures))
    exposure_seeds = id_hits | content_hits | path_hits | fixed_ids | fixed_signatures
    registered_exposure_ids = set(exposure_seeds)
    for task_id in tuple(exposure_seeds):
        registered_exposure_ids.update(signature_to_ids[signatures[task_id]])
    previous_aliases.update(
        alias
        for task_id in previous_ids
        if task_id in signatures
        for alias in signature_to_ids[signatures[task_id]]
    )
    excluded = registered_exposure_ids | previous_aliases
    if len(registered_exposure_ids) < EXPECTED_PRIOR_EXCLUSIONS:
        raise SystemExit(
            f"reconstructed {len(registered_exposure_ids)} prior exclusions; "
            f"expected at least {EXPECTED_PRIOR_EXCLUSIONS}"
        )

    by_signature: dict[str, list[str]] = defaultdict(list)
    for task_id in known_ids - excluded:
        by_signature[signatures[task_id]].append(task_id)
    eligible = [(signature, sorted(task_ids)[0]) for signature, task_ids in by_signature.items()]
    eligible.sort(key=lambda row: hashlib.sha256((SEED + "\0" + row[0]).encode()).hexdigest())
    selected = eligible[:SELECTED_TASKS]
    if len(selected) != SELECTED_TASKS:
        raise SystemExit(f"only {len(selected)} unique eligible tasks remain")

    challenge: dict[str, dict] = {}
    selected_source = []
    grid_count = 0
    for index, (signature, task_id) in enumerate(selected, 1):
        alias = f"cohort_{index:03d}"
        task = tasks[task_id]
        challenge[alias] = {
            "train": [
                {"input": pair["input"], "output": pair["output"]}
                for pair in task["train"]
            ],
            "test": [{"input": pair["input"]} for pair in task["test"]],
        }
        grid_count += len(task["test"])
        selected_source.append(
            {
                "alias": alias,
                "public_training_task_id": task_id,
                "input_signature_sha256": signature,
                "source_file_sha256": source_hashes[f"{task_id}.json"],
                "test_grid_count": len(task["test"]),
            }
        )

    challenge_raw = (json.dumps(challenge, ensure_ascii=False, indent=2) + "\n").encode()
    (RUN_DIR / "challenge_input.json").write_bytes(challenge_raw)
    selection = {
        "selection_seed": SEED,
        "selection_method": "SHA256(seed + NUL + input-only normalized task signature); first 100 unique eligible signatures",
        "official_training_task_count": len(tasks),
        "prior_evidence_file_count": len(manifest),
        "prior_evidence_sha_mismatch_count": len(mismatches),
        "prior_evidence_sha_mismatches": mismatches,
        "prior_evidence_missing_file_count": len(missing),
        "prior_manifest_expected_exclusions": symbolic["cohort"]["union_excluded_task_ids"],
        "reconstructed_prior_exclusions": len(registered_exposure_ids),
        "previous_symbolic_cohort_aliases_excluded": len(previous_aliases),
        "remaining_unique_signature_count": len(eligible),
        "remaining_source_task_alias_count": sum(len(values) for values in by_signature.values()),
        "selected_task_count": len(selected),
        "selected_test_grid_count": grid_count,
        "runtime_input_sha256": hashlib.sha256(challenge_raw).hexdigest(),
        "source_training_inventory_sha256": source_inventory_sha,
        "fixed100_input_sha256": fixed_sha,
        "selected_source_tasks": selected_source,
    }
    selection_raw = (json.dumps(selection, ensure_ascii=False, indent=2) + "\n").encode()
    (RUN_DIR / "selection_manifest.json").write_bytes(selection_raw)
    prereg = {
        "schema": "arc2-v9-provisional-action-gate-prereg-v1",
        "run_id": SEED,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "registered_before_prediction": True,
        "track": "ARC2",
        "purpose": "Paired G2 pilot: preserve the current HDS-admitted path and test whether a train-exact generic candidate rejected only by the HDS equality gate can still be exposed as an explicitly unconfirmed provisional action.",
        "conditions": {
            "previous": "Current behavior: only candidates with full train fit and HDS equality admission reach the action candidate list.",
            "candidate": "For symbolic_program_induction only, retain a valid candidate with full public-train fit as provisional when HDS equality admission is absent; record hds_admitted=false and do not alter HDS truth/admission state.",
            "fixed": "Same source data, HDS engine, candidate generators, input order, runtime limits, and two-attempt selector.",
        },
        "primary_metrics": ["pass@1", "pass@2", "unique_attempt2_hits", "fallback", "candidate_coverage", "wall"],
        "not_a_full_abcd_result": True,
        "exposure_status": "unknown",
        "exposure_reason": "Six prior evidence files differ from their registered SHA256; their current ID, input-signature, and training-file references were included in exclusions, but historical bytes are not proven identical.",
        "runtime_task_id_or_hash_routing": False,
        "runtime_reads_test_outputs": False,
        "runtime_input_file": "challenge_input.json",
        "runtime_input_sha256": hashlib.sha256(challenge_raw).hexdigest(),
        "task_count": len(challenge),
        "test_grid_count": grid_count,
        "prior_exclusions_reconstructed": len(registered_exposure_ids),
        "fresh_remainder_before_selection": len(eligible),
        "prior_evidence_manifest_sha256": hashlib.sha256(SYMBOLIC_PREREG.read_bytes()).hexdigest(),
        "prior_evidence_sha_mismatches": mismatches,
        "selection_manifest_sha256": hashlib.sha256(selection_raw).hexdigest(),
        "source_training_inventory_sha256": source_inventory_sha,
        "prediction_status": "NOT_STARTED",
        "test_output_access": "forbidden until all A/B/C/D predictions and their hashes are frozen",
    }
    (RUN_DIR / "preregistration.json").write_text(
        json.dumps(prereg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "state": prereg["prediction_status"],
                "task_count": len(challenge),
                "test_grid_count": grid_count,
                "prior_exclusions": len(registered_exposure_ids),
                "remaining_unique_signatures": len(eligible),
                "sha_mismatches": len(mismatches),
                "runtime_input_sha256": prereg["runtime_input_sha256"],
                "selection_manifest_sha256": prereg["selection_manifest_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
