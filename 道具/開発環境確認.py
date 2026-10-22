#!/usr/bin/env python3
"""通信せず、ローカル開発環境と公開データの利用可否を確認する。"""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import subprocess
import sys
import tomllib


ルート = Path(__file__).resolve().parents[1]
必須配布 = (
    "numpy", "scipy", "hds-learning-system", "matplotlib", "pytest", "ruff",
    "ipykernel", "jupyterlab", "kaggle", "kagglesdk",
)


def グリッド確認(グリッド: object, 場所: str) -> None:
    if not isinstance(グリッド, list) or not 1 <= len(グリッド) <= 30:
        raise ValueError(f"{場所}: 行数が1〜30ではない")
    幅 = None
    for 行 in グリッド:
        if not isinstance(行, list) or not 1 <= len(行) <= 30:
            raise ValueError(f"{場所}: 列数が1〜30ではない")
        if 幅 is None:
            幅 = len(行)
        if len(行) != 幅:
            raise ValueError(f"{場所}: 長方形ではない")
        if any(type(色) is not int or not 0 <= 色 <= 9 for 色 in 行):
            raise ValueError(f"{場所}: 色が整数0〜9ではない")


def 公開問題確認(問題: object) -> None:
    if not isinstance(問題, dict):
        raise ValueError("問題がobjectではない")
    for 区分 in ("train", "test"):
        例一覧 = 問題.get(区分)
        if not isinstance(例一覧, list) or not 例一覧:
            raise ValueError(f"{区分}: 例がない")
        for 番号, 例 in enumerate(例一覧):
            if not isinstance(例, dict):
                raise ValueError(f"{区分}[{番号}]: 例がobjectではない")
            # 対象は正解が公開された公式sourceのみ。hidden testへは適用しない。
            for キー in ("input", "output"):
                場所 = f"{区分}[{番号}].{キー}"
                if キー not in 例:
                    raise ValueError(f"{場所}: 欠落")
                グリッド確認(例[キー], 場所)


def Python確認() -> dict:
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Python 3.12が必要")
    if sys.prefix == sys.base_prefix or Path(sys.prefix).resolve() != ルート / ".venv":
        raise ValueError("このrepositoryの.venvで実行してください")
    return {"版": sys.version.split()[0], "仮想環境": ".venv"}


def 配布確認() -> dict:
    版 = {}
    不足 = []
    for 名前 in 必須配布:
        try:
            # kaggle自体をimportすると認証が走るため、metadataのみを読む。
            版[名前] = importlib.metadata.version(名前)
        except importlib.metadata.PackageNotFoundError:
            不足.append(名前)
    if 不足:
        raise ValueError(f"依存package欠落: {', '.join(不足)}")
    return 版


def 描画確認() -> dict:
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    図 = Figure(figsize=(2, 2))
    FigureCanvasAgg(図)
    軸 = 図.subplots()
    軸.imshow(np.arange(9, dtype=np.int8).reshape(3, 3), vmin=0, vmax=9)
    with io.BytesIO() as 出力:
        図.savefig(出力, format="png")
        if not 出力.getvalue().startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNG描画に失敗")
        サイズ = 出力.tell()
    return {"backend": "Agg", "PNGバイト数": サイズ, "保存先": "メモリのみ"}


def runtime依存確認() -> dict:
    指定 = [
        行.strip()
        for 行 in (ルート / "requirements-runtime.txt").read_text(encoding="utf-8").splitlines()
        if 行.strip() and not 行.lstrip().startswith("#")
    ]
    宣言 = tomllib.loads((ルート / "pyproject.toml").read_text(encoding="utf-8"))
    if set(指定) != set(宣言["project"]["dependencies"]):
        raise ValueError("pyprojectとrequirements-runtimeの依存指定が不一致")
    版 = {}
    for 条件 in 指定:
        名前, 期待 = 条件.split("==")
        実測 = importlib.metadata.version(名前)
        if 実測 != 期待:
            raise ValueError(f"runtime依存の版不一致: {名前} は {期待} が必要、実測 {実測}")
        版[名前] = 実測
    return 版


def 数値計算確認() -> dict:
    from hds学習系統 import HDS学習実行系
    import numpy as np
    from scipy.optimize import Bounds, milp

    結果 = milp(
        c=np.array([1.0]), integrality=np.array([1]),
        bounds=Bounds([1.0], [3.0]), options={"time_limit": 5.0},
    )
    if not 結果.success or not np.allclose(結果.x, [1.0]):
        raise ValueError("SciPy/HiGHSの整数計画起動に失敗")
    return {
        "NumPy/SciPy/HiGHS": "起動成功", "目的値": float(結果.fun),
        "学習機械import": HDS学習実行系.__module__,
    }


