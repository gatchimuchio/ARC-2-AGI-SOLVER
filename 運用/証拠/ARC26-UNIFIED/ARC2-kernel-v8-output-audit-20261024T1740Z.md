# ARC2 private kernel v8 output audit

Kernel v8 completed as a private Kaggle notebook execution. The deterministic cell id removed the prior `MissingIDFieldWarning`; the run log contains no traceback, exception, or error marker.

The output has 240 tasks and 259 test examples. All examples have two syntactically valid grids. The audit records 254 `solver_hold` fallbacks and zero distinct second attempts. Runtime was 343.718 seconds.

The `submission.json` bytes are identical to v7 (SHA-256 `c34dcdd39e1afacba8c2fe992ffd93378c92bbbde3885a58f43f3fd02253bcb2`); runtime changed by -0.045 seconds. This establishes a notebook format compatibility fix only; it does not establish solver accuracy. HOLD fallbacks are not counted correct.

This was a private kernel execution, not an official competition submission. No public score is attributed to this run.

Evidence: `運用/証拠/ARC26-UNIFIED/ARC2-kernel-v8-output-audit-20261024T1740Z.json`
