# Legacy Repository Map

新`ARC-2-AGI-SOLVER`へ移行する際の参照対象を記録する。

## `gatchimuchio/ARC-2-HDS-PERFECT-SOLVER`

既存のARC2 HDS solver再構築repository。
旧AGENTSでは最上位architectureを次の4責任として定義していた。

```text
HDS Judgement Runtime
+ ARC2 Capability Stack
+ Immutable Compiled Knowledge
+ Submission Runtime
```

またtask ID、input hash、literal answer map、fixed output等をruntime selectionへ持ち込まないgeneralization boundaryを持っていた。

一方、そのsnapshotのREADMEではproduction emitter、clean-holdout completion evidence、official score-improvement claimは未成立と明記されていた。

したがって新repositoryでは、実装・tests・teacher/evaluation資産を**再利用候補**として扱い、旧completion claimやphaseをCurrent Authorityとして継承しない。

## `gatchimuchio/ARC-Layer-0-Functional-Compliance`

ARC関連の既存Layer-0資産repository。
新ARC2へ採用する場合は、必要な責任とinterfaceを個別に棚卸しし、現行strategyへ明示接続する。

## Adoption Rule

legacy asset採用時は次を確認する。

1. 何の責任を担うか
2. 現行目的に必要か
3. runtime generalization boundaryを満たすか
4. answer／identity leakageがないか
5. current evaluationで再現可能か
6. old claimをcurrent evidenceへ流用していないか
