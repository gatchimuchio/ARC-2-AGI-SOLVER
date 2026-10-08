# 候補200: 小物体優先と元位置順の条件付き合成

状態: PURE_READY_NOT_ADOPTED。基底112課題/157格子、公式増分未検証。正本変更なし。

開始前に目的指示書全文、AGENTS、権限順序、現在状態、戦略を確認し、結果報告後の続行前に原文全文を再読。全3教師入出力と両query入力を既存proposal184のobservations.pngで実見し、指定teachers-only/input-onlyをpure実行で再観測。公式query正解、hidden、solutions、native、scorerは未使用。

## 最初の不足と既存能力

元126核と129部分key-viewの完全sourceは現存し、184freezeの両SHAに一致する。このfamilyに必要な旧sourceは未回収ではない。元92commit/raw等の全体履歴未復旧については今回回収したとは主張しない。

旧4programは全3教師を説明し、query0は全一致、query1はsmall_firstの等セル数競合でHOLD。新規コピー同士の競合点(6,12)は背景。両物体のC8連結性は端点を1個除いても残るため、連結性だけでは順位は決まらない。C4分割では対角線の個別中心転写が形を破壊する。元位置のセル所有保護として解ける競合でもない。

最初の不足は物体認識ではなく、同数の小物体優先に未定義な所有順位。親指定の追加priorをPRIOR.mdへ定義してから候補検証した。セル数優先を変えず、同数時だけ既存source_firstの元bbox辞書順を副キーに合成する。教師から論理的に一意な規則とは主張しない。サイズ範囲・色ID・filename・hash・固定答えは選択に使わない。

## 最小変更

変更対象は対辺標点配置核.pyのactのみ。元actを_actとして保持し、公開actは元実行が成功した場合、その全返却tupleをそのまま返す。失敗理由がequal_priority_color_conflictだけ、かつsmall_firstの場合のみ既存source_first副キーで再実行する。他制御、別failureや混合failure、例外は元のまま。拡張自体の失敗/例外も伝播する。

旧保持4programを一つも捨てず、全role・program成功および完全格子一致を維持。HDS・教材・登録・全体gateは変更なし。候補.pyは依存確認用のbyte-identical copy。

## pure結果

- 全教師fitの保持4program集合・fit全記録が旧と完全同一
- 全3教師のconsensus全tupleが旧と一致し教師再現
- query0全tupleが旧と完全一致
- query1は4program×2frame役割が全成功・全出力一致。競合点はmagenta(6)。入力の元bbox順による結果で正解照会なし
- synthetic 300 role×8program=2400 action比較で旧成功の全tuple保持、他制御/他failure全tuple保持
- query1は4回転・9循環色置換で等変
- 候補全件のfailure、不一致、例外伝播、拡張境界の混合失敗保持を検査

OPENBLAS_NUM_THREADS=1、CPU10秒、512MiB、wall60秒。HiGHSは未使用で既存threads=1設定を変更しない。実行方法はcheck_candidate.pyの3引数にsource/teachers-only/input-onlyを指定。candidate-result.jsonに入力のみからの候補出力と全role記録を保存。

初回audit_ownership.pyは集合のJSON直列化で失敗。cellsをsortしたlistへ直して再実行PASS。solver失敗とは区別する。候補初期draftはrank変更を直接行ってpure通過したが、混合failureの全tuple維持のため最終版を旧act先行・等数単独失敗のみ再実行へ限定し再検証した。初期draftを採用していない。

## 未実施と受渡し

native/HDS統合、全体回帰、公式評価、採用、commit、upload、remote操作は未実施。性能改善はまだ主張しない。親は凍結kernelのみを独立監査し、旧回帰のfrozen126 SHA pinを無根拠に変更せず新旧契約を別検証する必要がある。現行旧基底と過去184HOLDは保持したまま。
