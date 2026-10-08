# 提案159: payload色ごとの全体C4連結性

## 教師由来の観測
教師1の非枠payload 0色は2成分から1成分へ（15画素保存）、2色は3成分から1成分へ（12画素保存）。教師2の9色は4成分から1成分へ（13画素保存）。役割色は153の入力parserから導出した。詳細はteacher-relation-evidence.json。

## 最小追加と新規事前
158の全ての完成済み継ぎ目適格配置に対して、各非枠payload色がちょうど1個のC4連結成分であり、入力片に含まれる全色の画素数が保存されることを要求する。accepted primitive「既存標識組立.same_color_components」を再利用する。

これは明示的な新しい固定事前であり、教師から一意に導かれたruleとは主張しない。色番号・寸法・位置・答え等のfitted parameterはない。

入力view、所有partition列挙、確定接触の厳密不可能証明、継ぎ目条件、全所有役割保持、予算100000は158から変更しない。

## 全解と全証明の保持
全ての完成済み継ぎ目適格配置について、各色のsource/rendered pixel数、全C4成分の画素集合・サイズ・個数、画素保存判定を記録する。不適格配置の具体的証明も残す。全体条件を満たす配置を全保持し、その全出力が一致した場合だけ返す。

一つの所有役割でも適格配置なし・格子不一致ならHOLD。資源不足はRESOURCE_INCOMPLETE / complete=false。途中までの適格配置だけから返さない。

C4 helperには完全組立矩形のtight cropを渡す。外側背景を省いても内部payloadのC4接続は変わらないため、これは同じpredicateの等価計算である。全画素保存を先に検査する。

## 証拠
- 教師2/2完全一致（teacher-evidence.json）。
- 独立syntheticの同色中心点4個が分離する例: 6個の全完成配置を調べ、全てに4成分である証明を残して棄却。
- 独立syntheticの異なる4色の中心点を持つ例: 各色1成分となる6個の配置を全保持し、6個の異なる格子のためHOLD。
- 予算1controlはRESOURCE_INCOMPLETE、出力なし。

compact-evidence.json、test_compact.pyに保存。

## API・凍結
- global_rectangle.fit(teachers) -> (State|None, record)
- global_rectangle.predict(state, grid, budget=100000) -> (grid|None, record)
- frozen Stateはprogram名だけを保持。
- SHA256: 028f4f509a302b514bc3556ea0aae2c46a747ca4cae71a85bf2a398deafb35fb

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=candidate142-production-20261007:proposal153-existing-composition-20261007:proposal154-rectangle-seam-composition-20261007:proposal155-touching-rectangle-view-20261007:proposal158-exact-seam-propagation-20261007:proposal159-global-rectangle-relation-20261007 python3 proposal159-global-rectangle-relation-20261007/test_compact.py

## 未確認・禁止範囲
このrevisionでは教師と独立syntheticだけを観測した。query配置・query出力・target・scorerを読んでいない。新規query予測前にsourceを凍結。独立入力検証・採否・production統合・回帰は未実行で親側の後続工程。153/154/155/158、core、protected authority、base sourceは変更していない。commit・pushなし。
