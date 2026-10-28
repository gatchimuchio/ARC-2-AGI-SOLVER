"""既存観測・事前教材と重ならない追加公開training入力を固定する。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SEED = "ARC2-v7-additional-training-cohort-20261028"


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def 作成(source: Path, visible_test: Path, previous_holdout: Path, fold_map: Path,
       generic_prior: Path, destination: Path):
    if destination.exists():
        raise FileExistsError("既存の実験ディレクトリは上書きしません")
    raw = source.read_bytes()
    if _sha(raw) != "779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5":
        raise ValueError("training入力が固定された版ではありません")
    tasks = json.loads(raw)
    test = json.loads(visible_test.read_text(encoding="utf-8"))
    previous = json.loads(previous_holdout.read_text(encoding="utf-8"))
    folds = json.loads(fold_map.read_text(encoding="utf-8"))
    prior = json.loads(generic_prior.read_text(encoding="utf-8"))
    if prior.get("source_split") != "training" or len(prior.get("examples", [])) != 279:
        raise ValueError("事前教材が固定されたtraining由来の279例ではありません")
    prior_pairs = {_sha(_bytes(example)) for example in prior["examples"]}
    excluded = set(test) | set(previous) | {entry["source_task"] for entry in folds.values()}
    overlap = {task_id for task_id, task in tasks.items()
               if any(_sha(_bytes(pair)) in prior_pairs for pair in task["train"])}
    excluded |= overlap
    eligible = set(tasks) - excluded
    ranked = sorted(eligible, key=lambda task_id: hashlib.sha256((SEED + "\0" + task_id).encode()).digest())
    chosen = sorted(ranked[:100])
    if len(chosen) != 100 or len(set(chosen)) != 100:
        raise ValueError("十分な課題を選べません")
    cohort = {task_id: tasks[task_id] for task_id in chosen}
    if any(set(task) != {"train", "test"} or any(set(pair) != {"input"} for pair in task["test"])
           for task in cohort.values()):
        raise ValueError("test正解または余分な入力が含まれています")
    challenge = _bytes(cohort)
    manifest = {"schema": "arc2-v7-additional-training-cohort-v1", "seed": SEED,
                "source_sha256": _sha(raw), "generic_prior_sha256": _sha(generic_prior.read_bytes()),
                "visible_test_sha256": _sha(visible_test.read_bytes()),
                "previous_holdout_sha256": _sha(previous_holdout.read_bytes()),
                "fold_map_sha256": _sha(fold_map.read_bytes()),
                "selection_id_sha256": _sha(_bytes(chosen)), "challenge_sha256": _sha(challenge),
                "selected_tasks": len(chosen), "test_grids": sum(len(x["test"]) for x in cohort.values()),
                "excluded_task_count": len(excluded), "prior_pair_overlap_task_count": len(overlap),
                "prior_exposure_limit": "Earlier development exposure outside these exclusions is not established.",
                "answers_read": False}
    destination.mkdir(parents=True)
    for name, data in (("challenges.json", challenge), ("manifest.json", _bytes(manifest))):
        with (destination / name).open("xb") as stream:
            stream.write(data)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "visible-test", "previous-holdout", "fold-map", "generic-prior", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(作成(args.source, args.visible_test, args.previous_holdout,
                        args.fold_map, args.generic_prior, args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
