"""壊れたARC入力と未取得の配布を区別できることを確認する。"""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


仕様 = importlib.util.spec_from_file_location(
    "開発環境確認", Path(__file__).resolve().parents[1] / "道具/開発環境確認.py"
)
確認 = importlib.util.module_from_spec(仕様)
仕様.loader.exec_module(確認)


class 開発環境確認試験(unittest.TestCase):
    def test_公開問題のtestにもoutputが必要(self):
        問題 = {"train": [{"input": [[0]], "output": [[1]]}], "test": [{"input": [[0]]}]}
        with self.assertRaisesRegex(ValueError, "test.*output.*欠落"):
            確認.公開問題確認(問題)
        問題["test"][0]["output"] = [[2]]
        確認.公開問題確認(問題)

    def test_不正グリッドを拒否(self):
        for 不正 in ([], [[]], [[1], [1, 2]], [[True]], [[1.0]], [[10]], [[-1]], [[0] * 31]):
            with self.subTest(不正=不正), self.assertRaises(ValueError):
                確認.グリッド確認(不正, "test")
        確認.グリッド確認([[0, 9], [1, 8]], "test")

    def test_空のtrainやtestを拒否(self):
        for 区分 in ("train", "test"):
            問題 = {
                "train": [{"input": [[0]], "output": [[1]]}],
                "test": [{"input": [[0]], "output": [[1]]}],
            }
            問題[区分] = []
            with self.subTest(区分=区分), self.assertRaises(ValueError):
                確認.公開問題確認(問題)

    def test_Kaggle未取得と内容不一致を区別(self):
        固定 = {"外部固定ファイル": {"sample_submission.json": {"サイズbyte": 2, "SHA256": "invalid"}}}
        with tempfile.TemporaryDirectory() as 一時, patch.object(確認, "ルート", Path(一時)):
            結果 = 確認.Kaggle配布確認(固定)
            self.assertEqual(結果["未取得"], ["sample_submission.json"])
            保存先 = Path(一時) / "入力/Kaggle/sample_submission.json"
            保存先.parent.mkdir(parents=True)
            保存先.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "不一致"):
                確認.Kaggle配布確認(固定)

    def test_HEAD一致でも公式ソースの変更を拒否(self):
        固定 = {"公式ソース": {"commit": "fixed"}}
        結果 = [
            subprocess.CompletedProcess([], 0, "fixed\n"),
            subprocess.CompletedProcess([], 0, " M data/training/example.json\n"),
        ]
        with tempfile.TemporaryDirectory() as 一時, patch.object(確認, "ルート", Path(一時)):
            Git印 = Path(一時) / "入力/公式ソース/ARC-AGI-2/.git"
            Git印.parent.mkdir(parents=True)
            Git印.touch()
            with patch.object(確認.subprocess, "run", side_effect=結果):
                with self.assertRaisesRegex(ValueError, "作業木に変更"):
                    確認.公式ソース確認(固定)

    def test_runtime依存の宣言と実環境の不一致を拒否(self):
        with tempfile.TemporaryDirectory() as 一時, patch.object(確認, "ルート", Path(一時)):
            ルート = Path(一時)
            (ルート / "requirements-runtime.txt").write_text("numpy==2.3.5\n", encoding="utf-8")
            設定 = ルート / "pyproject.toml"
            設定.write_text('[project]\ndependencies = ["numpy==2.5.3"]\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "依存指定が不一致"):
                確認.runtime依存確認()
            設定.write_text('[project]\ndependencies = ["numpy==2.3.5"]\n', encoding="utf-8")
            with patch.object(確認.importlib.metadata, "version", return_value="2.5.3"):
                with self.assertRaisesRegex(ValueError, "版不一致"):
                    確認.runtime依存確認()
            with patch.object(確認.importlib.metadata, "version", return_value="2.3.5"):
                self.assertEqual(確認.runtime依存確認(), {"numpy": "2.3.5"})


if __name__ == "__main__":
    unittest.main()
