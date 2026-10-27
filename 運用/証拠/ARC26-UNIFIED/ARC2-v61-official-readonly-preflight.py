"""Read-only, exact-version preflight for the frozen ARC2 v61/v1 candidate.

No push, submission, final-selection, or credential mutation is implemented.
Output files are exclusive. A PASS remains an observation, never a submission.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from 接続 import Kaggle操作 as ops

SLUG = "arc-prize-2026-arc-agi-2"
KERNEL = "tecchannn/arc2-v61-local-teacher-pair-consensus-candidate"
RECORD = ROOT / "出力/Kaggle/arc2-v61-local-teacher-pair-consensus-candidate/v1/実行記録.json"
STAGING = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026"
OLD_PAGES = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-official-entry-pages-20261026T222951Z.json"
EXPECTED = {
    "main.ipynb": "9cb8580836257a95423560407351612cb1413c62cbd7b0ac8d62169da16120d4",
    "kernel-metadata.json": "511f18f3207790e9a4f6f119c58aeba49f09f560810028eee2a8a544798a66f9",
    "solve.py": "d47dac81dbcb9cd9a151fa7461145b5ac708291dbb52af8a4099e20efbc4a791",
    "bundle.zip": "06f7e19da4f1b6fc0059a4aef03833fd9074bc725204a3f9c5c1b33523e0fbee",
    "code_cell": "58b6219ecbdcdd33c41181c7d5c5743d9231f54759c7eb01aacc99aa474297e6",
    "submission.json": "827bccfc1cf51e2fc87d687ba51e1375899650a530ec00e7a20eb1f71eb2dd18",
    "challenge": "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value) -> None:
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n").encode("utf-8"))


def code_cells(raw: str) -> list[str]:
    notebook = json.loads(raw)
    return ["".join(cell["source"]) for cell in notebook["cells"] if cell.get("cell_type") == "code"]


def observe(destination: Path) -> dict:
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    from kagglesdk.competitions.types.competition_enums import SubmissionGroup
    from 接続.ARC2.Kaggle提出 import 入力検査, 提出検査

    if sys.flags.optimize:
        raise RuntimeError("preflight assertions must remain enabled")
    destination = destination.resolve()
    if not destination.is_relative_to((ROOT / "運用/証拠/ARC26-UNIFIED").resolve()):
        raise ValueError("preflight output must stay in the ARC2 evidence tree")
    destination.mkdir(exist_ok=False)
    record = ops.記録確認(ops.JSON読込(RECORD))
    assert record["kernel"] == KERNEL and record["version"] == 1
    assert record["code_sha256"] == EXPECTED["main.ipynb"]
    assert record["metadata_sha256"] == EXPECTED["kernel-metadata.json"]
    for name in ("main.ipynb", "kernel-metadata.json", "solve.py", "bundle.zip"):
        assert digest((STAGING / name).read_bytes()) == EXPECTED[name], name
    local_metadata, _ = ops.metadata確認(STAGING)
    assert local_metadata["id"] == KERNEL
    local_cells = code_cells((STAGING / "main.ipynb").read_text(encoding="utf-8"))
    assert len(local_cells) == 1 and digest(local_cells[0].encode()) == EXPECTED["code_cell"]
    api = ops.認証API()
    entered_response = api.competitions_list(group="entered", search="ARC Prize 2026", page_size=100)
    entered = [item for item in entered_response.competitions
               if item.ref.rstrip("/").endswith("/" + SLUG)]
    assert len(entered) == 1 and entered[0].user_has_entered is True
    deadline = ops._日時UTC(entered[0].deadline)
    assert deadline is not None
    pages = [{"name": page.name, "content": page.content} for page in api.competition_list_pages(SLUG)]
    write_new(destination / "official-pages.json", pages)
    previous = {page["name"]: page["content"] for page in ops.JSON読込(OLD_PAGES)["pages"]}
    current = {page["name"]: page["content"] for page in pages}
    critical = ("rules", "Timeline", "Code Requirements", "Evaluation")
    assert all(name in current for name in critical)
    changed_pages = [name for name in critical if previous.get(name) != current[name]]
    limits = api.competition_get_submission_limits(SLUG)
    status = ops.状態(api, record)
    assert status["status"] == "COMPLETE" and status["失敗詳細あり"] is False
    with api.build_kaggle_client() as client:
        request = ApiGetKernelRequest()
        request.user_name, request.kernel_slug = KERNEL.split("/")
        remote = client.kernels.kernels_api_client.get_kernel(request)
        metadata = remote.metadata
        assert metadata.ref == KERNEL and metadata.current_version_number == 1
        assert metadata.is_private is True and metadata.enable_internet is False
        competition_sources = list(metadata.competition_data_sources)
        allowed_sources = {SLUG, "https://www.kaggle.com/competitions/" + SLUG,
                           "https://www.kaggle.com/competitions/" + SLUG + "/"}
        assert len(competition_sources) == 1 and competition_sources[0] in allowed_sources
        assert remote.blob.kernel_type == "notebook" and remote.blob.language == "python"
        remote_cells = code_cells(remote.blob.source)
        assert remote_cells == local_cells
        remote_notebook_sha = digest(remote.blob.source.encode())
    downloaded = ops.出力取得(api, record, destination / "exact-version-output")
    files = list((destination / "exact-version-output").rglob("submission.json"))
    assert len(files) == 1 and digest(files[0].read_bytes()) == EXPECTED["submission.json"]
    challenges_path = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
    assert digest(challenges_path.read_bytes()) == EXPECTED["challenge"]
    challenges = 入力検査(json.loads(challenges_path.read_bytes()))
    predictions = json.loads(files[0].read_bytes())
    提出検査(challenges, predictions)
    assert list(challenges) == list(predictions)
    status_after = ops.状態(api, record)
    assert status_after["status"] == "COMPLETE"
    history = ops.履歴取得(api)
    gate = ops.提出可能性(api)
    selected = api.competition_submissions(SLUG, group=SubmissionGroup.SUBMISSION_GROUP_SELECTED, page_size=100)
    selected_refs = [item.ref for item in (selected or []) if item is not None]
    assert len(set(selected_refs)) == len(selected_refs) <= 2
    write_new(destination / "official-history.json", history)
    now = datetime.now(timezone.utc)
    limits_dict = {key: getattr(limits, key) for key in
                   ("num_today", "num_total", "num_allowed_now", "limited_by_total")}
    clear = (gate["許可"] and limits.num_today == 0 and limits.num_allowed_now >= 1
             and not limits.limited_by_total and now < deadline and not changed_pages)
    result = {
        "schema": "arc2-v61-exact-version-readonly-preflight-v1", "track": "ARC2",
        "observed_at_utc": now.isoformat(), "read_only": True, "submission_performed": False,
        "competition": SLUG, "entry_verified": True, "official_deadline_utc": deadline.isoformat(),
        "critical_pages_changed_since_review": changed_pages, "submission_limits": limits_dict,
        "kernel": KERNEL, "version": 1, "status": status, "status_after": status_after,
        "private": True, "internet": False, "competition_source_verified": True,
        "competition_sources": competition_sources,
        "selected_final_refs": selected_refs, "final_selection_action_performed": False,
        "remote_notebook_sha256": remote_notebook_sha, "local_remote_code_cells_identical": True,
        "artifact_sha256": EXPECTED, "submission_format_valid": True,
        "test_tasks": len(challenges), "test_grids": sum(len(task["test"]) for task in challenges.values()),
        "exact_version_download": downloaded, "gate": gate,
        "output_hash_scope": "Pre-submit public/placeholder output of this exact version; hidden rerun bytes are not observed.",
        "all_observed_submission_preconditions_pass": bool(clear),
        "source_sha256": digest(Path(__file__).read_bytes()),
        "next_action": "Root must review fresh evidence, create exclusive one-shot intent, and use recorded v61/v1 once; on ambiguity query history, never resend.",
    }
    write_new(destination / "preflight.json", result)
    return {"evidence": str((destination / "preflight.json").relative_to(ROOT)),
            "preflight_sha256": digest((destination / "preflight.json").read_bytes()),
            "all_preconditions_pass": bool(clear), "gate": gate, "limits": limits_dict}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = observe(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        # No API response, request headers, signed URLs, or secrets in diagnostics.
        print(json.dumps({"preflight": "FAILED", "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
