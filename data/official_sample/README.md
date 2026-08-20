# ARC Prize 2026 ARC-AGI-2 Official Sample

このdirectoryは、ユーザーがアップロードしたKaggle公式サンプル
`arc-prize-2026-arc-agi-2.zip` の6 JSONファイルを保持するための正規配置場所です。

## Provenance

- Uploaded archive SHA-256:
  `d00746ef4e06a515ad53bde4dff276dc8ef5a26829a0ebeafc8cf8ba6371abaa`
- Canonical ARC-AGI-2 source:
  `arcprize/ARC-AGI-2`
- Pinned source commit:
  `f3283f727488ad98fe575ea6a5ac981e4a188e49`
- Verification manifest:
  `MANIFEST.json`

ファイルは公式ARC-AGI-2 task sourceからKaggle形式へ再生成し、アップロードZIP内の各ファイルと**byte size / SHA-256が完全一致した場合だけ**commitされます。

## Files

- `arc-agi_training_challenges.json` — 1000 tasks
- `arc-agi_training_solutions.json` — 1000 solutions
- `arc-agi_evaluation_challenges.json` — 120 tasks
- `arc-agi_evaluation_solutions.json` — 120 solutions
- `arc-agi_test_challenges.json` — Kaggle local placeholder 240 tasks
- `sample_submission.json` — placeholder submission format

`arc-agi_test_challenges.json`はローカルで見えるplaceholderであり、Kaggleの正式rerun時にはhidden test tasksへ差し替えられる境界として扱います。

## Sync

```bash
python3 scripts/sync_official_sample.py \
  --source /path/to/ARC-AGI-2 \
  --output data/official_sample
```

通常は`.github/workflows/repository-guard.yml`が固定公式commitから生成・照合します。
