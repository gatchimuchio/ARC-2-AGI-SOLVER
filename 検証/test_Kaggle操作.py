"""外部送信せず、Kaggleの版固定と失敗時の提出抑止を確認する。"""

from contextlib import nullcontext
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile, ZipInfo

from kagglesdk.kernels.types.kernels_api_service import (
    ApiGetKernelSessionStatusResponse,
    ApiGetKernelResponse,
    ApiKernelMetadata,
    ApiKernelSessionOutputFile,
    ApiListKernelSessionOutputResponse,
    ApiSaveKernelResponse,
)
from kagglesdk.kernels.types.kernels_enums import KernelWorkerStatus
import pytest

from 接続 import Kaggle操作 as 操作


@pytest.fixture
def 記録():
    return {
        "schema": 操作.記録版,
        "competition": 操作.大会,
        "kernel": "owner/test-notebook",
        "version": 7,
        "code_sha256": "a" * 64,
        "metadata_sha256": "b" * 64,
    }


@pytest.fixture
def 送信フォルダ(tmp_path):
    フォルダ = tmp_path / "notebook"
    フォルダ.mkdir()
    (フォルダ / "main.py").write_text("print('smoke')\n", encoding="utf-8")
    内容 = {
        "id": "owner/test-notebook", "title": "Test Notebook",
        "code_file": "main.py", "language": "python", "kernel_type": "script",
        "is_private": True, "enable_internet": False,
        "competition_sources": [操作.大会],
    }
    (フォルダ / "kernel-metadata.json").write_text(json.dumps(内容), encoding="utf-8")
    return フォルダ


def API作成(status=KernelWorkerStatus.COMPLETE, ファイル名=("submission.json",)):
    応答 = ApiGetKernelSessionStatusResponse()
    応答.status = status
    出力応答 = ApiListKernelSessionOutputResponse()
    一覧 = []
    for 名前 in ファイル名:
        ファイル = ApiKernelSessionOutputFile()
        ファイル.file_name = 名前
        ファイル.url = "https://example.invalid/output"
        一覧.append(ファイル)
    出力応答.files = 一覧
    client = SimpleNamespace(kernels=SimpleNamespace(kernels_api_client=Mock()))
    remote = client.kernels.kernels_api_client
    remote.get_kernel_session_status.return_value = 応答
    remote.list_kernel_session_output.return_value = 出力応答
    Notebook = ApiGetKernelResponse()
    Notebook.metadata = ApiKernelMetadata()
    Notebook.metadata.ref = "owner/test-notebook"
    Notebook.metadata.current_version_number = 7
    remote.get_kernel.return_value = Notebook
    api = Mock()
    api.build_kaggle_client.side_effect = lambda: nullcontext(client)
    api.competition_submissions.return_value = []
    api.competition_get_submission_limits.return_value = SimpleNamespace(num_allowed_now=1)
    api.competition_submit_code.return_value = SimpleNamespace(ref=123)
    return api, remote


def test_送信は受付版とコードhashを保存し提出しない(送信フォルダ, tmp_path, monkeypatch):
    monkeypatch.setattr(操作, "ルート", tmp_path)
    api, _ = API作成()
    応答 = ApiSaveKernelResponse()
    応答.ref = "owner/test-notebook"
    応答.version_number = 7
    api.kernels_push.return_value = 応答
    結果 = 操作.送信(api, 送信フォルダ, 600)
    api.kernels_push.assert_called_once_with(str(送信フォルダ.resolve()), timeout="600")
    保存 = 操作.記録確認(操作.JSON読込(Path(結果["実行記録"])))
    assert 保存["version"] == 7
    assert 保存["code_sha256"] == hashlib.sha256((送信フォルダ / "main.py").read_bytes()).hexdigest()
    api.competition_submit_code.assert_not_called()


