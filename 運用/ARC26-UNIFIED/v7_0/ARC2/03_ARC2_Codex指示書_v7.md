# ARC-AGI-2 Codex実行指示書 v7.0（実装・検収命令）

**対象リポ**：`https://github.com/gatchimuchio/ARC-2-AGI-SOLVER` `main`。  
**適用一式**：同梱`01_ARC2_仕様書_v7.md`、`02_ARC2_工程表_v7.md`、本書。**この3ファイルでARC2指示は自己完結**。旧共通v6の未達成部分は証拠として保持するが、実行優先順位は現Owner指示とv7に合わせる。ARC3は触るな。

## 0. 絶対命令：やるべきことを取り違えるな

> **既存のHDSラーニングマシン・事前記憶・公開データ・ARC2既存コードを使い、未知の格子を実際に正解し、HDSの学習効果を実証し、Kaggle公式提出をエラーなしで受理・採点させ、その数値を反復改善して優勝を狙え。**

あなた（Codex）は**指示を実装し、実行結果で検証する担当者**。方針そのものを独断で書き換えず、目的に合わないローカルな達成条件を作るな。提出ルート・実格子生成・競技力改善を切り離して「どれか達成で完了」とするな。

**重要な訂正**：**提出エラーは公式採点成立の受理ではない。エラー後はKaggleで残枠を照会し、送信できる限りその日でも何度でも修正・再提出を試みよ。** 形式PASSやNotebook`COMPLETE`、低得点`0.00`の正式採点と混同するな。実際にKaggle側で制限された場合だけ、そのAPI根拠・解除条件・次の行動を報告し、無理な迂回はしない。

## 1. 開始前30分：現状の事実を掴む

必ず以下の順に**観測してから変更**する。

1. `git status --short`、`git rev-parse HEAD`、`AGENTS.md`、`制御/現在状態.json`、現行HDS・記憶・Kaggle adapter、旧v6文書、提出監視台帳、AGI-2公式サンプルを確認。ユーザーの既存未コミット変更を残す。
2. `接続/ARC2/HDS接続.py`、`接続/ARC2/Kaggle提出.py`、`道具/ARC2Kaggle提出bundle.py`、`検証/ARC2評価.py`と`接続/Kaggle操作`の**現行CLI `--help`/関数仕様**を確認。存在しないサブコマンドを作り話で実行しない。
3. 添付データ実数を比較する。参照版は`training 1000`, `evaluation 120 tasks / 172 test grids`, `test 240 tasks / 259 test grids`。リポに他版があれば差を記録し、採点器に入れる母数は常に実入力から導出。**旧120/167を現行と同一視しない**。
4. Kaggle接続を使って**現在の提出履歴・残枠・終端状態・エラー詳細**を確認。特に`57682971`の`COMPLETE`＋`publicScore=null`＋`Notebook Timeout`は**採点不成立**として扱い、実状態を再照会。近時の数値`0.00`と旧ベスト`0.83`は区別する。
5. スコアリング失敗を再現可能な局所実験へ分解。**なぜprivate完走できてもscoringでtimeoutなのか**を実ログで切り分ける。明確でないなら暫定原因のまま、修正後の検証で絞る。
6. **勝利の距離を数値で見る**：10/27の公開順位転載では首位88.06%、観測された自己ベスト0.83%は**87.23ポイント差**。最新Kaggle値を照合し、旧family拡張だけを主要攻略法とするな。
7. **受賞資格の公開義務を確認**：公式は賞の対象になる使用コード・方法のオープンソース化を要求する。一方、Ownerは非開示のHDS中核を保護している。公開できるDomain Adapter・公開済みソルバーによる構成を優先し、**秘密中核の開示を勝手に決定するな**。資格と秘密保持が両立しない場合、コードの変更前にOwnerへ選択を求める。

最低限の実行起点（環境に合わせて`uv`/`python`を選択し、先に`--help`を見る）：

```bash
git status --short
git rev-parse HEAD
uv run --locked python -m 接続.Kaggle操作 接続確認
uv run --locked python -m 接続.Kaggle操作 履歴
uv run --locked python 検証/ARC2評価.py --help
uv run --locked python 道具/ARC2Kaggle提出bundle.py --help
uv run --locked python -m 接続.Kaggle操作 --help
```

`uv`未導入なら正しい既存実行環境へ置換する。**入力ファイル・lock・envを勝手に作り直さない**。

## 2. 最初の実装：公式得点の出口を先に復旧

