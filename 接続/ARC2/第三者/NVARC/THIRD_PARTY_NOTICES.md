# Third-Party Notices

This dataset bundles source needed for offline ARC Prize evaluation.

## Tiny Recursive Models

- Project: SamsungSAILMontreal/TinyRecursiveModels
- Source: https://github.com/SamsungSAILMontreal/TinyRecursiveModels
- Commit: e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9
- License: MIT
- Bundled license: `third_party/TinyRecursiveModels/LICENSE`

The runtime applies small, documented compatibility changes in a temporary
working copy: disable Weights & Biases, use the offline Adam-atan2 package, and
write evaluation artifacts locally. The upstream files in this dataset remain
unchanged.

## Icecuber ARC Solution

- Project: top-quarks/ARC-solution
- Source: https://github.com/top-quarks/ARC-solution
- Commit: 9407072659de1270358c2ba34c527785214dd68b
- License: MIT
- Bundled license: `third_party/icecuber/LICENSE`

`src/runner.cpp` accepts environment variables for the challenge directory and
evaluation mode. That narrow adaptation lets the original solver process the
2026 hidden task file without bundling any task answers.

## TRM Checkpoint

The notebook expects the public `cpmpml/arc-prize-trm-031` Kaggle dataset. Its
Kaggle metadata declares CC0: Public Domain. The checkpoint is attached as a
separate input and is not redistributed in this source dataset.

## Offline Python Wheels

The `wheels` directory contains unmodified PyPI distributions for Hydra Core,
OmegaConf, antlr4-python3-runtime, adam-atan2-pytorch, argdantic, coolname,
pydantic-settings, and python-dotenv. Their package metadata and license files
remain inside each wheel.
