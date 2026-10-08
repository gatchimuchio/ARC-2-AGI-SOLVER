# 提案158: 確定接触による厳密な早期不可能証明

## 変更責任
155の所有view・固定事前・継ぎ目条件を変更せず、探索順序と予算100000も保持する。155が全外周適合配置を完成してから継ぎ目を調べていた処理を、既に配置された二矩形の確定接触に限り前倒しする。153/154/155および155の資源不足試行は変更しない。

## 厳密性
配置済みの完全矩形同士では、共有する辺区間と双方の全画素列が既に確定している。後から第三の矩形を重ねることは元から禁止されており、第三の配置でこの辺区間の画素列が変わることはない。従って「列の完全一致、または片側全枠」の元predicateに違反する二片を含むprefixは、どの完成配置でも不可能である。

前倒し判定は新しく配置する片と既配置片の全接触を検査し、違反した接触の全profile・配置prefix・提案位置を証拠として記録する。それ以外のprefixは切らない。ranking、成功優先、候補数打切り、予算増加、新しい色/寸法/位置priorを追加していない。

探索順、全所有役割、全実行可能完成配置、格子不一致のHOLDは維持する。最後に154のcertify_contactsを再度適用し、全完成配置について元predicateを確認する。資源不足は従来通りRESOURCE_INCOMPLETEで部分出力を返さない。

## 証拠
- 教師2/2完全一致。
- test_parity.pyの22件の完了fixtureで、155と出力・status・生存placementの順序付き全列・実行可能配置数・異なる格子数が一致。
- fixtureは教師D4変換16件、継ぎ目違反、一致、全壁、同値6配置、不一致6配置、複数飽和所有競合を含む。
- 全37件の外周だけを満たす完成proposalについて、最適化された共有辺profile証明が154の全画素描画接触証明と完全一致。継ぎ目違反proposalも含めて照合した。
- 予算1の不足controlはRESOURCE_INCOMPLETE、部分出力なし。

teacher-evidence.jsonとparity-evidence.jsonに保存。

## API・凍結
- propagated_rectangle.fit(teachers) -> (State|None, record)
- propagated_rectangle.predict(state, grid, budget=100000) -> (grid|None, record)
- Stateはfrozen。program名は155と同一。
- SHA256: cf9ca4dc1fe6a4bfb077e09cdf97dc7f5cb27e9f2cf93b2d5363e49b992d72ce

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=candidate142-production-20261007:proposal153-existing-composition-20261007:proposal154-rectangle-seam-composition-20261007:proposal155-touching-rectangle-view-20261007:proposal158-exact-seam-propagation-20261007 python3 proposal158-exact-seam-propagation-20261007/test_parity.py

## 未確認
新規query予測より前に凍結。workerは158のquery予測・target・scorer・公開評価を実行していない。独立入力検証・採否・production統合・回帰は親側の後続工程。core/protected/base source編集、commit、pushなし。
