# ARC2 C2-066 — Compound foreground transform pilot

The public-training pre-screen covered 267 tasks and 1,191 possible LOO folds. The proposed joint D4 foreground transform, bijective color map, and constant translation fit four teacher folds and produced a unique input-only candidate on three folds within one task.

A manifest-seeded reservoir selected one applicable task and one fold for the time-limited pilot. The baseline HDS first answer was a fallback. The compound candidate produced one exact public-training answer:

| Metric | Previous HDS | HDS plus candidate | Delta |
| --- | ---: | ---: | ---: |
| Answer | 0 | 1 | +1 |
| Exact / union exact | 0 | 1 | +1 |
| Wrong | 0 | 0 | 0 |
| Fallback | 1 | 0 | -1 |

No previous exact answer regressed. Baseline solver runtime was 1.795 s; candidate prediction runtime rounded to 0.000 s. This one-fold, one-task result is only a positive pilot signal; it does not establish general capability or justify adoption.

The predeclared gate therefore advances C2-066 to full matched LOO over the 267-task / 1,191-fold population, evaluating every candidate-applicable fold and reusing the unmodified baseline aggregate for folds where the new family cannot apply. No production code, Notebook, or official Kaggle state changed.

Evidence: `P5_HDS_compound_foreground_D4_palette_translation_pilot.json`. Specification: `運用/ARC26-UNIFIED/C2-066_foreground_D4_palette_translation_public_LOO.md`.
