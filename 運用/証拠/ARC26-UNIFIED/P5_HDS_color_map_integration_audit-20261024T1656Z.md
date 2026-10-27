# C2-056 integration audit

Observed 2026-10-24 16:56 UTC after reviewing the HDS inference contract.

C2-056 created one HDS engine per source color. In HDS v0.4.2, deterministic relation discovery requires at least two distinct condition values (`推論.py`, `_決定的対応候補`, `len(条件種類) >= 2`). A per-color engine sees only one `input_color` condition value, so it cannot learn the intended relation. This explains the five color queries without a unique prediction.

The measured C2-056 implementation still produced no candidate, but this result does **not** falsify the task-wide color-map hypothesis. The previous report's “stop this hypothesis” decision is superseded by this audit; retain the pilot metrics as an implementation result only. No production artifact changed.

A synthetic-only check using one shared HDS engine and two distinct input-color conditions returned unique mappings for both colors with no request, conflict, or quarantine. This verifies the basic engine contract, not ARC capability.

Next action: a separate C2-057 four-task public-training LOO pilot will use one shared task-wide HDS engine so its condition set can contain multiple colors. It will retain teacher-only training, full-grid exact scoring after return, fallback-as-incorrect, and the five-minute stop rule. Expand only if exact improvement is observed.
