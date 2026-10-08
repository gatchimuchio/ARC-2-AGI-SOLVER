# 候補121 計数色層旋回

同条件公開120課題/167例で92/127→93/128、+1課題/+1格子。6ffbe589 query0を追加し、127旧格子は全て同一。誤出力0、通常資源失敗0。

既存のbbox・crop・C4成分・色mask・D4変換を再利用した。新しいscene priorは、少なくとも一色が四辺に届く共通正方形canvasと、canvas外の同色の直線C4成分を回数cueとして完全に所有すること。cueのない色は恒等、異色maskの重なりはHOLD。背景・正方形・cueの全適格解釈を保持し、全8個の反復D4 programを全教師で評価する。保持programや解釈の失敗・不一致はHOLD、例外は伝播する。

3教師369cells、6普通の確認群、input-only13×13、HDS current3/prior0を確認。既存familyにはこのscene/action契約がなかったため、ARC計数色層旋回を空のpriorで接続した。HDS学習・支持・同値・隔離・最終family合意・coreは変更していない。

全回帰は101個の今回の成功processと、変更を使用しない同一window scopeの保存済み29-case recordで102script/4588reported checks。既存の失敗したwindow再試行をPASSに改変せず、元の完全成功recordを明示的に再利用した。

基底9c1075bae28da663a10e72943d32d289a14b8dd2。今回のsource/runtimeは新規の検証結果。失われた旧92commit/rawの復旧は主張しない。新grammarの設計priorと教師による適合は区別する。候補118/122の誤出力を含む不採用記録は別の保存済みevidenceに保持し、今回へ混入していない。