def test_同版の既存実行記録を保護して今回分を別名保存(送信フォルダ, tmp_path, monkeypatch):
    monkeypatch.setattr(操作, "ルート", tmp_path)
    既存パス = tmp_path / "出力" / "Kaggle" / "test-notebook" / "v7" / "実行記録.json"
    既存パス.parent.mkdir(parents=True)
    既存パス.write_text('{"previous":"preserve"}\n', encoding="utf-8")
    api, _ = API作成()
    応答 = ApiSaveKernelResponse()
    応答.ref = "owner/test-notebook"
    応答.version_number = 7
    api.kernels_push.return_value = 応答

    結果 = 操作.送信(api, 送信フォルダ)

    今回パス = Path(結果["実行記録"])
    assert 今回パス != 既存パス
    assert 今回パス.name.startswith("実行記録-")
    assert json.loads(既存パス.read_text(encoding="utf-8")) == {"previous": "preserve"}
    保存 = 操作.記録確認(操作.JSON読込(今回パス))
    assert 保存["version"] == 7
    assert 保存["code_sha256"] == hashlib.sha256((送信フォルダ / "main.py").read_bytes()).hexdigest()
    api.competition_submit_code.assert_not_called()


def test_実APIのサイト相対refを正規化して記録する(送信フォルダ, tmp_path, monkeypatch):
    monkeypatch.setattr(操作, "ルート", tmp_path)
    api, _ = API作成()
    応答 = ApiSaveKernelResponse()
    応答.ref = "/code/owner/test-notebook"
    応答.url = "https://www.kaggle.com/code/owner/test-notebook"
    応答.version_number = 2
    api.kernels_push.return_value = 応答
    結果 = 操作.送信(api, 送信フォルダ)
    assert 結果["kernel"] == "owner/test-notebook"
    assert 結果["version"] == 2
    assert 操作.JSON読込(Path(結果["実行記録"]))["kernel"] == "owner/test-notebook"


@pytest.mark.parametrize("参照", [
    "/code/other/wrong", "/code/owner/test-notebook/3", "/code/../test-notebook",
    "/code//owner/test-notebook",
])
def test_サイト相対refも他Notebookや不正pathを拒否(参照):
    応答 = ApiSaveKernelResponse()
    応答.ref = 参照
    # URLだけ正しくても、不一致のrefを握りつぶして採用しない。
    応答.url = "https://www.kaggle.com/code/owner/test-notebook"
    with pytest.raises(操作.操作エラー):
        操作.送信応答Notebook確認(応答, "owner/test-notebook")


@pytest.mark.parametrize("URL", [
    "https://www.kaggle.com/code/owner/test-notebook",
    "https://www.kaggle.com/owner/test-notebook",
])
def test_ref欠落時はAPIのKaggle_URLとの一致を確認(送信フォルダ, tmp_path, monkeypatch, URL):
    monkeypatch.setattr(操作, "ルート", tmp_path)
    api, _ = API作成()
    応答 = ApiSaveKernelResponse()
    応答.url = URL
    応答.version_number = 7
    api.kernels_push.return_value = 応答
    結果 = 操作.送信(api, 送信フォルダ)
    assert 結果["kernel"] == "owner/test-notebook"
    assert 結果["version"] == 7


@pytest.mark.parametrize("URL", [
    "", "https://evil.invalid/code/owner/test-notebook",
    "https://www.kaggle.com@evil.invalid/code/owner/test-notebook",
    "https://www.kaggle.com/code/other/wrong",
    "https://www.kaggle.com/code/owner/test-notebook/99",
])
def test_ref欠落かつURL不正ではidから推測しない(URL):
    応答 = ApiSaveKernelResponse()
    応答.url = URL
    with pytest.raises(操作.操作エラー):
        操作.送信応答Notebook確認(応答, "owner/test-notebook")


@pytest.mark.parametrize("変更", [
    {"is_private": False}, {"is_private": "true"}, {"enable_internet": True},
    {"competition_sources": []}, {"code_file": "../outside.py"},
    {"code_file": "missing.py"}, {"id": "owner/test-notebook/7"},
    {"kernel_type": "notebook"}, {"id_no": 999},
])
def test_不正metadataは通信前に拒否(送信フォルダ, 変更):
    パス = 送信フォルダ / "kernel-metadata.json"
    内容 = 操作.JSON読込(パス)
    内容.update(変更)
    パス.write_text(json.dumps(内容), encoding="utf-8")
    (送信フォルダ.parent / "outside.py").write_text("", encoding="utf-8")
    api, _ = API作成()
    with pytest.raises(操作.操作エラー):
        操作.送信(api, 送信フォルダ)
    api.kernels_push.assert_not_called()


