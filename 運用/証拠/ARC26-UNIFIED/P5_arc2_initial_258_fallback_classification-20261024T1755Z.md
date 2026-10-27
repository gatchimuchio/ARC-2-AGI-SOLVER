# ARC2 initial official fallback classification

The first scored official submission, 57560705 (Notebook v2), completed with public score 0.00. Its 258 fallback rows reconcile as follows:

- 257 HDS `断定保留` rows, primarily because existing provisional principles lacked sufficient observations. The reason counter also records two unresolved quarantined-principle occurrences; these are overlapping reason occurrences, not extra test rows.
- One `AssemblyIncomplete` exception from the optional sparse-marker assembly path. The exact v2 source exceeded the configured 250000-work cap in `fit_teachers` and did not catch the exception. The later local integration catches it and abstains safely; the v5 runtime diagnostic recorded zero task exceptions.
- One HDS-produced candidate among 259 test examples. Its correctness is unknown and is not counted as a solved item.

This separates a concrete exception path from the larger candidate-coverage/admission gap. The later official v5 score remained 0.00 despite three non-HOLD outputs, and private v8 reduced the fallback count to 254 without changing its output relative to v7; neither output count establishes accuracy.

Related public-training pilots remain non-adopted: C2-054 and C2-057 had zero union-exact delta; C2-056 was an invalid integration and does not falsify its hypothesis. No new generic HDS mechanism has measured improvement. No problem-ID/hash branching or evaluation answers were used.

Evidence: `運用/証拠/ARC26-UNIFIED/P5_arc2_initial_258_fallback_classification-20261024T1755Z.json`