**最初のゲート**：高得点モデルを構想するだけでなく、**本番でエラーなしに数値スコアを返す最小構成**を確保。

1. 既存HDS/記憶を実際に読み、既存の`Kaggle提出.py`から全taskを処理。起動、タスク内、候補選択、タスク完了、`submission.json`保存、終了のタイミングをログ計測。
2. **総時間の内部予算、タスク時間上限、worker停止、最終書出し時間、RAM監視**を実装・調整し、競技のCPU/GPU 12時間に余裕を持って収める。スレッドの未完join、孤児プロセス、書出し後停止不能等を実測して解消。private runtimeが400秒程度で終わった観測だけでscoringの完走を保証してはいけない。
3. 出力フォーマットは**公式sampleに完全準拠**。各taskのtest例数と順序、合法grid、`attempt_1`/`attempt_2`、元データのID、`submission.json`の位置を検査。fallbackは形式維持のため許されるが「解いた」と報告するな。
4. 必要なHDS・`記憶/事前記憶/v0.4`、許可された公開モデル/assetsを**本番の隔離環境に実搭載**し、runtimeで参照した事実をhashつきで保存。
5. 新Notebook版をcommit→run→ログ確認→公式提出（競技枠が許す場合）。`submission_id`とsource buildを紐付け、**数値scoreまたはエラーが確定するまで状態追跡**。

**注意**：初回数値スコアが`0.00`なら「本番経路の成立」は検収してよい。ただし「競技進捗十分」とは宣言せず、直ちに本物の正答生成へ移れ。

## 3. 提出失敗時の必須実装（今回の最重要是正）

現行の提出監視が`API status=COMPLETE`だけで成功扱いするなら修正せよ。下記の状態モデルとテストケースを**実際のKaggle履歴形式に合わせて**実装し、APIの各レイヤ（Notebook run／scoring submission／quota）を分離する。

```text
inspect(submission_id):
    raw = kaggle_fetch_submission_and_notebook_status(submission_id)
    if pending_or_running(raw):
        return IN_PROGRESS
    if terminal_error(raw) or (raw.errorDetails and numeric_score_absent(raw)):
        return TERMINAL_ERROR_NOT_SCORED
    if is_terminal_success(raw) and not raw.errorDetails and numeric_score_present(raw):
        return SCORED_ACCEPTED  # 0.00 も有効な数値
    return UNVERIFIED

on TERMINAL_ERROR_NOT_SCORED:
    preserve_raw_logs_and_submission_id()
    diagnose_root_cause_or_record_unknown()
    fix_the_cause_or_justify_transient_retry()
    limit = query_current_kaggle_submission_limit()
    if limit.allows_submit_now:
        validate_new_notebook_version()
        submit_again_without_waiting_for_next_day()
        continue_until_terminal_result()
    else:
        record_actual_kaggle_denial_and_next_eligible_time()
        continue_local_score_improvement()

on SCORED_ACCEPTED:
    bind_score_to_exact_build()
    preserve_daily_quota_and_final_selection_limits()
    start_next_offline_improvement_cycle()
```

**必須テスト**：

- `COMPLETE + publicScore=null + Notebook Timeout` ⇒ **ERROR／未採点／再提出判断**。
- `ERROR + score=null` ⇒ **ERROR／未採点**。
- `PENDING + score=null` ⇒ **進行中**（同一提出の重複送信禁止）。
- `COMPLETE + publicScore=0.00 + errorDetails空` ⇒ **正常採点、低得点。無条件の同日再送対象にしない**。
- `COMPLETE + publicScore=12.34 + errorDetails空` ⇒ **正常採点**。
- `COMPLETE + score=null + errorDetails空` ⇒ **不明・照会継続**。
- `ERROR後にsubmission quotaが残る` ⇒ **当日再送**。`ERROR後にKaggleが送信拒否` ⇒ 実際の拒否理由を記録し、制限を守る。

**重要**：旧文書や処理が「submitを試みたら日次回数を消費」「`COMPLETE`なら停止」としていれば**v7と矛盾**。この誤分類を必ず修正する。**再提出回数に任意の3回・5回等の固定上限を付けるな**。ただし無修正で永久連打するな。Kaggle側制約、残実行時間、症状の変化を見て合理的に判断する。

## 4. 正答率を上げる開発の主線：候補生成→選別→2試行

