# 新規検証済みの復旧候補

previous 76/120課題・107/167正答格子 → current 89/120・124/167。delta +13課題・+17正答格子。元の107正答格子は全て同一、誤出力0、通常公開評価の資源失敗0。data・10 CPU秒・512MiB・60 wall秒・3workersは同一。

外部76 checkpointの完全treeを復元した後、16件のruntime変更を元の完全SHA256へ一致させて回収し、38最終moduleと必要な2接続を合成した。元の066/072/075は未復旧。失われた最高92/127とそのcommit/rawは当時の独立検証事実として記録し、今回のsource・履歴・scoreと区別する。新しい3再構成はこのcommitに含めない。

最初の通常公開評価は88/122でd8e07eb2がCPU停止し、元の2格子を失ったため不採用。入力だけで成立するborder singleton cue不在の必要条件を既存の合同物体出口証明へ追加した。両C4/C8モデルに必要な条件で、全教師を検査し、既存の2×N symbolic slotsで未実行renderを数える。render、モデル空間、HDS、予算は変更しない。教師限定比較は旧10 render/2.732 CPU秒と、新0 render/10 symbolic slotsで保持モデル集合が同一。既存351 checksと失敗した入力の旧2格子一致を確認した。

全回帰は98 script・4542 reported checks。97 current成功recordと、source・依存・data・抽出native helperが同一で変更fitterを実行しない既存全体模様窓のprior29-case成功recordを合成した。直近の同scope24/29資源失敗、最初のcollector schema不一致、最初のCPU scoreは別ファイルで失敗のまま保存する。件数はscope上のreported checksであり、重複のない意味的能力数を表さない。113/117の失われた合成fixture期待値は再現済みと偽らず、今回の小さな普通の確認へ置き換えた。

制御/現在状態と戦略はOwnerの明示許可範囲で事実へ同期。2つの検証manifestから可変status文書を明示的な歴史的provenanceへ移し、全実行source/authority pinを保存した。文書同期後に両既存scriptの255/116 checksが成功した。AGENTS、HDS core、採点器、公式gitlinkは変更しない。

再実行: `python 検証/復旧一括検証.py . /tmp/recovery-regressions.json`。準備map内の古い絶対pathは当時の準備provenanceであり、runnerは現在rootと相対script名を使う。通常採点: `python 検証/ARC2評価.py --mode current --output /tmp/current-official.json`。

この1commitは復旧という1目的でまとめ、各変更の元source pin/系譜はsource-recovery-inventory.jsonに保持する。旧rawや旧commitを作り直したとは主張しない。GitHubへの送信はしていない。
