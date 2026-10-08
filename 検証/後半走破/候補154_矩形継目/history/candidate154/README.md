# 提案154: 既存矩形組立と継ぎ目連続性の合成

提案153とその証拠を変更せず、継ぎ目条件のみを追加した独立候補。教師2/2完全一致、コンパクト検査25/25成功。production・HDS統合、元query、target、scorer、公開評価は実行していない。

## 教師だけから観測した関係
全矩形片の接触区間について、向かい合う画素列が完全一致するか、一方の全区間が枠色である。教師1は一致する縦方向接触3本と、一方が壁の横方向接触2本。教師2は完全一致4本。

これは追加の明示的な固定事前であり、数値や色番号をfitしたものではない。教師だけでは弱い外周条件と本条件を識別できない。今回の新規programの定義としてのみ提案する。153の解釈を「誤り」と断定したり、教師から必然的に本条件だけが導出されたと主張しない。

## 全提案と全解の保持
153のobserveをそのまま使用し、背景・L標識・矩形片・固定角の構造parserは変更しない。153のassembleで全幾何proposalを列挙し、その全placement記録を消費する。旧候補が複数格子不一致を返した場合も、それを理由にproposalを省略しない。

全proposalの全接触について、双方の画素列、完全一致判定、全壁判定を記録する。追加条件を満たさないproposalは、具体的な入力由来の違反証明を記録したうえで、この新しい制約充足問題の実行可能集合に入れない。成功例だけを保持するrankingや任意枝刈りは行わない。

新制約を満たす全配置の全格子が一致しなければHOLD。構造役割の一つでも解なし・不一致ならHOLD。資源不足はRESOURCE_INCOMPLETE / complete=falseで途中解を返さない。

## API・固定依存
- seam_rectangle.fit(teachers) -> (State|None, record)
- seam_rectangle.predict(state, grid, budget=100000) -> (grid|None, record)
- Stateはfrozen、program名だけを保持。fitted_parametersは空。
- seam_rectangle.py SHA256: 1e7d97da06e3c72808147c0e6e4fedd0956798733dfd3f605954695836f6d0c4
- 153 anchored_rectangle.py SHA256: 3b25da045f96cb799a4d84c0c4159fd3b39e34214212f72936ea5b87940e4ad7

実行:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=candidate142-production-20261007:proposal153-existing-composition-20261007:proposal154-rectangle-seam-composition-20261007 python3 proposal154-rectangle-seam-composition-20261007/test_compact.py

## コンパクト証拠
teacher-evidence.jsonに両教師の全接触profileを保存。compact-evidence.jsonに25検査を保存。

教師D4共変性16件、palette置換2件、独立した外周正常・継ぎ目違反例、独立した一致例、全壁例、継ぎ目条件をすべて満たす6通りの格子不一致を全保持してHOLDする例、同値6通りを全保持する例、資源不足、parser不変を検査した。

## 未解決
構造役割が得られない入力には対応しない。今回の教師からはそのparserを拡張する独立証拠を得ていない。入力検証と採否は親側で別途実施する。core・protected authority・base sourceの変更、commit・pushなし。
