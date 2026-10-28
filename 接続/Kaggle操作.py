#!/usr/bin/env python3
"""対象大会のNotebookを送信・観測し、明示された版だけを提出する。"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import sys
from tempfile import TemporaryFile
from urllib.parse import urlsplit
from zipfile import ZipFile


大会 = "arc-prize-2026-arc-agi-2"
ルート = Path(__file__).resolve().parents[1]
記録版 = "arc2-kaggle-run-v1"


class 操作エラー(Exception):
    """秘密を含まない、利用者に表示できる診断。"""


def JSON読込(パス: Path) -> dict:
    try:
        内容 = json.loads(パス.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise 操作エラー("JSONファイルを読めません。パスとJSON形式を確認してください。") from None
    if not isinstance(内容, dict):
        raise 操作エラー("JSONの最上位はobjectが必要です。")
    return 内容


def Notebook名確認(名前: object) -> str:
    if not isinstance(名前, str) or not re.fullmatch(
        r"[a-zA-Z0-9_-]+/[a-zA-Z0-9][a-zA-Z0-9_-]*", 名前
    ):
        raise 操作エラー("Notebookのidは版番号を含まない owner/slug が必要です。")
    return 名前


def 送信応答Notebook確認(応答, 期待名: str) -> str:
    """実APIの /code/owner/slug 参照と正規owner/slugを検証する。"""
    参照 = 応答.ref
    if isinstance(参照, str) and 参照.startswith("/code/"):
        # Kaggle 2.2.4の実送信応答はサイト相対path。owner/slugへ正規化して照合する。
        参照 = 参照.removeprefix("/code/").removesuffix("/")
        Notebook名確認(参照)
    if not 参照:
        try:
            URL = urlsplit(応答.url)
        except ValueError:
            raise 操作エラー("送信応答のNotebook URLを検証できません。再送せずKaggle側を確認してください。") from None
        if URL.scheme != "https" or URL.netloc not in ("www.kaggle.com", "kaggle.com"):
            raise 操作エラー("送信応答に検証可能なKaggleのNotebook参照がありません。再送せずKaggle側を確認してください。")
        パス = URL.path.strip("/").split("/")
        if len(パス) == 3 and パス[0] == "code":
            パス = パス[1:]
        参照 = "/".join(パス)
        Notebook名確認(参照)
    if 参照 != 期待名:
        raise 操作エラー("送信応答のNotebookとmetadataのidが不一致です。自動再送せずKaggle側を確認してください。")
    return 参照


def metadata確認(フォルダ: Path) -> tuple[dict, Path]:
    フォルダ = フォルダ.resolve()
    内容 = JSON読込(フォルダ / "kernel-metadata.json")
    Notebook名確認(内容.get("id"))
    if 内容.get("id_no") is not None:
        raise 操作エラー("id_noは使用できません。送信対象はidで指定してください。")
    if 内容.get("is_private") is not True:
        raise 操作エラー("metadataのis_privateはJSONのtrueが必要です。")
    if 内容.get("enable_internet") is not False:
        raise 操作エラー("metadataのenable_internetはJSONのfalseが必要です。")
    ソース = 内容.get("competition_sources")
    if not isinstance(ソース, list) or 大会 not in ソース:
        raise 操作エラー("metadataのcompetition_sourcesに対象大会が必要です。")
    if not all(isinstance(項目, str) for 項目 in ソース):
        raise 操作エラー("competition_sourcesは文字列の配列が必要です。")
    コード名 = 内容.get("code_file")
    if not isinstance(コード名, str) or not コード名:
        raise 操作エラー("metadataのcode_fileが必要です。")
    コード = (フォルダ / コード名).resolve()
    if not コード.is_relative_to(フォルダ) or not コード.is_file():
        raise 操作エラー("code_fileは送信フォルダ内の実在するファイルが必要です。")
    種類 = {".py": "script", ".ipynb": "notebook"}.get(コード.suffix)
    if not 種類 or 内容.get("kernel_type") != 種類 or 内容.get("language") != "python":
        raise 操作エラー("Pythonの.py/script または .ipynb/notebook を指定してください。")
    return 内容, コード


def 記録確認(記録: dict) -> dict:
    if 記録.get("schema") != 記録版 or 記録.get("competition") != 大会:
        raise 操作エラー("実行記録のschemaまたは大会が一致しません。")
    Notebook名確認(記録.get("kernel"))
    if type(記録.get("version")) is not int or 記録["version"] < 1:
        raise 操作エラー("実行記録に正の整数の版番号が必要です。")
    for キー in ("code_sha256", "metadata_sha256"):
        if not isinstance(記録.get(キー), str) or not re.fullmatch(r"[0-9a-f]{64}", 記録[キー]):
            raise 操作エラー("実行記録にSHA256が必要です。")
    return 記録


def JSON保存(パス: Path, 内容: dict) -> None:
    パス.parent.mkdir(parents=True, exist_ok=True)
    # 既存の実行・提出証跡を上書きしない。
    with パス.open("x", encoding="utf-8") as 出力:
        json.dump(内容, 出力, ensure_ascii=False, indent=2)
        出力.write("\n")


def 認証API():
    # kaggleのimport自体が認証を試みる。SDKの生ログや設定全体は表示しない。
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle import api

            if not getattr(api, "_authenticated", False):
                api.authenticate()
    except (Exception, SystemExit):
        raise 操作エラー(
            "Kaggle認証に失敗しました。Kaggle CLIのログインまたは利用者ホームの認証設定を確認してください。"
        ) from None
    return api


def 接続確認(api) -> dict:
    # 公開file一覧だけでは認証の証拠にならないため、本人の提出履歴も読む。
    api.competition_list_files(大会)
    履歴 = api.competition_submissions(大会, page_size=20) or []
    return {
        "状態": "接続成功",
        "competition": 大会,
        "username": api.get_config_value("username"),
        "最近の提出数": len(履歴),
        "注記": "大会参加条件・提出資格は提出時にもKaggleが判定します。",
    }


def 送信(api, フォルダ: Path, timeout: int = 600) -> dict:
    if type(timeout) is not int or timeout <= 0:
        raise 操作エラー("timeoutは正の秒数が必要です。")
    フォルダ = フォルダ.resolve()
    metadata, コード = metadata確認(フォルダ)
    コードSHA = hashlib.sha256(コード.read_bytes()).hexdigest()
    metadataSHA = hashlib.sha256((フォルダ / "kernel-metadata.json").read_bytes()).hexdigest()
    応答 = api.kernels_push(str(フォルダ), timeout=str(timeout))
    if 応答.error:
        raise 操作エラー("KaggleがNotebook送信エラーを返しました。KaggleのNotebook画面を確認してください。")
    不正 = [
        名前
        for 名前 in (
            "invalid_tags", "invalid_dataset_sources", "invalid_competition_sources",
            "invalid_kernel_sources", "invalid_model_sources",
        )
        if getattr(応答, 名前)
    ]
    if 不正:
        raise 操作エラー("Kaggleがmetadataの参照を拒否しました: " + ", ".join(不正))
    参照 = 送信応答Notebook確認(応答, metadata["id"])
    if type(応答.version_number) is not int or 応答.version_number < 1:
        raise 操作エラー("送信応答に有効な版番号がありません。自動再送せずKaggle側を確認してください。")
    記録 = {
        "schema": 記録版,
        "competition": 大会,
        "kernel": 参照,
        "version": 応答.version_number,
        "code_file": コード.relative_to(フォルダ).as_posix(),
        "code_sha256": コードSHA,
        "metadata_sha256": metadataSHA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": timeout,
    }
    パス = ルート / "出力/Kaggle" / 参照.split("/")[1] / f"v{応答.version_number}" / "実行記録.json"
    try:
        JSON保存(パス, 記録)
    except OSError:
        raise 操作エラー(
            f"Notebook送信は受理されましたが実行記録を保存できません。対象={参照} 版={応答.version_number}。"
            "再送前に保存先を確認してください。"
        ) from None
    return {"状態": "送信受理・実行結果未確認", "実行記録": str(パス), **記録}


def 現行版確認(remote, 記録: dict) -> None:
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest

    要求 = ApiGetKernelRequest()
    要求.user_name, 要求.kernel_slug = 記録["kernel"].split("/")
    metadata = remote.get_kernel(要求).metadata
    if not metadata or metadata.ref != 記録["kernel"]:
        raise 操作エラー("Kaggle側のNotebook参照が実行記録と一致しません。")
    if metadata.current_version_number != 記録["version"]:
        raise 操作エラー(
            "記録版がKaggle側の現行版と一致しません。状態確認・提出には現行版の実行記録を使ってください。"
            "過去版の出力取得は可能です。"
        )


def 状態(api, 記録: dict) -> dict:
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionStatusRequest

    記録確認(記録)
    要求 = ApiGetKernelSessionStatusRequest()
    要求.user_name, 要求.kernel_slug = 記録["kernel"].split("/")
    # 実APIでstatusのversion_label指定は404。現行版の前後一致で観測対象を限定する。
    with api.build_kaggle_client() as client:
        remote = client.kernels.kernels_api_client
        現行版確認(remote, 記録)
        応答 = remote.get_kernel_session_status(要求)
        現行版確認(remote, 記録)
    return {
        "kernel": 記録["kernel"], "version": 記録["version"],
        "status": 応答.status.name,
        "失敗詳細あり": bool(応答.failure_message),
        "観測方法": "現行版番号を前後確認",
    }


def 出力一覧(api, 記録: dict) -> tuple[list, str]:
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest

    記録確認(記録)
    ファイル = []
    ログ = ""
    トークン = ""
    既出 = set()
    with api.build_kaggle_client() as client:
        remote = client.kernels.kernels_api_client
        現行版確認(remote, 記録)
        while True:
            要求 = ApiListKernelSessionOutputRequest()
            要求.user_name, 要求.kernel_slug = 記録["kernel"].split("/")
            要求.page_size = 100
            要求.page_token = トークン
            応答 = remote.list_kernel_session_output(要求)
            ファイル.extend(応答.files or [])
            if not ログ:
                ログ = 応答.log
            トークン = 応答.next_page_token
            if not トークン:
                break
            if トークン in 既出:
                raise 操作エラー("出力一覧のページ指定が循環しています。取得を中断しました。")
            既出.add(トークン)
        現行版確認(remote, 記録)
    return ファイル, ログ


def 出力先確認(保存先: Path, 名前: str) -> Path:
    # APIが返す相対名で保存先外・Windows代替ストリームへ書き込まない。
    相対 = PurePosixPath(名前)
    if not 名前 or "\x00" in 名前 or "\\" in 名前 or ":" in 名前 or 相対.is_absolute() or any(
        部分 in ("", ".", "..") or 部分.rstrip(" .") != 部分 or PureWindowsPath(部分).is_reserved()
        for 部分 in 名前.split("/")
    ):
        raise 操作エラー("出力に安全でない相対ファイル名があります。")
    パス = 保存先.joinpath(*相対.parts)
    if not パス.resolve().is_relative_to(保存先.resolve()) or パス.is_symlink():
        raise 操作エラー("出力先が保存フォルダ外またはsymlinkです。")
    if パス.exists():
        raise 操作エラー("出力先に既存ファイルがあります。空の保存フォルダを指定してください。")
    return パス


def 出力取得(api, 記録: dict, 保存先: Path) -> dict:
    from kagglesdk.kernels.types.kernels_api_service import ApiDownloadKernelOutputRequest

    記録確認(記録)
    保存先 = 保存先.resolve()
    要求 = ApiDownloadKernelOutputRequest()
    要求.owner_slug, 要求.kernel_slug = 記録["kernel"].split("/")
    # KaggleHubと同じdownload APIの整数版指定は、実在版成功・不存在版404を実測済み。
    要求.version_number = 記録["version"]
    with TemporaryFile() as 一時, api.build_kaggle_client() as client:
        with client.kernels.kernels_api_client.download_kernel_output(要求) as 応答:
            応答.raise_for_status()
            for 塊 in 応答.iter_content(chunk_size=1024 * 1024):
                一時.write(塊)
        一時.seek(0)
        with ZipFile(一時) as アーカイブ:
            予定 = []
            for 項目 in アーカイブ.infolist():
                種類 = stat.S_IFMT(項目.external_attr >> 16)
                if 種類 not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise 操作エラー("出力ZIPにsymlinkまたは特殊ファイルが含まれています。")
                パス = 出力先確認(保存先, 項目.filename.rstrip("/") if 項目.is_dir() else 項目.filename)
                if not 項目.is_dir():
                    予定.append((パス, 項目))
            if len({パス for パス, _ in 予定}) != len(予定):
                raise 操作エラー("出力ZIPのファイル名が重複しています。")
            for パス, 項目 in 予定:
                パス.parent.mkdir(parents=True, exist_ok=True)
                # ZIP名は全件事前検査済み。extractallや既存ファイルの上書きは使わない。
                with アーカイブ.open(項目) as 入力, パス.open("xb") as 出力:
                    shutil.copyfileobj(入力, 出力)
    return {
        "kernel": 記録["kernel"], "version": 記録["version"],
        "取得ファイル": [str(パス) for パス, _ in 予定],
    }


def _日時UTC(値):
    if isinstance(値, datetime):
        return 値.replace(tzinfo=timezone.utc) if 値.tzinfo is None else 値.astimezone(timezone.utc)
    if isinstance(値, str):
        try:
            日時 = datetime.fromisoformat(値.replace("Z", "+00:00"))
        except ValueError:
            return None
        return 日時.replace(tzinfo=timezone.utc) if 日時.tzinfo is None else 日時.astimezone(timezone.utc)
    return None


def _数値スコアか(値) -> bool:
    if 値 is None or isinstance(値, bool):
        return False
    try:
        return Decimal(str(値).strip()).is_finite()
    except (InvalidOperation, ValueError):
        return False


def _明示的な実行時間超過(提出記録) -> bool:
    """Kaggleが実行時間超過を明記した終端失敗だけを再試行可能とする。"""
    詳細 = getattr(提出記録, "error_description", None)
    if not isinstance(詳細, str):
        return False
    小文字 = 詳細.casefold()
    return "notebook timeout" in 小文字 or "exceeded the allowed runtime" in 小文字


def 提出可能性(api, now: datetime | None = None) -> dict:
    """公式残枠と直近提出の状態に基づき、送信前に安全側で判定する。"""
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    履歴 = [x for x in (api.competition_submissions(大会, page_size=100) or []) if x is not None]
    日付付き = [(x, _日時UTC(getattr(x, "date", None))) for x in 履歴]
    日付不明 = [x for x, 日時 in 日付付き if 日時 is None]
    当日提出 = [x for x, 日時 in 日付付き if 日時 is not None and 日時.date() == now.date()]
    最新 = max(日付付き, key=lambda row: row[1] or datetime.min.replace(tzinfo=timezone.utc))[0] if 日付付き else None
    実行時間超過再試行 = (
        最新 is not None
        and getattr(getattr(最新, "status", None), "name", None) == "COMPLETE"
        and not _数値スコアか(getattr(最新, "public_score", None))
        and _明示的な実行時間超過(最新)
    )
    結果 = {
        "許可": False,
        "competition": 大会,
        "utc_day": now.date().isoformat(),
        "latest_ref": getattr(最新, "ref", None),
        "latest_status": getattr(getattr(最新, "status", None), "name", None),
        "latest_public_score": getattr(最新, "public_score", None),
        "today_submission_refs": [getattr(x, "ref", None) for x in 当日提出],
        "scoreless_timeout_retry": 実行時間超過再試行,
    }
    状態名 = getattr(getattr(最新, "status", None), "name", None) if 最新 is not None else None
    詳細 = getattr(最新, "error_description", None) if 最新 is not None else None
    数値あり = _数値スコアか(getattr(最新, "public_score", None)) if 最新 is not None else False
    if 最新 is None:
        状態分類 = "NOT_SUBMITTED"
    elif 状態名 in {"PENDING", "SUBMITTED", "RUNNING"}:
        状態分類 = "IN_PROGRESS"
    elif 状態名 in {"ERROR", "FAILED"} or (状態名 == "COMPLETE" and bool(詳細) and not 数値あり):
        状態分類 = "TERMINAL_ERROR_NOT_SCORED"
    elif 状態名 == "COMPLETE" and 数値あり and not 詳細:
        状態分類 = "SCORED_ACCEPTED"
    else:
        状態分類 = "UNVERIFIED"
    結果["latest_score_state"] = 状態分類
    try:
        制限 = api.competition_get_submission_limits(大会)
        残枠 = getattr(制限, "num_allowed_now", None)
        if type(残枠) is not int or 残枠 < 0:
            raise ValueError("残枠が不正です")
        結果["num_allowed_now"] = 残枠
    except Exception:
        結果["理由"] = "Kaggleの現在の提出残枠を確認できません。"
        return 結果
    if 日付不明:
        結果["理由"] = "提出日時を解釈できない履歴があり、日次枠を安全に確認できません。"
    elif 残枠 == 0:
        結果["理由"] = "Kaggleの現在の提出残枠は0です。"
    elif 状態分類 == "IN_PROGRESS":
        結果["理由"] = "直近提出の公式採点が完了していません。先に同一IDの履歴を追跡してください。"
    elif 状態分類 == "UNVERIFIED":
        結果["理由"] = "直近提出の採点状態を確認できません。詳細を照会してください。"
    elif any(getattr(getattr(x, "status", None), "name", None) == "COMPLETE" and _数値スコアか(getattr(x, "public_score", None)) and not getattr(x, "error_description", None) for x in 当日提出):
        結果["理由"] = "当日は既に数値採点済みの提出があります。"
    else:
        結果["許可"] = True
        結果["理由"] = "公式残枠と直近提出の状態を確認しました。提出版と失敗原因の対処を確認してください。"
    return 結果


def 提出(api, 記録: dict, メッセージ: str) -> dict:
    記録確認(記録)
    if not メッセージ.strip():
        raise 操作エラー("提出messageは空にできません。")
    ゲート = 提出可能性(api)
    if not ゲート["許可"]:
        raise 操作エラー(ゲート["理由"])
    if 状態(api, 記録)["status"] != "COMPLETE":
        raise 操作エラー("指定版のNotebookがCOMPLETEではないため提出しません。")
    一覧, _ = 出力一覧(api, 記録)
    if not any(項目.file_name == "submission.json" for 項目 in 一覧):
        raise 操作エラー("指定版の出力にsubmission.jsonがないため提出しません。")
    応答 = api.competition_submit_code(
        file_name="submission.json", message=メッセージ, competition=大会,
        kernel=記録["kernel"], kernel_version=記録["version"], quiet=True,
    )
    if type(応答.ref) is not int or 応答.ref < 1:
        raise 操作エラー("提出受付番号を確認できません。再提出前にKaggleの提出履歴を確認してください。")
    return {
        "状態": "提出受理・採点結果未確認", "competition": 大会,
        "kernel": 記録["kernel"], "version": 記録["version"],
        "submission_ref": 応答.ref, "created_at": datetime.now(timezone.utc).isoformat(),
        "提出ゲート": ゲート,
    }


def 履歴取得(api) -> dict:
    一覧 = api.competition_submissions(大会, page_size=20) or []
    return {"competition": 大会, "最新20件": [
        {
            "ref": 項目.ref, "date": 項目.date.isoformat() if 項目.date else None,
            "status": 項目.status.name, "public_score": 項目.public_score,
            "失敗詳細あり": bool(項目.error_description),
        }
        for 項目 in 一覧 if 項目 is not None
    ]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="操作", required=True)
    sub.add_parser("接続確認", help="認証・大会アクセスを読み取りだけで確認")
    push = sub.add_parser("送信", help="NotebookをKaggleへ送信して実行を開始（提出は別操作）")
    push.add_argument("--folder", type=Path, required=True)
    push.add_argument("--timeout", type=int, default=600, help="Kaggle実行上限秒数。既定600秒")
    for 名前 in ("状態", "出力", "提出"):
        command = sub.add_parser(名前)
        command.add_argument("--record", type=Path, required=True)
        if 名前 == "出力":
            command.add_argument("--path", type=Path, required=True)
        if 名前 == "提出":
            command.add_argument("--message", required=True)
    sub.add_parser("提出可否確認", help="Kaggleの残枠と直近提出の採点状態を読み取り専用で確認")
    sub.add_parser("履歴", help="対象大会の最新20件の提出履歴")
    args = parser.parse_args(argv)
    try:
        # ローカル入力の不備では認証・通信を開始しない。
        記録 = 記録確認(JSON読込(args.record)) if hasattr(args, "record") else None
        if args.操作 == "送信":
            metadata確認(args.folder)
            if args.timeout <= 0:
                raise 操作エラー("timeoutは正の秒数が必要です。")
        api = 認証API()
        # SDKの警告やURL・応答全文はstdout/stderrへ漏らさない。
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            if args.操作 == "接続確認":
                結果 = 接続確認(api)
            elif args.操作 == "送信":
                結果 = 送信(api, args.folder, args.timeout)
            elif args.操作 == "状態":
                結果 = 状態(api, 記録)
            elif args.操作 == "出力":
                結果 = 出力取得(api, 記録, args.path)
            elif args.操作 == "提出":
                結果 = 提出(api, 記録, args.message)
                保存先 = args.record.parent / f"提出記録-{結果['submission_ref']}.json"
                try:
                    JSON保存(保存先, 結果)
                except OSError:
                    raise 操作エラー(
                        f"提出は受理されましたが記録を保存できません。受付番号={結果['submission_ref']}。"
                        "再提出せず提出履歴を確認してください。"
                    ) from None
                結果["提出記録"] = str(保存先)
            elif args.操作 == "提出可否確認":
                結果 = 提出可能性(api)
            else:
                結果 = 履歴取得(api)
        print(json.dumps(結果, ensure_ascii=False, indent=2))
        if args.操作 == "提出可否確認" and not 結果["許可"]:
            return 2
        if args.操作 == "状態" and 結果["status"] in (
            "ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED",
        ):
            return 1
        return 0
    except 操作エラー as 例外:
        print(f"Kaggle操作失敗: {例外}", file=sys.stderr)
    except Exception as 例外:
        # SDK例外の本文・request header・署名URLを無差別に表示しない。
        HTTP状態 = getattr(getattr(例外, "response", None), "status_code", None)
        原因 = f"HTTP {HTTP状態}" if isinstance(HTTP状態, int) else type(例外).__name__
        print(
            f"Kaggle操作失敗: {原因}。認証・大会参加・ネットワーク・保存先を確認してください。"
            "送信／提出の途中なら、再実行前にKaggle側の履歴を確認してください。",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
