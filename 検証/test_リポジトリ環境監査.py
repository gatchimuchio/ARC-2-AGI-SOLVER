"""現在状態の選択を保持し、構造破損を拒否する監査の回帰試験。"""

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


仕様 = importlib.util.spec_from_file_location(
    "リポジトリ環境監査", Path(__file__).resolve().parents[1] / "道具/リポジトリ環境監査.py"
)
監査 = importlib.util.module_from_spec(仕様)
仕様.loader.exec_module(監査)


class リポジトリ環境監査試験(unittest.TestCase):
    def setUp(self):
        一時 = tempfile.TemporaryDirectory()
        self.addCleanup(一時.cleanup)
        self.ルート = Path(一時.name).resolve()
        self.状態 = {
            "スキーマ版": "arc2-current-state-ja-v2",
            "基底言語": "日本語",
            "状態": "検証中",
            "現在作業": "構造確認",
            "戦略": "選択された戦略",
            "自動遷移": False,
            "学習機械正本": "HDS/試験用学習機械",
        }
        for 名前 in (*監査.必須, "HDS/試験用学習機械/README.md"):
            対象 = self.ルート / 名前
            対象.parent.mkdir(parents=True, exist_ok=True)
            対象.write_text("", encoding="utf-8")
        差替 = patch.object(監査, "ルート", self.ルート)
        差替.start()
        self.addCleanup(差替.stop)

    def 実行(self):
        (self.ルート / "制御/現在状態.json").write_text(
            json.dumps(self.状態, ensure_ascii=False), encoding="utf-8"
        )
        with redirect_stdout(io.StringIO()) as 出力:
            監査.main()
        return json.loads(出力.getvalue())

    def test_選択済みと未選択の戦略を保持する(self):
        for 戦略 in ("選択された戦略", None):
            with self.subTest(戦略=戦略):
                self.状態["戦略"] = 戦略
                結果 = self.実行()
                self.assertEqual(結果["状態"], "合格")
                self.assertEqual(結果["学習機械"], self.状態["学習機械正本"])
                self.assertIn("解答性能は未評価", 結果["検証範囲"])
                self.assertEqual(
                    json.loads((self.ルート / "制御/現在状態.json").read_text(encoding="utf-8")),
                    self.状態,
                )

    def test_不正な現在状態を拒否する(self):
        for 項目, 値 in (
            ("スキーマ版", "arc2-current-state-ja-v1"),
            ("基底言語", "英語"),
            ("状態", ""),
            ("現在作業", None),
            ("戦略", True),
            ("戦略", " "),
            ("自動遷移", True),
            ("自動遷移", 0),
            ("学習機械正本", "存在しない学習機械"),
            ("学習機械正本", "../外部"),
        ):
            with self.subTest(項目=項目, 値=値), self.assertRaises(SystemExit):
                監査.現在状態確認({**self.状態, 項目: 値})
        for 欠落 in self.状態:
            with self.subTest(欠落=欠落), self.assertRaises(SystemExit):
                監査.現在状態確認({k: v for k, v in self.状態.items() if k != 欠落})
        with self.assertRaises(SystemExit):
            監査.現在状態確認([])

    def test_空directoryは許容するが旧構成ファイルは拒否する(self):
        残存 = self.ルート / "ミニドラ/空の下位directory"
        残存.mkdir(parents=True)
        self.assertEqual(self.実行()["状態"], "合格")
        (残存 / "README.md").write_text("旧構成", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "除去済み構成が再出現"):
            self.実行()

    def test_不正JSONは合格にしない(self):
        (self.ルート / "制御/現在状態.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "現在状態を読めない"):
            監査.main()

    def test_選択した学習機械のREADME欠落を拒否する(self):
        (self.ルート / self.状態["学習機械正本"] / "README.md").unlink()
        with self.assertRaisesRegex(SystemExit, "学習機械正本またはREADME"):
            self.実行()


if __name__ == "__main__":
    unittest.main()