def 公式ソース確認(マニフェスト: dict) -> dict:
    ソース = ルート / "入力/公式ソース/ARC-AGI-2"
    if not (ソース / ".git").exists():
        raise ValueError("公式submodule未取得: git submodule update --init --recursive が必要")
    結果 = subprocess.run(
        ["git", "-C", str(ソース), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if 結果.returncode:
        raise ValueError("公式submoduleのHEADを読めない")
    commit = 結果.stdout.strip()
    if commit != マニフェスト["公式ソース"]["commit"]:
        raise ValueError("公式submoduleのHEADとmanifestの固定commitが不一致")
    差分 = subprocess.run(
        ["git", "-C", str(ソース), "status", "--porcelain", "--untracked-files=normal"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if 差分.returncode:
        raise ValueError("公式submoduleの作業木の変更有無を読めない")
    if 差分.stdout.strip():
        raise ValueError("公式submoduleの作業木に変更または未追跡ファイルがある")
    件数 = {}
    for 区分, 期待数 in (("training", 1000), ("evaluation", 120)):
        ファイル一覧 = sorted((ソース / "data" / 区分).glob("*.json"))
        if len(ファイル一覧) != 期待数:
            raise ValueError(f"公開{区分}: {len(ファイル一覧)}件、期待{期待数}件")
        for ファイル in ファイル一覧:
            try:
                公開問題確認(json.loads(ファイル.read_text(encoding="utf-8")))
            except (OSError, ValueError) as 例外:
                raise ValueError(f"公開{区分}/{ファイル.name}: {例外}") from 例外
        件数[区分] = len(ファイル一覧)
    return {
        "commit": commit,
        "作業木": "変更なし",
        "公開問題数": 件数,
        "test正解": "全件公開outputを検証済み",
    }


def Kaggle配布確認(マニフェスト: dict) -> dict:
    未取得 = []
    検証済み = []
    for 名前, 期待 in マニフェスト["外部固定ファイル"].items():
        ファイル = ルート / "入力/Kaggle" / 名前
        if not ファイル.is_file():
            未取得.append(名前)
            continue
        内容 = ファイル.read_bytes()
        if len(内容) != 期待["サイズbyte"] or hashlib.sha256(内容).hexdigest() != 期待["SHA256"]:
            raise ValueError(f"Kaggle配布/{名前}: manifestのサイズまたはSHA256と不一致")
        検証済み.append(名前)
    return {
        "取得状態": "未取得あり" if 未取得 else "全6ファイルが固定manifestと一致",
        "未取得": 未取得,
        "検証済み": 検証済み,
        "注記": "公開sourceの利用可否とKaggle配布の取得・同一性は別に判定する",
    }


def main() -> int:
    検査 = []
    Kaggle配布 = {"取得状態": "未確認"}

    def 確認(名前, 処理):
        try:
            詳細 = 処理()
        except Exception as 例外:
            # 環境変数・認証情報・外部commandのstderrは出力しない。
            理由 = str(例外) if isinstance(例外, ValueError) else type(例外).__name__
            検査.append({"対象": 名前, "状態": "失敗", "理由": 理由})
        else:
            検査.append({"対象": 名前, "状態": "合格", "詳細": 詳細})

    確認("Python", Python確認)
    確認("依存package", 配布確認)
    確認("runtime依存契約", runtime依存確認)
    確認("数値計算", 数値計算確認)
    確認("グリッド描画", 描画確認)
    try:
        マニフェスト = json.loads(
            (ルート / "入力/公式サンプル/マニフェスト.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        検査.append({"対象": "manifest", "状態": "失敗", "理由": "固定manifestを読めない"})
    else:
        確認("公式公開source", lambda: 公式ソース確認(マニフェスト))
        try:
            Kaggle配布 = Kaggle配布確認(マニフェスト)
        except (OSError, ValueError, KeyError) as 例外:
            理由 = str(例外) if isinstance(例外, ValueError) else type(例外).__name__
            Kaggle配布 = {"取得状態": "検証失敗", "理由": 理由}
            検査.append({"対象": "Kaggle配布", "状態": "失敗", "理由": 理由})
    合格 = all(項目["状態"] == "合格" for 項目 in 検査)
    print(
        json.dumps(
            {"開発環境": "合格" if 合格 else "失敗", "検査": 検査, "Kaggle配布": Kaggle配布},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if 合格 else 1


if __name__ == "__main__":
    raise SystemExit(main())
