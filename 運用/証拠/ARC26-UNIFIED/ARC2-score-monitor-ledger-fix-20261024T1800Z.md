# ARC2 score monitor ledger write repair

The legacy monitor recorded a successful official status query only in its restart checkpoint. It did not add the observation to the shared score/work ledgers or write a new evidence artifact. The monitor now saves the full read-only history rows, hashes the snapshot, appends both ledgers, and links the checkpoint to that evidence. Query errors are recorded without credential data.

Targeted monitor tests: **5 passed**. The 2026-10-24 17:43 UTC status observation was backfilled with an explicit limitation: the legacy tick returned the unchanged latest ID/status/score but did not retain a refreshed full history list, so the previous full snapshot is referenced and `history_unchanged` remains unknown.

The next live monitor tick is due at 18:43:51 UTC; the patched live path has not run yet. No official submission or rerun was performed.

Evidence: `運用/証拠/ARC26-UNIFIED/ARC2-score-monitor-ledger-fix-20261024T1800Z.json`
