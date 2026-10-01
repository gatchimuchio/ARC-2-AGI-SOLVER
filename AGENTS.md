# AGENTS.md — ARC2 標準作業要領

## 目的
Ownerの現在の明示目的を保持し、ARC2の実装・解析・評価を行い、成立した成果だけを残す。

## 権限
1. Ownerの現在の明示指示
2. AGENTS.md
3. 制御/現在状態.json
4. 現行コード・tests・runtime結果・公式結果
5. Git履歴・一般論・推測

未確認事項を推測で補完しない。

## 保護対象
Ownerの明示指示なしに、AGENTS.md、制御/現在状態.json、運用上の権限・目的を変更・削除・再定義してはならない。
作業者が自分で規範を書き換え、その規範を根拠に自分の作業を正当化してはならない。

## 現行基底
- 学習機械: HDS/学習系統/v0.4.2
- 公式入力: 入力/
- 事前記憶: 記憶/事前記憶/v0.4
- 現在状態: 制御/現在状態.json

## 作業
現状観測 → 原因特定 → 最小変更 → targeted test → local evaluation → regression → 差分監査 → 採否。

禁止:
- 問題ID・filename・hashによる答え分岐
- answer map、固定出力、問題専用script
- 評価正解・hidden情報のruntime流入
- 無関係なrefactorや重複実装
- test数、artifact数、機構追加を性能改善と読み替えること

能力改善を主張する場合は同一条件の previous / current / delta を示す。
改善未確認の変更を成果としてmainへ積み上げない。

## Git
main一本を基本とする。force push、history rewrite、証拠破壊はOwnerの明示指示なしに行わない。
GitHubには成立した成果と履歴だけを残す。
