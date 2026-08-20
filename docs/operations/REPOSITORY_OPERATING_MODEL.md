# Repository Operating Model

この文書はARC2攻略戦略ではなく、repositoryそのものを長期運用するための環境設計を説明する。
規範上の実行契約はroot `AGENTS.md`、権威順序はroot `AUTHORITY_ORDER.md`を正本とする。

## 1. Design Goal

戦略、実装、評価、提出、履歴が更新され続けても、AI実装者が現在地点を誤認しないrepositoryを作る。

目的:

1. 戦略未選択でも環境が成立する
2. Current Stateを一か所から解決する
3. 規範と実測を分離する
4. 旧ARC2資産を削除せず権威から隔離する
5. strategy revisionが変わってもAGENTSを書き直さない

## 2. Four Planes

### Normative Plane

何を目指し、何を守るか。

```text
Owner
→ AGENTS.md
→ AUTHORITY_ORDER.md
→ selector-selected specification / roadmap / task / instruction
```

### Selection Plane

今何を実行するか。

```text
control/CURRENT_SELECTOR.json
```

Selectorは`UNSELECTED`を正式に表現できる。

### Evidence Plane

何が実際に成立したか。

```text
source / tests / holdout / runtime / Kaggle run / accepted score
```

### Historical Plane

以前何が起きたか、どの資産が残っているか。

```text
docs/history/
legacy repositories
old reports / old claims / old submission assets
```

## 3. Pre-Strategy State

このrepositoryでは、環境設計と攻略戦略を分離する。

```text
Environment Ready
↓
Strategy Unselected
↓
Owner selects objective projection
↓
Strategy / Roadmap / Current Task
↓
Implementation
```

`UNSELECTED`中に、旧solverのarchitectureやwork blockを暗黙のcurrent strategyへ昇格させない。

## 4. Work Resolution

`SELECTED`後の一作業は次の流れで解決する。

```text
Owner objective
↓
Repository Operating Contract
↓
Current Selector
↓
Selected Task / Instruction
↓
Observed implementation and evidence
↓
Target - Current = Gap
↓
Minimal causal change
↓
Relevant verification
↓
Observed result
↓
Explicit state transition when authorized
```

## 5. Claim / Evidence Boundary

| Level | Evidence | 主張可能範囲 |
|---|---|---|
| E0 | 文書・静的構造・artifact存在 | 定義／存在 |
| E1 | unit/static/schema | 局所契約 |
| E2 | local integrated/holdout | local能力 |
| E3 | declared official-like evaluation | 宣言laneでの能力 |
| E4 | Kaggle platform normal run | platform実行 |
| E5 | accepted official score | 公式結果 |

E0〜E2をE5の代用にしない。

## 6. Legacy Adoption

旧repositoryをコピーすること自体は移行ではない。

採用は少なくとも次を満たす必要がある。

1. 現在の目的に必要な責任を持つ
2. interfaceが現行構造へ接続できる
3. answer leakage／identity routing境界を満たす
4. 現在のtests／evidence laneで再評価できる
5. old claimをcurrent evidenceとして流用しない

## 7. Main-only Operation

repository branchは`main`一本をcanonicalとする。
`.github/workflows/repository-guard.yml`はmain push時に環境checkを実行し、main以外のremote branchを削除する。

## 8. State Transition

`UNSELECTED -> SELECTED`およびPoint advanceは独立した作用として扱う。

- 条件成立
- evidence固定
- transition権限確認
- Selectorとmirror更新
- environment check

の順で閉じる。
