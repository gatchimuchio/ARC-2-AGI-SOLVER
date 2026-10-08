# Resource diagnosis of rejected candidate175

All eight tasks with official resource failures entered the unconditional constructor peer fit with zero legacy feature models. The frozen predict implementation delegates len(tables) != 1 directly to the original legacy candidate; none of these tasks can consult the peer models. Skipping the unused computation follows that exact pre-existing necessary condition.

Externally instrumented, input-only runtimes used the same 10-CPU-second/512-MiB/60-wall-second limits. No frozen source was edited, no model/teacher filtering was performed, and no official scorer was called during diagnostics. The diagnostic wrapper adds imports and logging and therefore may change time/memory failure type or whether a marginal case finishes. The original score remains the authoritative budget result.

- 0934a4d8: CPU kill while fit was active, first render had begun; original score reported memory limit.
- 4c7dc4dd: MemoryError inside fit after 6 render calls, 492,496 KiB peak RSS; original score reported CPU limit.
- 80a900e0: CPU kill while fit was active; at least 10 render calls had begun; original score reported memory limit.
- 981571dc: MemoryError inside fit after 8 render calls; original score reported CPU limit.
- a251c730: CPU kill while fit was active; at least 90 render calls had begun; original score also reported CPU limit.
- a32d8b75: Diagnostic runtime completed. Unused fit executed all 144 teacher/program render calls, consumed approximately 2.06 user-CPU seconds, and retained zero models. Original score reported CPU limit. This run does not prove the exact kill location in the original run.
- b99e7126: MemoryError inside fit after 15 render calls; original score also reported memory limit.
- d8e07eb2: Diagnostic runtime completed. Unused fit executed all 240 teacher/program render calls, consumed approximately 3.33 user-CPU seconds, and retained zero models. Original score reported CPU limit. This run does not prove the exact kill location in the original run.

Peer render constructs a comparison record for every ordered object pair and each allowed symmetry, and fit retains every render record for all 48 programs and all teachers. This explains the observed constructor memory/time cost without referring to test targets. No optimization of that exhaustive fitting computation is proposed: only deferred evaluation until its existing branch can actually use its result.

See resource-diagnosis/summary.json and per-task stderr/event records for exact CPU, RSS and call counts. See LAZY-FIT-PROPOSAL.md for the proposed branch, cache contract and required independent tests. See rejected-seal.json for frozen-file conservation.
