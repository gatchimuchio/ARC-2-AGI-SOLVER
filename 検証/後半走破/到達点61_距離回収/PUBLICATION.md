# 距離回収・到達点61の公開ファイル

解決rootはrepositoryの `検証/後半走破/到達点61_距離回収/` です。比較.json、checkpoint61.json、学習台帳/、sources/ の全相対pathはこのrootに対して解決します。source_pathを引用元ファイルの親directory相対に解釈しません。

内部memberは evidencearchive-delta-v3.tar.gz の同名virtual path、外部memberは external-references-v2.json のcommit 6a6090cd1b7e7a9043739d928bab5f7f9ae90e4f / repository_path / blobから取得し、sizeとSHA256を検証します。外部repository_pathだけはrepository root相対です。

学習台帳の元67件は既存repositoryの学習台帳/で不変。新しい068 deltaはこのpackage rootの学習台帳/です。runtime5filesの公開先はpublication-files-v3.jsonに明記したrepository root相対pathです。

checkpoint61.jsonはv3 replay完了・独立PASSと回帰0件を追記した現行metadata。旧checkpointはhistory/stage1/checkpoint61.jsonにbyte不変で保持します。過去stage1検証が旧checkpointのSHAを指す場合はこのhistory版で検証します。比較の21項目・82引用は不変です。旧full/v2 archiveはlocalに保持し、再公開しません。
