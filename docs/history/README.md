# Historical Assets Index

このdirectoryは、過去のARC2実装・設計・評価・submission資産を削除せず、現在の権威面から分離して扱うためのindexである。

```text
CURRENT
= control/CURRENT_SELECTOR.json が選択する現行文書／state

STABLE OPERATING SURFACE
= AGENTS.md
+ AUTHORITY_ORDER.md
+ docs/operations/

HISTORICAL / LEGACY
= Selectorから選択されない旧文書・旧repository・旧artifact・旧claim
```

HISTORICALは無価値を意味しない。
再利用候補、失敗証拠、設計遷移、teacher evidenceとして利用できる。
ただしcurrent completion／score／strategyへ自動昇格しない。

旧claimを訂正するために当時の記録を書き換えない。必要なら新しいaudit／invalidationを追加する。