**v6の失敗を繰り返すな**：HDSが隠されたtest output観測を要求してHOLDになると、形だけのinputコピーへ落ちる。**これは内部判断の保留としてはよくても、コンペの予測器としては失敗**。

1. **現行失点分類**：公開trainingの未見holdoutを固定し、各test出力で`candidate_missing`, `candidate_invalid`, `correct_candidate_rejected`, `attempts_same`, `HOLD`, `fallback_copy`, `timeout`を記録。真の原因に対する最小修正から着手。
2. **既存HDS／記憶資産**：v0.4.2呼出と事前記憶の一般的規則抽出を保全。HDS候補の一部がHOLDでも、成立済みの他候補まで棄却しない。特定task ID/filename/hashにひもづく答え分岐を実装しない。
3. **汎用候補生成**：物体、色役割、構造関係、D4、コピー・移動・整列、切出し、反復、補完、空間対応の**演算子合成**とtrain全例制約によるプログラム探索を実装。手動で名前だけ違うFamilyを増殖させない。
4. **高得点の現実的選択肢**：Kaggleが許す公開ソルバー、公開事前学習モデル、test-time adaptationの候補を**公式ルール・ライセンス・CPU/GPU実装予算**で受入検査し、実測上有利なものを統合。従来方式を神聖視して勝てる外部資産を検討対象から外すな。反対に公開モデル名だけで採用するな。
   - **具体例を実際に比較**：NVARC 2025公開コードとモデル、ARChitects公開方式、2026の合法なDSL/TTT/公開重み。NVARCの過去公開27.64%は**現行で再現するまで今回の実績ではない**。首位88%級を狙うには、強い複数解法の相補統合・HDS制御による追加利得・限られた計算資源配分の実測が必須。
5. **候補選抜**：train exact・LOO・構造簡潔性・独立支持・推論リスクでrankし、`attempt_1`に最も強い仮説、`attempt_2`に真に相補的な別候補を配置。単純最多票で候補少数派を捨てる影響を検証する。
6. **HDS判断の正当な接続**：仮説採否、計算要求、止め時、実行予算、失敗記憶の更新にHDSを使用。**不確定な出力を暫定行動として出すことと、その正当性を原理として断言することを分離**する。
7. **資源配分**：初期候補を全問で処理したうえで、残GPU/CPU時間を高期待値の難問に振り分け。12時間未満で終了・保存まで保証。強化版によりCPU緊急版を破壊しない。

一つの変更バッチごとに必ず同一データ・同一時間制限の`before/current/delta`を作れ。候補の数が増えても**正解が増えていなければ性能改善ではない**。逆に公開未見で1出力でも真に増えれば、具体的機構と他への影響を確認して次に進め。

## 5. 旧120/167は有限時間で再現調査

1. `ARC2-main-delta-120-167-evidence224.tar.xz`等の**アーカイブ内の根拠・対象データ版・評価器**を突合。hash一致だけでは能力実証にならない。
2. 旧版の一般的なプログラム学習・変換器を抽出し、evaluation solutions・正解表・task IDベース分岐を含まないことを確かめる。
3. 過去のcp932文字コード問題は実行条件として是正し、短いサンプル→一致版全件の順に確認。評価母数167を現行172と混ぜない。
4. **最大4～6時間で有望な移植ルートが見えなければ、この工程を打切り/保留**。本番得点獲得と新汎用エンジンの実装を止めない。過去の美しい記録を取り戻すこと自体が目的ではない。

## 6. 「ラーニングマシン成立」の検証を独立完結させよ

実験条件を**A＝HDS判断なし/記憶なし、B＝HDS判断あり/記憶なし、C＝HDS判断あり/初期記憶あり・更新停止、D＝HDS判断あり/更新あり**とし、同一候補生成器・同一公開training未見holdout・同一seed・同一計算制限で比較する。

- `A→B`は判断・探索制御効果、`B→C`は事前記憶効果、`C→D`は**経験による更新効果**。
- 出力格子の違い、正答増減、採否基準・仮説集合・手続き・失敗署名・記憶の**前後hash**を保存。
- 更新を止めたら差分が消えるか、メモリを消したら差分が消えるか、同一seed再実行で再現するかを確認。
- `HDS.pyをimportした`、記憶を置いた、状態が変わった、ログが増えた、は**実用的学習の実証ではない**。
- 結果が0または悪化なら必ず未実証と表示。失敗原因を次の改善に接続し、証拠なく「原理は成功」と言わない。

## 7. 検収表（すべて実数・版・母数付き）

