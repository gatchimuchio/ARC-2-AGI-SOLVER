# Repository Authority Model

この文書はARC-2-AGI-SOLVERの**規範権威、実行選択、観測事実、履歴**の関係を定義する。
現在Point、score、product status等の可変状態は保持しない。

## 1. Normative Authority Plane

1. Ownerの現在の明示指示
2. root `AGENTS.md`と対象pathの下位`AGENTS.md`
3. root `AUTHORITY_ORDER.md`
4. `control/CURRENT_SELECTOR.json`が選択するspecification
5. 同Selectorが選択するroadmap
6. 同Selectorが選択するCurrent Task
7. 同Selectorが選択するlocal instruction
8. current code／tests／configurationが示す既存interface契約

Selectorが`UNSELECTED`の場合、4〜7は存在しない。過去repositoryや一般論で勝手に補完しない。

## 2. Selection Plane

「今どの戦略・Task・Instructionを実行するか」の唯一の入口は:

`control/CURRENT_SELECTOR.json`

である。

```text
selection_status = UNSELECTED
=> repository environment only; strategy is not yet authoritative

selection_status = SELECTED
=> selector-selected documents define current work
```

README、commit時刻、ファイル名、旧phase stateはselectorではない。

## 3. Observed Reality Plane

以下は権威文書ではなく、実際に何が成立したかを示す観測面である。

- source code
- unit／integration／holdout results
- runtime trace
- generated reports
- official sample evaluation
- Kaggle execution
- accepted official score

```text
Authority decides what should be done.
Evidence decides what has been established.
```

規範に「完成」と書かれていても、必要Evidenceが未成立なら能力は未成立である。

## 4. Conflict Rule

```text
Target says PASS + Evidence says FAIL
=> FAIL is observed state; target remains repair objective.
```

```text
Historical claim says COMPLETE + Current selector/evidence does not support it
=> preserve historical claim; do not promote it to current completion.
```

矛盾を無言で平均化・再解釈しない。

## 5. Historical / Legacy Plane

以下は原則としてcurrent authorityではない。

- `docs/history/`
- selectorから選択されない旧strategy／roadmap／instruction
- 旧solver repositoryのcode／reports／claims
- 旧release／submission artifact

legacy assetは再利用候補である。再利用時は、現在のinterfaceとevidence条件へ再接続する。

## 6. Stable Surface Rule

次のstable surfaceへactive strategy ID、active Point ID、current score等を転記しない。

- `AGENTS.md`
- `AUTHORITY_ORDER.md`
- root `README.md`
- `docs/README.md`
- `docs/operations/`

Current StateはSelectorから読む。