@pytest.mark.parametrize("属性,値", [
    ("error", "denied"), ("invalid_competition_sources", [操作.大会]),
    ("invalid_dataset_sources", ["owner/data"]), ("invalid_kernel_sources", ["owner/kernel"]),
    ("invalid_model_sources", ["owner/model"]), ("version_number", 0),
    ("ref", "other/wrong"),
])
def test_送信失敗や版不明では実行記録を作らない(送信フォルダ, tmp_path, monkeypatch, 属性, 値):
    monkeypatch.setattr(操作, "ルート", tmp_path)
    api, _ = API作成()
    応答 = ApiSaveKernelResponse()
    応答.ref = "owner/test-notebook"
    応答.version_number = 7
    setattr(応答, 属性, 値)
    api.kernels_push.return_value = 応答
    with pytest.raises(操作.操作エラー):
        操作.送信(api, 送信フォルダ)
    assert not (tmp_path / "出力").exists()


def test_指定版の状態と全出力ページを確認して同じ版を提出(記録):
    api, remote = API作成()
    二頁目 = remote.list_kernel_session_output.return_value
    一頁目 = ApiListKernelSessionOutputResponse()
    一頁目.next_page_token = "second-page"
    remote.list_kernel_session_output.side_effect = [一頁目, 二頁目]
    結果 = 操作.提出(api, 記録, "checked run")
    要求 = remote.get_kernel_session_status.call_args.args[0]
    assert (要求.user_name, 要求.kernel_slug, 要求.version_label) == ("owner", "test-notebook", "")
    assert [呼出.args[0].version_label for 呼出 in remote.list_kernel_session_output.call_args_list] == ["", ""]
    assert [呼出.args[0].page_token for 呼出 in remote.list_kernel_session_output.call_args_list] == ["", "second-page"]
    assert remote.get_kernel.call_count == 4  # 状態・全ページ出力のそれぞれ前後に現行版照合。
    api.competition_submit_code.assert_called_once_with(
        file_name="submission.json", message="checked run", competition=操作.大会,
        kernel="owner/test-notebook", kernel_version=7, quiet=True,
    )
    assert 結果["submission_ref"] == 123


@pytest.mark.parametrize("status", [KernelWorkerStatus.RUNNING, KernelWorkerStatus.ERROR])
def test_未完了または失敗した版は提出しない(記録, status):
    api, remote = API作成(status=status)
    with pytest.raises(操作.操作エラー, match="COMPLETE"):
        操作.提出(api, 記録, "test")
    remote.list_kernel_session_output.assert_not_called()
    api.competition_submit_code.assert_not_called()


def test_動作確認や別階層の出力では提出できない(記録):
    api, _ = API作成(ファイル名=("environment.json", "nested/submission.json"))
    with pytest.raises(操作.操作エラー, match="submission.json"):
        操作.提出(api, 記録, "test")
    api.competition_submit_code.assert_not_called()


@pytest.mark.parametrize("変更", [
    {"competition": "another-competition"}, {"version": 0}, {"version": True},
    {"version": "7"}, {"kernel": "owner/kernel/99"}, {"code_sha256": "invalid"},
])
def test_異なる大会や不正な実行記録は通信前に拒否(記録, 変更):
    記録.update(変更)
    api, _ = API作成()
    with pytest.raises(操作.操作エラー):
        操作.提出(api, 記録, "test")
    api.build_kaggle_client.assert_not_called()
    api.competition_submit_code.assert_not_called()


@pytest.mark.parametrize("名前", ["../secret", "/absolute", "a/../../secret", "C:/secret", "x:stream", "a\\b"])
def test_出力pathが保存先を逸脱しない(tmp_path, 名前):
    with pytest.raises(操作.操作エラー):
        操作.出力先確認(tmp_path, 名前)
    既存 = tmp_path / "existing"
    既存.touch()
    with pytest.raises(操作.操作エラー, match="既存"):
        操作.出力先確認(tmp_path, "existing")


