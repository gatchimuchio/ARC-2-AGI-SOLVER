# 候補189: 凡例stampの部分所有と非干渉保存

状態: pure候補凍結。全4教師fit、input-only候補1、targeted128 PASS。公式採点/native/full回帰/採用/commit/uploadは未実施。105/148からの性能増分は未確認。runtime、HDS中核、Gateは一切変更していない。

## 既存能力と最初のgap

- 旧 `arc2-restored-592d2c5-audit/keyed_stamp_probe.py` が現存。コピーのSHAはfreezeに記録。C8同色glyph、bbox端の空/実セルanchor、外向き二色code（近=value、遠=key）、全色role列挙、同時clipped stampをそのまま再利用。
- 旧完全所有は全教師fitするがquery全56色role列挙で0、描画前HOLD。shape=8/background=0のroleで唯一不成立なのは、残るforegroundがすべて既知keyである条件。旧失敗はlegacy-report.jsonに保存。
- この条件だけ緩和すると教師2/queryとも6roleで識別失敗。partial-report.jsonに全raw/失敗を保存し、成功roleだけを拾っていない。
- 127/128と呼ばれる旧候補の完全sourceは限定検索では未発見。旧初期probeの再利用と区別し、127/128の復元とは主張しない。

## 最小合成と明示prior

1. 部分所有: 外部foregroundには既知keyの対象セルと未指示の受動セルを分ける。glyph全成分が一意なraw codeを持つこと、glyph/key/valueのdisjoint所有、key一意性、bbox内の他foreground禁止など旧条件は保持。
2. 背景識別: 現行 `接続/ARC2/凡例矩形教材.py` のunique-mode認識、および同じCounter/C4で表現する外周modeと最大C4地を比較。全4教師でfitした3モデルを全保持。queryでは3モデルとも背景0/glyph8で一致。全6raw role自体は記録に残し、背景制約で描画前に選別する。教師/queryともモード・外周・最大C4の1位は一意。
3. 非干渉: 現行 `接続/ARC2/標識軸転写候補.py:render_assignment` の入力copy、所有sourceだけ消費、foreign overlap拒否という作用を合成。未指示セルを保存し、そこへの異色stampはHOLD。queryの未指示点は7セル（6色の点6個、1色の点1個）。
4. 凡例の出力色が別凡例のkeyでも入力から同時に読む。queryの2→4→1を連鎖実行する新解釈は採用しない。教師には2↔4、6↔7および1↔2の循環があり、逐次書換は既存の同時作用と異なる。

これらの背景・未指示セル保存は教師と整合する追加priorであり、教師から論理的に唯一の規則とは主張しない。特に未指示セルを消す対案も全教師fitし、queryでは保存案と7セル違う。全3背景モデルの消去出力と差分を alternatives-hold.json に保持。消去案は反証されておらず、非干渉priorを採用した別語彙のHOLD候補である。

## 凍結物

- `keyed_stamp_kernel.py`: 標準ライブラリのみのpure kernel。`fit_teachers(pairs)` と `predict(grid, model)`。modelはkind/version/背景ルール名のみで教師格子やquery答えを含まない。
- `legacy-to-kernel.diff`: 現存旧probeからの全差分。C8/bbox/codeの幾何条件は維持。partial所有、描画前背景制約、passive保存/競合判定、全教師fitと全保持モデルconsensusだけを追加。旧probeの広範な例外HOLD化は削除しruntime例外を伝播。
- `freeze.json`: SHAと範囲。
- `kernel-report.json`: 全教師全候補診断、input-only予測、全raw role。
- `targeted-report.json`: 128検査。教師再現、D4全8、12色置換、非破壊、invalid、部分所有、passive異色衝突HOLD、同色重なり、消去対案、保持model失敗/不一致HOLD、runtime例外伝播。

HDSへの接続は未実施。3モデルの一つでも失敗した場合や出力が異なる場合はpredictがHOLDし、成功subsetへ縮小しない。
