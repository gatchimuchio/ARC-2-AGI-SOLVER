# Control Plane

`control/`はrepositoryの可変な実行状態を扱う。

## Current Entry Point

現在作業の唯一の入口は:

`control/CURRENT_SELECTOR.json`

である。

## Selection Status

### `UNSELECTED`

戦略未選択。repository operating environmentだけが成立している状態。

この状態では以下を`null`にする。

- `active_strategy`
- `spec_path`
- `roadmap_path`
- `roadmap_manifest_path`
- `current_task_path`
- `active_point`
- `active_instruction_path`

`auto_advance_allowed`は`false`。

旧repository、過去文書、README、mtimeから戦略を推測して自動選択しない。

### `SELECTED`

Ownerの指示または正式なstrategy selectionによって、spec／roadmap／task／instructionが選択された状態。

Selectorの参照pathはrepository-relative POSIX pathとし、historical namespaceを指さない。
Current TaskやRoadmap Manifestに同じstate値が存在する場合、それらはSelectorとの整合確認用mirrorとして扱う。

```text
Selector != mirror
=> STATE_DRIFT / visible failure
```

## Transition Rule

`UNSELECTED -> SELECTED`は実装開始の副作用ではなく、明示的なstate transitionである。

1. Owner目的を確定する
2. strategy specificationを置く
3. roadmap／Current Task／instructionを接続する
4. Selectorを同一変更で更新する
5. environment checkerを通す

Point advanceも同様に、exit条件を満たしただけで自動遷移しない。

## Validation

```bash
python scripts/check_repository_environment.py
```
