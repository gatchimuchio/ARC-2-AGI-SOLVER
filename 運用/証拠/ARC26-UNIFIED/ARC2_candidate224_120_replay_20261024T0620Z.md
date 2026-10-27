# ARC2 candidate224 120/167 evidence audit and replay

Observed 2026-10-24 06:20 UTC. This is a P1-2 evidence status update under the current ARC26 v3 instructions.

## Archived run

The 201-part evidence package was reconstructed from its original parts. Its SHA-256 is `6d7e9250e4f9972248e0f2f70fe7ecdcf7518f0fc1fa89df0ca50186318f2991` (19,717,340 bytes); the verifier checked 1,574 payload files and returned PASS.

The archived candidate224 result records 120/120 tasks and 167/167 test examples correct, with no unanswered examples, wrong attempted tasks, or resource failures. It records 95.895 seconds of scorer runtime and a successful, reaped process (96.501 seconds). Conditions recorded: 10 CPU seconds per task, 512 MiB address space, 60-second wall limit, three workers, and `OPENBLAS_NUM_THREADS=1`. The archived result SHA-256 `c5b9efe9f779e50bd479835e8834bb918cbb19cbb918fccd623c0a089b152313` matches the delta record: previous 119/166, current 120/167, delta +1/+1; 166 prior grids identical, one new grid, no lost/changed/wrong grids, and 3,856 frozen pins unchanged.

This confirms that the package contains a coherent historical 120/167 run record. The recorded executable was the Codex runtime at `/opt/codex/.../python`; the package verifier validates its evidence payload and hashes, not a fresh execution.

## Fresh WSL replay

A fresh run used the pinned source commit `ae6be9b70125b1b9f55cbc00a57292ca4211f5c8`, source tree `eea51c2850bbbbe5ea324eec069b43e49babf518`, and public dataset commit `f3283f727488ad98fe575ea6a5ac981e4a188e49`. It used WSL Ubuntu-24.04, Python 3.12.3, NumPy 2.3.5, SciPy 1.17.0, and the same per-task CPU, memory, wall-time, worker-count, and OpenBLAS limits. The runtime worker directory contained no evaluation-solution directory; the parent process used solutions only to score returned predictions.

The replay returned 107/120 tasks and 150/167 examples, with 17 unanswered, zero wrong attempted tasks, and 13 CPU-limit failures, in 236.398 seconds. Raw result SHA-256: `12ddb0d39dbd1a5af2edd57e2eb9f3808fe1a7b801afee20b3a6df8dfbc29552`. The replay used Ubuntu `/usr/bin/python3` and a reconstructed parent harness, not the archived Codex runtime and original runner byte-for-byte.

## P1-2 status

The archive's 120/167 result is now verified as an internally consistent historical record, but independent reproduction remains **HOLD**. The WSL result does not reproduce it and has 13 CPU-limit failures under a different interpreter. This is not evidence that the archived result is false, and it is not a fresh PASS. Keep fallback/HOLD answers unscored. No Kaggle submission was made.

Read-only Kaggle history at 2026-10-24 06:19 UTC still showed submission `57576155` as `COMPLETE`, public score `0.00`; that day's submission slot was already used. Full latest-20 record: `official-history-20261024T0618Z.json`.