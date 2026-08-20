# ARC-2 AGI Solver

ARC Prize 2026 / ARC-AGI-2で、汎用solverとして公式満点を狙うための実装repositoryです。

このrepositoryは**戦略より先に開発環境を固定する**方針で運用します。現在Point、score、product status、攻略revなどの可変状態をREADMEやAGENTSへ複製しません。

## Current State

現在作業の唯一の入口:

[`control/CURRENT_SELECTOR.json`](control/CURRENT_SELECTOR.json)

初期状態ではstrategyは未選択です。戦略を決める前でもrepository operating contract、履歴境界、検証規則、main-only運用は成立します。

環境整合の確認:

```bash
python scripts/check_repository_environment.py
```

## Operating Contract

- [`AGENTS.md`](AGENTS.md): repository-wide implementation contract
- [`AUTHORITY_ORDER.md`](AUTHORITY_ORDER.md): authority / evidence / history boundary
- [`docs/operations/REPOSITORY_OPERATING_MODEL.md`](docs/operations/REPOSITORY_OPERATING_MODEL.md): repository operating model
- [`control/README.md`](control/README.md): Current Selectorとstate transition契約

## Repository Map

```text
AGENTS.md                  stable agent operating contract
AUTHORITY_ORDER.md         authority / evidence / history model
control/                   single Current Selector and future state
docs/operations/           stable repository operating model
docs/strategy/             strategy specifications
docs/roadmap/              implementation roadmaps
docs/instructions/         local execution instructions
docs/history/              legacy / historical asset index
scripts/                   repository-level audit / validation tools
.github/workflows/          repository guard and main-only enforcement
```

## Legacy Assets

既存のARC2実装資産は削除せず、別repositoryに保持されています。

- `gatchimuchio/ARC-2-HDS-PERFECT-SOLVER`
- `gatchimuchio/ARC-Layer-0-Functional-Compliance`

これらは再利用候補ですが、新repositoryのCurrent Authorityではありません。採用時は現在の目的・interface・evidence条件へ再接続します。

詳細は[`docs/history/LEGACY_REPOSITORIES.md`](docs/history/LEGACY_REPOSITORIES.md)を参照してください。
