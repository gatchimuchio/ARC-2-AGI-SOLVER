# C2-066 HDS同値採用経路の全適合fold監査

観測時刻: 2026-10-24 20:43 UTC  
判断: **不採用**。候補単体の正例はHDS経路で再現せず、1 foldで従来正答をHOLDへ退行させた。

## 仮説と評価範囲

公開trainingの各課題に対し、残る教師例すべてと整合する「前景D4変換・全単射パレット写像・一定平行移動」の複合規則を作り、未見入力から出力候補を生成する。課題識別子、hash、評価正解は実行時に使わない。

公開training全267課題・1,191 foldを事前走査した結果、教師に適合したfoldは4、候補を生成できたfoldは3だった。先の候補単体full LOOでは、影響fold3件でHDS既存出力2/3正答から候補との和集合3/3正答へ増えた。しかし、その候補は既存HDSの教師学習・同値採用・出力格子（同値必須）を通していなかったため、採用判断には使わず、今回の隔離評価へ進めた。

## HDS隔離評価

既存のARC2接続を証拠フォルダ内へ複製し、C2-066教材を一機構として加えたoverlayで、全教師適合fold4件を前回HDSと比較した。held-out outputは両solverの返却後に採点し、証拠には集計値だけを保存した。

| 対象 | previous HDS | C2-066入りHDS | delta |
|---|---:|---:|---:|
| 適合fold 4件の正答 | 3 | 2 | -1 |
| fallback | 1 | 2 | +1 |
| wrong | 0 | 0 | 0 |
| C2-066を最終solver出力として採用 | — | 0/4 | — |

内訳は候補生成可能な3件ではprevious/currentとも2正答・1 fallbackで、改善なし。候補生成不能の1件ではpreviousの正答がcurrentのfallbackへ変わった。HDS教師学習記録ではC2-066が4/4件で全教師再現・同値採用となった一方、テスト照会ではこの未対応入力が「test候補が未確定」となり、HDS接続は採用済み機構の未解決理由がある場合にタスク全体を断定保留にする。別の1件ではC2-066候補がHDS排気で保留され、追加回答にはならなかった。

全1,191 foldの既存baseline 16正答に、全適合fold4件のmatched deltaを反映すると15正答、fallback 1,176、wrong 0となる。残る1,187 foldでは教師適合条件が成立せず、この教材は起動しない。これは既存完全LOOの影響外foldを再利用した導出値で、全1191 foldをHDS overlayで再実行した値ではない。

## 結論

単体候補の正例はHDS同値出力ゲートを通る改善にならず、保守的な未解決処理による退行が発生した。C2-066は不採用とし、production connector、Kaggle notebook、提出物へ移さない。fallbackを正答には数えていない。

## 再現・保全情報

- 集計JSON: C2-066-HDS-admission-final-LOO.json  
  SHA256: 173f630c321be2dcd6764a7e1a2fec4a1d838f562bed9ef40fed15c5eb7f6491
- 候補教材: C2-066_compound_foreground_D4_palette_translation.py  
  SHA256: ae7364556c21bd04d22043138138c054a4a71d0a7a67ba12d2052b15205d4e3b
- HDS隔離runner: P5_HDS_compound_foreground_D4_palette_translation_HDS_admission_LOO.py  
  SHA256: dbe06fc07ba6356f62a1cc7793740f67c488ebbbcc7947f62bbadb2de891325f
- overlay HDS接続SHA256: afc045d0fd4fd2edb9127cf2bc16becb50ec1e52f8b59d3efc09d1d77e0067e7
- 公開training manifest SHA256: 10a0146ab6374f18f44a770b37154ccb6d579fddb9a321eb3bf936666bc85aa8
- 元HDS接続SHA256: d1b31e1c39aac62e99b86a1bbf267725e5306a13f54fced6690e67e133345f55
- プロジェクトvenvでrunnerをpy_compileし、4適合foldの隔離LOOを実行。例外0件。
- Kaggle照会・提出・Notebook変更なし。AGENTS.mdと制御/現在状態.jsonは作業前後で各SHA256不変。
