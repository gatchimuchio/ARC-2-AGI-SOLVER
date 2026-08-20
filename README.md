# ARC-2 AGI Solver

ARC Prize 2026 / ARC-AGI-2を対象に、HDS・ミニドラ・記憶の三主体構成で満点を狙うためのrepository。

## 基底方針

実務上やむを得ない外部境界を除き、設計・判断・記憶・診断・内部schema・命令形の基底言語は日本語とする。

```text
AGI = HDS + ミニドラ（LLM） + 記憶
HDSコンパイラ ∈ HDS
```

現在状態の唯一の入口は[`制御/現在状態.json`](制御/現在状態.json)。現在は再設計中で、戦略は未選択。

## ARC2公式入力

公式サンプル資産は`入力/公式サンプル/`、公式ARC-AGI-2 sourceは`入力/公式ソース/ARC-AGI-2`に固定する。これらは攻略戦略ではなく入力正本である。

## Repository Map

```text
AGENTS.md                 恒久的なAI実装・監査契約
制御/                     現在状態の単一入口
運用/                     日本語基底・権限・運用規則
設計/                     AGI三主体の不変構成
HDS/                      入力・判断主体とHDSコンパイラ
ミニドラ/                 LLM主体
記憶/                     Prior / Runtime Memory
入力/                     ARC2公式入力資産
接続/                     Kaggle / ARC / Python等の外部境界
戦略/                     今後選択する攻略戦略
検証/                     実行結果と証拠
道具/                     repository-level監査・変換工具
```

旧構成・旧英語正本・過去の実装候補はGit履歴に残るが、現在の権威ではない。Ownerの明示指示なしに復活させない。

環境監査:

```bash
python3 道具/リポジトリ環境監査.py
```
