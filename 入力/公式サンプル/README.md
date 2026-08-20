# ARC2公式サンプル

アップロード済み`arc-prize-2026-arc-agi-2.zip`をARC2公式入力の正本として扱うためのmanifestを保持する。

- 圧縮ZIPのSHA-256とサイズを`マニフェスト.json`へ固定する。
- ZIP内部6ファイルのファイル名、サイズ、SHA-256、record数を固定する。
- `入力/公式ソース/ARC-AGI-2`は`arcprize/ARC-AGI-2`の固定commitを参照する。
- 公式ファイル名は外部Kaggle/ARC契約なので英語のまま保持する。

このdirectoryは原入力の証拠面であり、定石・Prior Memory・攻略戦略そのものではない。
