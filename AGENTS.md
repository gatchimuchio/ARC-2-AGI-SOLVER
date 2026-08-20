# Repository Operating Contract

この文書は、ARC-2-AGI-SOLVERでAI実装エージェント／コード監査者が作業するための**恒久的な運用契約**である。
攻略戦略、現在Point、score、product statusなどの可変状態はここに書かない。

最上位目的は、ARC Prize 2026 / ARC-AGI-2で汎用solverとして公式満点を成立させること。
ただし、この目的に対する具体戦略は`control/CURRENT_SELECTOR.json`で選択するまで未確定として扱う。

## 1. Authority

規範の優先順位:

1. Ownerの現在の明示指示
2. 対象pathに適用される最も近い`AGENTS.md`
3. root `AUTHORITY_ORDER.md`
4. `control/CURRENT_SELECTOR.json`が選択する現行仕様・ロードマップ・Current Task・局所指示
5. 現行コード、interface、tests、設定が示す既存契約
6. 参照repository／historical evidence
7. 推測、記憶、一般論

下位`AGENTS.md`はroot契約を具体化できるが、目的、authority、evidence、failure規則を緩和してはならない。

## 2. Current State

可変な現在状態の入口は次だけである。

`control/CURRENT_SELECTOR.json`

Selectorは`selection_status`を持つ。

- `UNSELECTED`: repository環境のみ成立し、攻略戦略は未選択
- `SELECTED`: spec／roadmap／task／instructionが選択済み

`UNSELECTED`をfailureとして扱わない。戦略決定前にコードやphaseを勝手に作り始めない。
README、AGENTS、旧repository、mtime、ファイル名のrev番号をCurrent Stateの代用品にしてはならない。

## 3. Normative Target と Observed State

```text
Normative Target != Observed State
```

仕様は「どうあるべきか」を定め、source、tests、runtime、official result、Kaggle scoreは「何が成立したか」を示す。
両者が矛盾する場合、観測事実を仕様に合わせて読み替えない。差分をgapとして扱う。

## 4. 作業開始契約

変更前に次を確認する。

1. rootと対象subtreeの`AGENTS.md`
2. `control/CURRENT_SELECTOR.json`
3. `python scripts/check_repository_environment.py`
4. 対象code／tests／evidence／既知failure
5. 目的、現在状態、不足、変更禁止範囲
6. 既存資産とlegacy資産の再利用可能性

既存資産で目的を満たせる場合、別solver、別runner、別schema、別pipelineを重複実装しない。

## 5. Change Principles

### Purpose First

局所test、coverage、artifact数、コード量、形式整理を最上位目的へ昇格させない。
既存設計が目的を阻害する場合、設計を守るために目的を縮小しない。

### Root Cause First

症状だけでなく、再発を生む責任境界を直す。

- authority drift
- state duplication
- hidden fallback
- identity routing
- answer leakage
- interface mismatch
- dependency drift
- evidence gap
- causal misattribution

### Minimal Causal Diff

変更は小ささではなく、目的を成立させる因果が閉じる最小単位にする。
無関係なcleanupやrenameを混ぜない。

## 6. Generalization Boundary

汎用ARC2 solverのruntime decisionに、解答を直接特定する情報を持ち込まない。

禁止例:

- task IDによるanswer routing
- input hash／filenameによる分岐
- dataset ordering依存
- literal answer map
- fixed output grid
- public solutionのruntime参照
- source split labelによる解答選択

診断・teacher evidenceでtask ID等を保持する場合も、production runtimeの選択入力へ逆流させない。

## 7. Evidence and Claims

主張の強さを証拠より上げない。

```text
E0  document / static structure / artifact existence
E1  unit / static / schema / deterministic local check
E2  local integrated / offline evaluation
E3  official sample / declared holdout evaluation
E4  Kaggle platform normal run
E5  official accepted score
```

class、test、artifact、digest、mock PASS、package成功は単独でofficial capabilityの証拠ではない。
score改善を主張するなら、実際にscoreを観測したlaneを示す。

## 8. Verification

変更対象に近い検証から開始し、必要な範囲まで広げる。

1. syntax／static／targeted unit
2. affected integration
3. solver regression／holdout
4. official／Kaggle validation

検証を通すためにgateを弱める、assertionを消す、expected resultを都合よく変更する、例外を握り潰す、別経路へsilent fallbackすることを禁止する。
未実行testをPASSと報告しない。

## 9. Failure Contract

failureは次の判断材料として保持する。

- failure evidenceを削除して成功扱いしない
- 不明値を推測で埋めない
- authority／path／interface不一致をsilent fallbackしない
- official failureをlocal成功で上書きしない
- 成立不能条件が見つかった場合は地点と原因を明示する

## 10. Legacy Boundary

次のrepositoryは再利用候補の**参照資産**であり、現在のAuthorityではない。

- `gatchimuchio/ARC-2-HDS-PERFECT-SOLVER`
- `gatchimuchio/ARC-Layer-0-Functional-Compliance`

旧実装を採用する場合は、現在の目的、interface、generalization boundary、evidence gateへ再接続する。
旧claimをそのままCurrent completionへ昇格させない。

## 11. Git Policy

このrepositoryはOwner方針により**main-only**で運用する。

- canonical branchは`main`のみ
-通常作業もmainを前提とする
- 不要なbranchを恒久保存しない
- `.github/workflows/repository-guard.yml`がmain以外のremote branchをcleanupする
- force push、history rewrite、evidence削除は明示指示なしに行わない

## 12. Completion Report

完了報告では最低限、次を区別する。

- 目的
- changed files／behavior delta
- 実行した検証
- 観測結果
- 未確認事項／残存risk
- Selectorを変更したか否か

「実装した」と「成立を確認した」を同義にしない。
