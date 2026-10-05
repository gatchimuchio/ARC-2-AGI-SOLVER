# 棄却001: 矩形遮蔽viewと既存二軸補完

## 結論

候補は棄却し、productionを開始点60の全328blobへ戻した。受理family追加0、受理primitive追加0、正答課題増分0。新規wrapperを既存67familyへ残していない。

## 観測順序

1. 全120課題359教師をteacher-onlyで検査し、0934a4d8の4教師だけfit
2. 入力のみで一意な全色支持矩形を遮蔽と決め、非遮蔽の元0を含む最大9色を可逆符号化
3. 4教師で13924軸候補を全列挙。raw crop一致22/52/24/54件の交差は一意な絶対反射和31/31
4. その後に既存全有限軌道guardを適用し4教師再現、同一fresh HDS内で4支持・同値採用・隔離0を確認
5. 独立監査、全68回帰script/1112test通過後、codeと条件を固定してquery input-only確認
6. queryは原witnessのない軌道 `[[14,0],[17,0]]` を検出しHOLD。直接候補0、HDS回答0
7. queryに合わせた軸選び直し・guard緩和を行わず棄却

これは固定した入力view/絶対二軸契約の適用境界であり、HDS中核の欠損、現行攻略路線全体の限界、query正解の不可能性を証明したものではない。新しい固定viewをHDSの意味学習へ読み替えない。

## 成功しなかった検査も保持

最初のsynthetic正例fixtureは全教師の遮蔽位置が同じで、20raw共通軸を残した。solverがguard前にHOLDするのは正しく、正例だというfixture仮定が誤りだった。旧20testの4fail/1error、当時のsource、修正内容を保存し、元の曖昧fixtureを明示的な負例として21番目のtestへ追加した。これをsolverの回帰失敗とは分類しない。

## 棄却後の実行手順の失敗と訂正

当初は採点せず棄却した。その後、復旧shellのcwdと相対pathが食い違い、復旧前checkがFileNotFoundErrorとなった。shellが失敗時停止になっておらず、後続の全120採点が候補を残したまま走った。誤った「rollback」ファイル名は原名とSHAを記録した上で、実際の由来である `unintended-candidate-fullscore` へ訂正した。

この意図しない採点の実測は60/120・84/167、delta0、誤格子0、資源失敗0、既存84格子同一。候補棄却は採点前に決定しており変更しなかった。scorer親は通常通り公式test正解を読んだが、子runtimeには渡しておらず、開発文脈にtest正解格子は表示・抽出していない。集計だけを確認した。

修正は絶対path・失敗時停止・archive hash照合を用い、候補3sourceのみを保存後に復旧。独立再検証で、全328baseline blob、全120solver execution、旧scorer全文が開始点と完全一致。67script/1091testが通過した。`判定時系列.json`、`実行手順失敗.json`、archive内の完全command/tracebackを保持し、最初の「採点未実施」と後の実施を区別する。

## 証拠

`凍結候補と全標本.tar.gz` に候補3source、freeze、全teacher/raw/native記録、全回帰、失敗fixture、固定input-only、棄却後の意図しない採点と復旧再採点、完全command、対応表を保存。`全標本manifest.json` で48原ファイルの完全bytesとSHA256を検査できる。候補再現は開始点commit `cc668e34d7ca014daf9f8944767476d56c56fafc` にarchiveのproduction3ファイルを重ねた状態。原freezeの絶対pathはarchive対応表で追跡する。

候補を現在solverへ再接続する指示ではない。queryを見て救済する再試行、vNext開発、HDS中核変更は行っていない。
