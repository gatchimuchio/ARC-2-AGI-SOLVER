# AGENTS.md — ARC2 標準作業仕様・標準作業要領書

## 1. 目的・優先順位

本書は、ARC2 の開発・修正・解析・評価・監査を行うAI作業者の標準作業要領である。
目的は作業量を増やすことではなく、Ownerの目的を保持し、必要な変更を実装・検証し、成立した成果だけを残すことである。

優先順位:

1. Ownerの現在の明示指示
2. 対象pathに最も近い `AGENTS.md`
3. `制御/現在状態.json` が選択する現行正本
4. 現行仕様・コード・tests・runtime結果・公式結果
5. 過去ログ・Git履歴・memory・一般論・推測

過去資産を現在の指示として扱わない。未確認事項を推測で補完しない。

## 2. 日本語基底・現在状態

内部意味の正本は日本語とする。
英語はコード、API、SDK、package、Kaggle/ARC固定記号など外部接続上必要な範囲に限定する。

現在状態の入口は `制御/現在状態.json` とする。
README、過去ログ、Git履歴から現在の戦略・作業対象を推測しない。
戦略が未選択なら勝手に補完しない。

## 3. 作業場所・GitHub運用

GitHubは作業場所ではなく、成果物・正本・履歴を保存する保管庫として扱う。

標準経路:

```text
GitHub mainの現行版を取得
→ サンドボックスへ展開
→ 調査・実装・試験・評価
→ 差分監査・採否
→ 成立した成果だけmainへ直接反映
```

- 実装、修正、通常試験、局所評価はサンドボックスまたはローカルで行う。
- remote repositoryは `main` 一本を基本とする。
- Ownerが明示指示しない限り作業branchを作らない。
- Pull Requestは使用しない。
- 二世代backup運用は要求しない。通常のGit履歴でrollback可能性を保持する。
- force push、history rewrite、証拠破壊をOwnerの明示指示なしに行わない。

## 4. 作業開始

変更前に必ず次を行う。

1. `python3 道具/リポジトリ環境監査.py`
2. `制御/現在状態.json` を読む。
3. Ownerの今回の目的を一文で固定する。
4. 関連仕様・コード・tests・評価経路・baselineを確認する。
5. 既存能力と不足を切り分ける。
6. 既存dirty差分や未追跡物を勝手に破壊しない。

同じ責任を持つ既存機能を確認せず、代替実装を新造しない。

## 5. 標準作業工程

```text
現状観測
→ 不足と原因の特定
→ 既存能力との照合
→ 変更責任の決定
→ 最小設計
→ 実装
→ targeted test
→ local integrated evaluation
→ regression確認
→ 差分監査
→ HDSによる採否
→ 成立した成果だけmainへ保存
→ remote反映確認
```

局所課題、中間指標、直近の失敗原因を、Ownerが定めた元の目的より上位へ昇格させない。

## 6. 実装・ARC固有規律

変更は目的を成立させる必要十分な範囲に限定する。

禁止:

- 無関係なrefactor、整理、再設計
- 重複実装、不要なfallback、parallel implementation
- testを通すためだけのproduction変更
- task / game / level IDによる答え分岐
- answer map、replay lookup、固定action列、問題固有script
- evaluator内部・hidden state・非公開正解の利用
- 評価用正解をMemoryへ入れて一般能力として扱うこと
- filename等による暗黙routing
- 競技規則外の外部情報取得

公開問題の解析結果をruntimeへ昇格する場合は、現在入力から再利用可能に導出できる構造へ蒸留する。

ARCの現行知能構成は次の責任境界を壊さない。

```text
HDS → ミニドラ / LLM ⇄ 記憶 → HDS → 出力・作用 → 再観測
```

HDSは観測・判断・採否・記憶更新を管轄する。
ミニドラ / LLMは推論・仮説・計画・候補生成を担い、HDSを迂回して最終出力や記憶更新を確定しない。
HDSコンパイラ等の補助機構を独立した判断主体へ昇格させない。
詳細構造は現行仕様を参照し、AGENTS.mdで再定義しない。

## 7. 試験・評価・GitHub Actions

通常の品質確認は作業者自身がサンドボックスで完了させる。

標準順:

```text
targeted test
→ 関連unit / integration
→ local evaluator
→ 必要なregression
→ 必要なら全数評価
```

能力改善を主張する比較は可能な限り同一条件で行い、`previous / current / delta / 副作用`を分ける。
未実行をPASSと書かない。実装したことと成立したことを同義にしない。

GitHub Actions / CIを通常の品質保証主体にしない。
push等を契機とする自動CIを標準運用にしない。

Actionsを使う場合は、原則として次に限定する。

- ローカルにないOS・外部環境での受入検査
- Kaggle / GitHub等の環境固有処理
- 重いbenchmark、全数評価、長時間・高負荷処理
- 外部runnerを使う合理性があるartifact生成

通常のunit test、regression、static check、local integrationをActionsへ代行させない。
必要なActionsは手動起動を基本とし、Actions成功を完成証拠へ自動昇格させない。

## 8. 失敗・採否

失敗を握り潰さず、原因・条件・影響範囲・反証条件・rollback・次のprobeへ圧縮して残す。
原因未確定なら未確定のまま保持する。

候補は必要に応じて `ADMIT / HOLD / REJECT / QUARANTINE / SUSPEND` に分類する。

- `ADMIT`: 要求を満たし採用可能
- `HOLD`: 成立しているが現在目的への前進が未確認
- `REJECT`: 回帰・誤仮説・目的不適合
- `QUARANTINE`: 診断用。通常runtimeへ採用しない
- `SUSPEND`: 証拠不足・原因未確定・正本衝突等で判断不能

score上昇だけで自動採用しない。

## 9. mainへの反映

検証・採否・差分監査が終わってから反映する。

```text
差分確認
→ 関連変更だけstage
→ commit
→ mainへpush
→ remote main確認
```

無差別stageを標準操作にしない。
作業途中や不採用候補をGitHubへ積み上げない。
rollback時は当該候補の差分だけを対象とし、Ownerや他作業者の既存差分を巻き込まない。

## 10. 完了報告

次を満たすまで完了としない。

- Owner要求が成立している。
- 必要な実装と検証が終わっている。
- 必要範囲のregressionを確認している。
- 未確認事項を把握している。
- 採否と差分監査が終わっている。
- GitHub反映案件ではmainへのpushとremote確認が終わっている。

最終報告は日本語で簡潔に、次を示す。

1. 目的
2. 変更内容・変更ファイル
3. 実行したtest / evaluationと結果
4. previous / current / delta と副作用
5. 採否
6. 未確認事項・残存問題
7. commit hash
8. push結果・remote main確認

**サンドボックスで仕事を完成させ、GitHubには完成した成果と履歴だけを残す。**
