# NEW066 門・完全経路の新規再構成

前回89/124 → 今回90/125、+1課題/+1格子。2b83f449のquery0を追加し、元124格子は全て同一、誤出力0、通常資源失敗0。同じ120課題/167例と10CPU秒/512MiB/60wall秒/3workers。

失われた旧066 sourceの復元ではなく、教師と既存D4・成分・距離・prepared移動primitiveから新たに再構成した。全24役割×8D4×4方向を教師適合し、全保持モデルの完全格子合意を要求する。旧距離fitter/predict関数は不変。方向への広がりがない平坦経路は動かさない。最初の教師不適合と修正前sourceは別の再構成workspaceに保存する。

教師2件と既存22対照、input-only、同じfamilyのHDS current2/prior0を確認。全回帰は98 current成功recordと、変更distance moduleを実行しない同一window scopeのprior29-case成功recordで99scripts/4564reported checks。中断により外側tool終端は取得不能だが、98子processのexit0とcomplete reportは永続化済み。通常採点PID6はexit0/reaped。

基底ece0dc7a。HDS core/authority/採点器/公式gitlinkは不変。これはpublic条件での実測であり、旧92commit/raw復旧やhidden一般化は主張しない。新072/075は未採用。