def ZIP応答設定(remote, ファイル名="environment.json", 内容=b'{"ok":true}', symlink=False):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as アーカイブ:
        項目 = ZipInfo(ファイル名)
        if symlink:
            項目.create_system = 3
            項目.external_attr = 0o120777 << 16
        アーカイブ.writestr(項目, 内容)
    応答 = Mock()
    応答.iter_content.return_value = [buffer.getvalue()]
    remote.download_kernel_output.return_value = nullcontext(応答)
    return 応答


def test_出力downloadは過去版を整数指定してZIP展開する(記録, tmp_path):
    api, remote = API作成(ファイル名=("environment.json",))
    応答 = ZIP応答設定(remote)
    remote.get_kernel.return_value.metadata.current_version_number = 99
    結果 = 操作.出力取得(api, 記録, tmp_path)
    要求 = remote.download_kernel_output.call_args.args[0]
    assert (要求.owner_slug, 要求.kernel_slug, 要求.version_number) == ("owner", "test-notebook", 7)
    remote.get_kernel.assert_not_called()
    remote.list_kernel_session_output.assert_not_called()
    応答.raise_for_status.assert_called_once()
    assert json.loads((tmp_path / "environment.json").read_bytes()) == {"ok": True}
    assert 結果["version"] == 7


@pytest.mark.parametrize("名前,symlink", [("../outside", False), ("link", True)])
def test_危険なZIPは展開しない(記録, tmp_path, 名前, symlink):
    api, remote = API作成()
    ZIP応答設定(remote, 名前, symlink=symlink)
    with pytest.raises(操作.操作エラー):
        操作.出力取得(api, 記録, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_出力ZIPは既存ファイルを上書きしない(記録, tmp_path):
    api, remote = API作成()
    ZIP応答設定(remote)
    (tmp_path / "environment.json").write_text("existing", encoding="utf-8")
    with pytest.raises(操作.操作エラー, match="既存"):
        操作.出力取得(api, 記録, tmp_path)
    assert (tmp_path / "environment.json").read_text() == "existing"


def test_状態の前後で現行版が変わったら観測結果を採用しない(記録):
    api, remote = API作成()
    初回 = remote.get_kernel.return_value
    次回 = ApiGetKernelResponse()
    次回.metadata = ApiKernelMetadata()
    次回.metadata.ref = 記録["kernel"]
    次回.metadata.current_version_number = 8
    remote.get_kernel.side_effect = [初回, 次回]
    with pytest.raises(操作.操作エラー, match="現行版"):
        操作.状態(api, 記録)


def test_状態または出力一覧で旧版を最新扱いせず提出を拒否(記録):
    api, remote = API作成()
    remote.get_kernel.return_value.metadata.current_version_number = 8
    with pytest.raises(操作.操作エラー, match="現行版"):
        操作.提出(api, 記録, "test")
    remote.get_kernel_session_status.assert_not_called()
    api.competition_submit_code.assert_not_called()


def test_出力一覧の観測中に版が変わったら提出しない(記録):
    api, remote = API作成()
    元 = remote.get_kernel.return_value
    新 = ApiGetKernelResponse()
    新.metadata = ApiKernelMetadata()
    新.metadata.ref = 記録["kernel"]
    新.metadata.current_version_number = 8
    remote.get_kernel.side_effect = [元, 元, 元, 新]
    with pytest.raises(操作.操作エラー, match="現行版"):
        操作.提出(api, 記録, "test")
    remote.list_kernel_session_output.assert_called_once()
    api.competition_submit_code.assert_not_called()


def test_CLIは外部例外本文の秘密を表示せず失敗する(monkeypatch, capsys):
    api, _ = API作成()
    api.competition_list_files.side_effect = RuntimeError("secret-token-must-not-appear")
    monkeypatch.setattr(操作, "認証API", lambda: api)
    assert 操作.main(["接続確認"]) == 1
    出力 = capsys.readouterr()
    assert "secret-token" not in 出力.out + 出力.err
    assert "RuntimeError" in 出力.err


def test_CLIの状態確認は実行失敗を非zeroで返す(記録, tmp_path, monkeypatch, capsys):
    パス = tmp_path / "実行記録.json"
    パス.write_text(json.dumps(記録), encoding="utf-8")
    api, _ = API作成(status=KernelWorkerStatus.ERROR)
    monkeypatch.setattr(操作, "認証API", lambda: api)
    assert 操作.main(["状態", "--record", str(パス)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "ERROR"
