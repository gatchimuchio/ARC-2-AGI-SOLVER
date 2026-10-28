"""固定済み公開training集団から、答えを分離した記憶介入用LOO課題を再現する。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def 作成(source: Path, cohort_manifest: Path, loo_manifest: Path, destination: Path):
    if destination.exists():
        raise FileExistsError("既存の実験ディレクトリは上書きしません")
    cohort = json.loads(cohort_manifest.read_text(encoding="utf-8"))
    specification = json.loads(loo_manifest.read_text(encoding="utf-8"))
    raw = source.read_bytes()
    if _sha(raw) != cohort["source_sha256"]:
        raise ValueError("training入力のhashが固定値と一致しません")
    source_tasks = json.loads(raw)
    ids = cohort["task_ids"]
    if len(ids) != 100 or len(set(ids)) != 100 or not set(ids) <= set(source_tasks):
        raise ValueError("固定対象100課題が不正です")
    selected = {task_id: source_tasks[task_id] for task_id in ids}
    frozen = _bytes(selected)
    if _sha(frozen) != cohort["challenges_sha256"] or _sha(frozen) != specification["source_cohort_sha256"]:
        raise ValueError("固定100課題のhashが一致しません")
    chosen = [(task_id, task) for task_id, task in sorted(selected.items())
              if len(task["train"]) == 2 and task["train"][0]["input"] != task["train"][1]["input"]]
    if len(chosen) != specification["selected_tasks"]:
        raise ValueError("選択課題数が固定条件と一致しません")
    inputs, solutions, mapping = {}, {}, {}
    for index, (task_id, task) in enumerate(chosen):
        for held in (0, 1):
            key = f"fold{index * 2 + held:03d}"
            inputs[key] = {"train": [task["train"][1 - held]],
                           "test": [{"input": task["train"][held]["input"]}]}
            solutions[key] = [task["train"][held]["output"]]
            mapping[key] = {"source_task": task_id, "held_training_example": held}
    if len(inputs) != specification["folds"]:
        raise ValueError("fold数が固定条件と一致しません")
    files = {"challenges.json": _bytes(inputs), "solutions-posthoc.json": _bytes(solutions),
             "fold-map.json": _bytes(mapping), "frozen100-challenges.json": frozen}
    for name, key in (("challenges.json", "challenge_sha256"),
                      ("solutions-posthoc.json", "posthoc_solutions_sha256"),
                      ("fold-map.json", "fold_map_sha256")):
        if _sha(files[name]) != specification[key]:
            raise ValueError(f"{name}のhashが固定値と一致しません")
    destination.mkdir(parents=True)
    for name, value in files.items():
        with (destination / name).open("xb") as stream:
            stream.write(value)
    return {name: _sha(value) for name, value in files.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "cohort-manifest", "loo-manifest", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(作成(args.source, args.cohort_manifest, args.loo_manifest, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
