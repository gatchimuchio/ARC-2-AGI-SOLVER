# NEW167 独立監査

判定: **静的契約・局所検証 PASS。親の凍結 input-only 検証へ進行可。採用・得点改善は未判定。**

目的: 既存 ARC記号命令列 の有限作用拡張について、所有権・失敗保持・全候補一致・資源失敗の契約を確認する。source 編集、統合、評価器実行はしない。

## 凍結・境界

- freeze.json の全 listed SHA256 を開始時と終了時に照合。周期補色局所命令.py は `2549295bf02989c15b86f7154e1993ad8985ef3f8fb1498f429762786b9c7d24`。
- 135 の4 module と比較し、変更は周期補色局所命令.py のみ。131→135 の差分は周期作用の enclosing outer_color binding 2箇所のみで、今回その契約は保持。
- inherited loader の candidate129 wrapper と6 helper は candidate166 の同名ファイルと byte-identical。
- 原 query/payload、非公開解、scorer、denied047 は未読。候補 query render 0。composition の原 script は query payload を読むため実行せず、その constructed 部分のみを独立試験に採用。

## 短い契約証明

1. 原 strict parser は同色 leaf cohort・同寸法・disjoint panel・唯一 blank を要求し、外枠による完全な disjoint pair exact cover を全列挙する。pair-local view も blank/shape から cohort 全体を採り、同 rim 色の pair と異色 enclosing tag を全列挙する。作用の成功で所有権候補を選ばない。
2. strict render に成功、あるいはどれかの role に1個でも retained action があれば、その結果をそのまま返す。従って既存の不一致、失敗した retained target action、空 role と action-bearing role の混在を新作用で救済しない。
3. pair-local view は既存 render が厳密に no_structural_role の時だけ進む。作用なし structural role の失敗も、作用の失敗・不一致も view fallback に進めない。
4. D4 の全10 subgroup を composition table で独立全列挙したうち identity 単独以外9個が inventory に厳密一致。8前変換×9群×2幾何×2端点 = 288 distinct models。identity 単独＋segment は既存 strict inventory が担当。
5. 各 model は全 demonstration の両方向を検査し、全 demo で少なくとも一方向一致する場合だけ保持。target の成否を保持条件に使わない。全 retained model を target に適用し、None を含めて記録する。いずれかの role が作用なし/失敗なら HOLD、それ以外でも全 grid 不一致なら HOLD。
6. wrapper fit は既存命令の complete teacher_input_contract と列挙された structural failure のみで同一 family に接続する。既存 model 有り、incomplete search、未知 failure では接続しない。全教師の正確再現が必要。別 family 登録は追加されない。
7. cover 訪問上限10000は ResourceLimit を投げ、局所 wrapper は例外を握り潰さない。新作用の列挙は有限固定で早期成功打切りなし。外部 runtime の時間制限・全入力 worst-case throughput は今回未計測。

## 実行結果

- `python -B run_inherited.py`: 2 teachers、5 constructed contrasts、3 old-outcome preservation、pair-local periodic positive が PASS。
- その全結果・teacher records・wrapper fit record は135の frozen結果と厳密一致。比較から除いたのは source_sha256 のみ。
- `python -B check_independent.py`: PASS。独立 union/segment 実装と4608 action比較、10 subgroup全列挙、288 action重複なし。
- 新 constructed positive は24 alternatives保持。色衝突と矩形 shape failure でも同一24 alternatives保持。
- 独立生成した all-success target disagreement も24 alternatives を保持したまま complete_grid_disagreement。具体的な synthetic grid/record は independent-result.json に保存。
- fallback guard 7ケース、ResourceLimit 伝播2ケース、binding拒否3ケースを injection で検証。

## 残存範囲

- 本監査は作者の sanitized q1 demonstration の48 retained actionsという主張を再実行していない。許可された教師、継承constructed、独立syntheticのみ使用。
- 実 query q0/q1 の出力、baseline差分、全数回帰、資源benchmark、採用、commit/pushは親の別工程。
- docstring / record.extension の periodic 名は新 orbit action を十分説明しないが、model/witness に orbit_group/segment_model が残るため意味判定への影響なし。非阻害の表示上の古さ。
