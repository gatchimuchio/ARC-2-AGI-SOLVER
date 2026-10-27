"""Build a local v61 bundle with teacher-pair object consensus as a final fallback."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BUILDS = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1"
PARENT = BUILDS / "v51-largest-component-background-20261026"
PROBE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-teacher-pair-consensus-v61-exact-paired-20261026.py"
OUTPUT = BUILDS / "v61-object-teacher-pair-consensus-20261026"
MANIFEST_NAME = "__arc2_bundle_manifest__.json"
OBJECT_PATH = "接続/ARC2/物体抽出候補.py"
ADAPTER_PATH = "接続/ARC2/Kaggle提出.py"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_files(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names or names[0] != MANIFEST_NAME:
            raise ValueError("parent bundle manifest is missing")
        manifest = json.loads(archive.read(MANIFEST_NAME))
        expected = {row["path"] for row in manifest["files"]}
        if set(names[1:]) != expected:
            raise ValueError("parent bundle file set differs from its manifest")
        return {name: archive.read(name) for name in names[1:]}


def patch_object_module(parent_source: str) -> str:
    tree = ast.parse(parent_source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ObjectExtractionCandidate"
    )
    candidate_method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "candidate"
    )
    helper_source = '''
def _candidate_from_models_one_vote(
    models: list[Model], test_input: Grid, *, outlier: bool = False
) -> tuple[Grid | None, dict[str, int]]:
    if not _valid_grid(test_input):
        return None, {"fitted_models": len(models), "applicable_models": 0}
    predictions: Counter[GridKey] = Counter()
    grids: dict[GridKey, Grid] = {}
    applicable = 0
    for model in models:
        output = _apply(model, test_input, outlier=outlier)
        if output is None:
            continue
        applicable += 1
        key = _grid_key(output)
        predictions[key] += 1
        grids[key] = output
    if not predictions:
        return None, {"fitted_models": len(models), "applicable_models": 0}
    top_votes = max(predictions.values())
    winners = [key for key, votes in predictions.items() if votes == top_votes]
    candidate = grids[winners[0]] if len(winners) == 1 else None
    return candidate, {
        "fitted_models": len(models),
        "applicable_models": applicable,
        "distinct_predictions": len(predictions),
        "top_votes": top_votes,
    }

'''
    lines = parent_source.splitlines(keepends=True)
    lines.insert(cls.lineno - 1, helper_source)
    source = "".join(lines)
    tree = ast.parse(source)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ObjectExtractionCandidate"
    )
    candidate_method = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "candidate"
    )
    pair_method = '''    def teacher_pair_consensus_candidate(
        self, test_input: Grid
    ) -> tuple[Grid | None, dict[str, int]]:
        """Return an output supported by multiple independently fit teacher pairs."""
        if not _valid_grid(test_input) or len(self.teachers) < 2:
            return None, {"top_votes": 0, "applicable_models": 0}
        pair_models = getattr(self, "_teacher_pair_models", None)
        if pair_models is None:
            from itertools import combinations
            pair_models = [
                ObjectExtractionCandidate(list(pair))
                for pair in combinations(self.teachers, 2)
            ]
            self._teacher_pair_models = pair_models
        predictions: Counter[GridKey] = Counter()
        grids: dict[GridKey, Grid] = {}
        for pair_model in pair_models:
            methods = [
                ("object", pair_model.models, False),
            ]
            if pair_model._outlier_models is None:
                pair_model._outlier_models = _fit(
                    pair_model.teachers, _OUTLIER_SELECTORS, extended=True
                )
            if pair_model._palette_models is None:
                pair_model._palette_models = _fit(
                    pair_model.teachers, _PALETTE_SELECTORS, extended=True
                )
            methods.extend((
                ("outlier", pair_model._outlier_models, True),
                ("palette", pair_model._palette_models, True),
            ))
            rows = []
            for index, (family, models, outlier) in enumerate(methods):
                prediction, record = _candidate_from_models_one_vote(
                    models, test_input, outlier=outlier
                )
                if not _valid_grid(prediction) or prediction == test_input:
                    continue
                votes = int(record.get("top_votes", 0))
                applicable = max(1, int(record.get("applicable_models", 0)))
                rows.append((family, prediction, (votes / applicable, votes, -index)))
            if not rows:
                continue
            rows.sort(key=lambda row: row[2], reverse=True)
            best_score = rows[0][2]
            winners = [row for row in rows if row[2] == best_score]
            winner_keys = {_grid_key(row[1]) for row in winners}
            if len(winner_keys) != 1:
                continue
            key = next(iter(winner_keys))
            predictions[key] += 1
            grids[key] = winners[0][1]
        if not predictions:
            return None, {"top_votes": 0, "applicable_models": len(pair_models)}
        top_votes = max(predictions.values())
        winners = [key for key, votes in predictions.items() if votes == top_votes]
        minimum_support = 1 if len(pair_models) == 1 else 2
        if len(winners) != 1 or top_votes < minimum_support:
            return None, {
                "top_votes": top_votes,
                "applicable_models": len(pair_models),
            }
        return grids[winners[0]], {
            "top_votes": top_votes,
            "applicable_models": len(pair_models),
        }

'''
    lines = source.splitlines(keepends=True)
    lines.insert(candidate_method.lineno - 1, pair_method)
    result = "".join(lines)
    ast.parse(result)
    return result


def patch_adapter(parent_source: str) -> str:
    marker = "            if 格子か(局所近傍候補) and 局所近傍候補 != 第一候補:\n"
    if parent_source.count(marker) != 1:
        raise ValueError("could not locate final second-answer fallback point")
    fallback = '''            if (
                (not 格子か(第二候補) or 第二候補 == 第一候補)
                and 位置 < len(課題["test"])
            ):
                _teacher_pair_candidate, _teacher_pair_record = 物体抽出候補器.teacher_pair_consensus_candidate(
                    課題["test"][位置]["input"]
                )
                if (
                    格子か(_teacher_pair_candidate)
                    and _teacher_pair_candidate != 第一候補
                ):
                    第二候補 = _teacher_pair_candidate
                    if 観測診断:
                        候補群 = 行.get("candidate_predictions")
                        if not isinstance(候補群, list):
                            候補群 = []
                            行["candidate_predictions"] = 候補群
                        候補群.append({
                            "family": "ARC物体teacher-pair consensus",
                            "answer": _teacher_pair_candidate,
                        })
'''
    result = parent_source.replace(marker, fallback + marker, 1)
    ast.parse(result)
    return result


def make_payload(files: dict[str, bytes]) -> tuple[bytes, list[dict[str, object]]]:
    rows = [
        {"path": name, "size": len(data), "sha256": sha(data)}
        for name, data in sorted(files.items())
    ]
    manifest_bytes = json.dumps(
        {"format": "arc2-hds-kernel-bundle-v1", "files": rows},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in [(MANIFEST_NAME, manifest_bytes), *sorted(files.items())]:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue(), rows


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    parent_manifest = json.loads((PARENT / "build-manifest.json").read_text(encoding="utf-8"))
    files = read_files(PARENT / "bundle.zip")
    original_object_sha = sha(files[OBJECT_PATH])
    original_adapter_sha = sha(files[ADAPTER_PATH])
    files[OBJECT_PATH] = patch_object_module(files[OBJECT_PATH].decode("utf-8")).encode("utf-8")
    files[ADAPTER_PATH] = patch_adapter(files[ADAPTER_PATH].decode("utf-8")).encode("utf-8")
    payload, rows = make_payload(files)
    candidate_commit = parent_manifest["source_commit"] + "+v61-teacher-pair-consensus"

    builder_path = ROOT / "道具/ARC2Kaggle提出bundle.py"
    spec = importlib.util.spec_from_file_location("arc2_local_bundle_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the project bundle renderer")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    launcher = builder._render_launcher(payload, candidate_commit)
    notebook = builder._render_notebook(launcher, sha(payload))
    metadata = json.loads((PARENT / "kernel-metadata.json").read_text(encoding="utf-8"))
    metadata["title"] = "ARC2 v61 local teacher-pair consensus candidate"

    manifest = dict(parent_manifest)
    manifest.update({
        "source_commit": candidate_commit,
        "source_files": len(rows),
        "source_bytes": sum(int(row["size"]) for row in rows),
        "payload_bytes": len(payload),
        "payload_sha256": sha(payload),
        "launcher_bytes": len(launcher),
        "launcher_sha256": sha(launcher),
        "notebook_bytes": len(notebook),
        "notebook_sha256": sha(notebook),
        "files": rows,
        "local_candidate_parent_build": PARENT.name,
        "local_candidate_parent_payload_sha256": parent_manifest["payload_sha256"],
        "local_candidate_build_script_sha256": sha(Path(__file__).read_bytes()),
        "local_candidate_probe_sha256": sha(PROBE.read_bytes()),
        "local_candidate_overlay": {
            "description": "only fill a duplicate second-answer slot with an object output supported by independently fitted teacher pairs",
            "object_module_parent_sha256": original_object_sha,
            "object_module_candidate_sha256": sha(files[OBJECT_PATH]),
            "adapter_parent_sha256": original_adapter_sha,
            "adapter_candidate_sha256": sha(files[ADAPTER_PATH]),
            "training_prior_memory_sha256": next(
                row["sha256"] for row in rows if row["path"].endswith("事前記憶訓練例.json")
            ),
        },
    })

    OUTPUT.mkdir(parents=True)
    (OUTPUT / "bundle.zip").write_bytes(payload)
    (OUTPUT / "solve.py").write_bytes(launcher)
    (OUTPUT / "main.ipynb").write_bytes(notebook)
    (OUTPUT / "kernel-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output": str(OUTPUT),
        "parent": str(PARENT),
        "payload_sha256": manifest["payload_sha256"],
        "notebook_sha256": manifest["notebook_sha256"],
        "object_module_sha256": manifest["local_candidate_overlay"]["object_module_candidate_sha256"],
        "adapter_sha256": manifest["local_candidate_overlay"]["adapter_candidate_sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
