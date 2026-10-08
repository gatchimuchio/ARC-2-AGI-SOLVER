# 提案155: 接触矩形の二重枠境界による所有分割

## 結果
教師2/2完全一致。コンパクト検査35/35成功。教師の片ごとの全画素集合・固定角・色役割は153と同一。153/154のsourceと証拠を変更していない。

## 許可された入力観測と最初の不足
candidate154-input-only-20261007/payload.json の test[0].input のみを診断した。L標識は正常だったが、C8成分に2個の非矩形連結体があり、153の「物理連結成分=矩形片」が成立しなかった。また全体は矩形の成分にも、二重の単色枠帯の両側に別の色payloadがあった。

新viewのparser診断だけを実行し、1個の構造所有解釈・13個の完全矩形leafを得た。費用13477。診断はinput-parser-diagnostic.jsonに保存。queryの組立・出力予測、target、scorer、公開評価は未実行。sourceはそれらの新規予測より前に凍結した。

## 新しい明示的固定事前
二つの隣接する単色枠帯が接し、その両側に非枠payloadが存在する境界を、物体間境界として飽和するまで切断する。行・列を対称に扱い、全ての許可cut順序が与える全飽和partitionを列挙する。同じ画素所有partitionへの異なるcut順序だけは同一意味として正規化する。

一方が枠だけの切断は許可しない。したがって、教師1にある二重の枠色終端行は新たな物体にしない。幾何所有の資格は全leafが完全矩形であり、全前景画素が標識またはleafに一度だけ所有され、固定角hostが一意であること。無資格のpartitionも、その非矩形leaf等の診断を保存する。資格のあるpartition/roleを組立結果によって落とすことはない。

このsegmentation事前は新規であり、教師から一意に学習されたと主張しない。色番号・座標・寸法・片数・taskルート・答えを保持するparameterはない。

## 既存能力の再利用と責任境界
- 153のC8観測・grid検証・予算・全矩形配置探索を使用。
- 154のcertify_contactsをそのまま使用。継ぎ目条件は変更しない。
- 入力viewのみ拡張したため、残る処理は全幾何proposal、全継ぎ目資格証明、全実行可能格子の合意を要求する。
- 資格のあるownershipの一つでも失敗または不一致ならHOLD。
- parserを含む全段階を同じ予算で計上。枯渇はRESOURCE_INCOMPLETE / complete=falseであり、部分的成功を返さない。

## 証拠
teacher-evidence.json: 教師2件の全証拠。
compact-evidence.json: 35検査。
input-parser-diagnostic.json: 許可された最初の入力の構造診断のみ。

検査は154の25検査に加え、両教師の所有不変、2つの異なる飽和partitionを全保持するsynthetic、双方の完全画素所有、矩形leaf、全切断境界が枠のみであること、全ownership role保持、partition競合のHOLDを含む。2partitionのsyntheticは、同じ6x6枠本体の3隅にpayloadを置き、水平先行と垂直先行で異なるleaf所有を許すもの。

## API・再実行
- touching_rectangle.fit(teachers) -> (State|None, record)
- touching_rectangle.predict(state, grid, budget=100000) -> (grid|None, record)
- Stateはfrozen dataclass、program名のみ。

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=candidate142-production-20261007:proposal153-existing-composition-20261007:proposal154-rectangle-seam-composition-20261007:proposal155-touching-rectangle-view-20261007 python3 proposal155-touching-rectangle-view-20261007/test_compact.py

凍結SHA256: 121d31d0921c9383b769b3b6515aa669259f4aca397c82da70760ba3a6889357

## 採否・未確認
独立監査・新規input-only実行・HDS採否・production統合・回帰・公開評価は親側の後続工程。core/protected authority/base source変更、commit、pushなし。