| 項目 | 必須証拠 | 次へ進む条件 |
|---|---|---|
| 計測 | 公開training未見holdout・evaluationの`tasks/test outputs`、採点器版、data hash | 正解数、HOLD、fallback、time outを嘘なく報告 |
| 生成 | 既存HDS→汎用仮説→test grid の入力・出力・成立条件トレース | inputコピー以外の実格子が生まれ、公開未見で評価できる |
| 採否 | 候補一覧・train一致・選択根拠・distinct 2 attempts | pass@2と試行2独自正解の差分を算出 |
| 学習 | A/B/C/D同一条件比較、状態hash、実出力・正答差分 | 効果が確認できた分だけ成立を主張 |
| 実行 | Kaggleと同等の本番ファイル配置/制限/無ネット/必要assets | 12h未満、全件JSON、落ちない終了経路 |
| 公式 | Notebook version＋source SHA＋submission ID＋エラーなし＋数値score | `SCORED_ACCEPTED`。ERROR/timeout/score nullは未通過 |
| 勝利へ | 前回公式score、最高score、勝利目標との差、次に直す最大ボトルネック | 終了宣言せず実験→改善→提出の次単位に進む |

## 8. Git・操作権限・記録

- **変更対象はARC2の推論・接続・採点・必要なテスト・Notebook梱包・提出制御・実験台帳に限る**。ARC3のファイルに触らない。
- `AGENTS.md`、`制御/現在状態.json`、原理正本・他の保護ファイルは**明示的Owner許可なしで更新しない**。旧版を消さず、v7を新指針として運用ログに参照させる。
- `main`中心、既存変更保全、force push/history rewrite禁止。証拠・失敗履歴を消さない。将来再現可能なcommit/hashに結果を結びつける。
- 外部モデル導入時はライセンス・配布の権利・公開アクセス・Kaggleのnotebook利用資源・オフライン配置とchecksumを確認してから採用。
- **独断の仕様変更・過剰な補助テスト・延々とした監視ループは不要**。重大な目的逸脱、法的/競技規則上の障害、ユーザー権限を要する外部操作のみ具体的に報告し判断を仰ぐ。権限がない操作を勝手に確定しない。
- 出力資料は既存`運用/`に、`run_id,HEAD,入力hash,新旧pass@2, official status/score, retry outcome, next action`を追記。旧v6結果を現在値に上書きしない。

## 9. 作業を止めてよい条件／止めてはいけない条件

**止めてはいけない**：

- 「提出がERRORだが今日の提出は終わり」。**誤り。まず残枠を照会し、送信できれば同日再提出**。
- 「NotebookがCOMPLETE」「private runが成功」「submission.json全件生成」「テスト全部PASS」。**公式スコアではない**。
- 「HDSがHOLDしたので全件inputコピーした」。**正答生成器が未成立**。
- 「公式採点0.00を取ったので成功」。**採点経路は成立、競技力は未達**。
- 「過去120/167が満点なので現在も強い」。**旧版の限定的記録**。
- 「正解なしだが設計資料・Family・ログを増やした」。**改善ではない**。

**正当な停止／Owner照会**：公式APIが実際に提出を拒否して次回合法送信時刻が明らか、明示的な追加権限が必要、競技規則上の不許可、ハード計算資源が不可用、期限到来、Ownerからの停止指示。停止時でも観測した事実・未観測事項・再開条件・次の実験を残す。`PENDING`は停止理由ではない。

## 10. 直近の最初の回答と次行動

**資料を読んだだけで長文計画を返さず、最初の1サイクルを実行せよ。** 最初の報告は以下の7行を必ず実測で埋める。

```text
1. HEAD / 変更済みファイル / 現行の有効なHDS・記憶経路
2. 現行challenge/evaluationの正確な母数とinput版hash
3. 公式提出最新ID/status/errorDetails/score/残枠
4. Timeout原因の観測済み事項・未観測事項・修正した箇所
5. ローカル未見pass@1, pass@2, fallback,HOLD, attempt2寄与
6. 今回のNotebook versionと公式採点結果、ERRORなら同日再送の実行結果
7. 首位へ向けた次の**最大得点増分が期待される実装**と即時実行コマンド
```

**完成判定**：本3点セットの完成はCodexに作業命令が伝わること。**実装の完成**は予測・学習・公式得点の実績でしか判断しない。期限まで最良の採点済み版を保護し、高スコアに向けて局所改善を反復せよ。
