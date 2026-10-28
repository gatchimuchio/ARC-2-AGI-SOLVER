"""固定v61実行器の診断コピーを作り、候補記録を追加する。正解は読まない。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v61-global-deadline-isolated"
EXPECTED = {
    "Kaggle提出.py": "dc90314d9fa18626c67b02177ddac9fd9ec2d1ef89bc3b5f76ae013861a15213",
    "deadline_control.py": "fd20d8b0609882b83217a7356a6175cd549c63a4c13ba7b9b852bc27a0a39f27",
    "outer_watchdog.py": "a26b1711cc77ad9797dcded9ad63427ea656ca27193fe7c5c2f24a1585473347",
    "solve.py": "740ebb543f6fbed996b12fff96cbb3b2892c964ece66d692e29445450ecac7af",
}


def _replace_once(source: str, anchor: str, replacement: str) -> str:
    if source.count(anchor) != 1:
        raise ValueError("診断挿入箇所が一意ではありません")
    return source.replace(anchor, replacement, 1)


def 作成(destination: Path) -> dict:
    if destination.exists():
        raise FileExistsError("既存の診断ディレクトリは上書きしません")
    data = {name: (SOURCE / name).read_bytes() for name in EXPECTED}
    for name, content in data.items():
        if hashlib.sha256(content).hexdigest() != EXPECTED[name]:
            raise ValueError(f"固定済みsourceのhash不一致: {name}")
    wrapper = data["Kaggle提出.py"].decode("utf-8")
    before = '            第二候補 = (候補対[1] if 候補対 else _一意な別候補を選ぶ(\n'
    wrapper = _replace_once(wrapper, before,
        '            診断選択前 = deepcopy(行.get("candidate_predictions", []))\n' + before)
    after = '            if 観測診断 and 位置 < len(課題["test"]):\n'
    wrapper = _replace_once(wrapper, after,
        '            公開行群[-1]["diagnostic_candidates"] = {\n'
        '                "preselection": 診断選択前,\n'
        '                "postselection": deepcopy(行.get("candidate_predictions", [])),\n'
        '                "candidate_attempts": deepcopy(行.get("candidate_attempts")),\n'
        '                "simple_candidate": deepcopy(行.get("simple_transform_candidate")),\n'
        '            }\n' + after)
    controller = data["deadline_control.py"].decode("utf-8")
    anchor = '    diagnostics = result.get("aggregate_diagnostics", {}) if aggregate_diagnostics and isinstance(result, dict) else {}\n'
    controller = _replace_once(controller, anchor,
        '    if aggregate_diagnostics:\n'
        '        directory = Path(os.environ["ARC2_DIAGNOSTIC_DIR"])\n'
        '        if not isinstance(task_id, str) or not task_id.isalnum():\n'
        '            raise ValueError("unsafe diagnostic task identifier")\n'
        '        with (directory / (task_id + ".json")).open("x", encoding="utf-8") as f:\n'
        '            json.dump(result, f, ensure_ascii=False, sort_keys=True)\n' + anchor)
    compile(wrapper, "Kaggle提出.py", "exec")
    compile(controller, "deadline_control.py", "exec")
    data["Kaggle提出.py"] = wrapper.encode("utf-8")
    data["deadline_control.py"] = controller.encode("utf-8")
    destination.mkdir(parents=True)
    for name, content in data.items():
        with (destination / name).open("xb") as f:
            f.write(content)
    manifest = {"source_sha256": EXPECTED,
                "diagnostic_sha256": {n: hashlib.sha256(v).hexdigest() for n, v in data.items()},
                "scope": "Captured candidates from the executed and instrumented paths only; no answers are read."}
    with (destination / "diagnostic-manifest.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(作成(args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
