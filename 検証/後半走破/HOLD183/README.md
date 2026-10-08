# 候補183: 支持control再観測

状態: HOLD。新しいruntime変更・凍結予測はなし。正本は無変更。

原指示書全文、AGENTS.md、権限順序、現在状態、戦略を照合。最上位目的120/120、現行102/144と残18を保持。全5教師と両query入力をobserved.pngで実見した。

既存familyは教師5件すべて再現し、query0成立、query1は異色2セルcontrolがsingleton候補に入らずraw_cue_floor_not_unique。入力のpost/beam分解、潜在末端、元のendpoint支持、下方接触、描画を追跡した。173保存patchを読み、全controlセルの再描画が実装済みであることを確認した。

既存単色除去→沈降を赤→青と青→赤の各順で合成し、各段を既存parserで再認識した。両順とも全段成立、control以外の最終盤面は173の同時和集合と完全一致。順序合成だけでは新しい予測にならない。潜在長・支持・最終形状検査からも、今回の実入力で別の出力を正当化する具体的不整合は特定できなかった。

170のpalette関係は教師だけで識別不能、173は教師・回帰を通したが公式新規誤答1で棄却された、という履歴を保持する。誤答情報だけを根拠に別のcontrol解釈へ切り替えていない。HDS v0.4.2とglobal gateは無変更。query正解、solutions、scorer、denied047を未読。公式採点・native統合・採用・commit・push・uploadを実行していない。

最小再検証はresult.json。今回の結果は正答増分ではない。
