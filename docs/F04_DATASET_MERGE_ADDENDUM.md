# F04 Dataset Merge Addendum — 2026-11-03

## Why the previous report showed 150
The earlier `docs/F04_GOLDEN_SET.md` was written on 2026-10-29 and reported only the Stage53 file
(`review-package/labeled-final.jsonl`, 150 samples). The Stage50 dataset
(`stage51/labeled-final.jsonl`, 232 samples) had not yet been located/considered at that time.
The number 150 reflected only Stage53, not the full available labeled data.

## Input files found
- Stage50: `H:\GIRuntime\labeling\stage51\labeled-final.jsonl`
  - sha256: `58cd0ec7a867fff7473cfa936768f2bc7a25cdfe647c528a03fd6cd26f80b419`
  - dataset_version: `stage50-primary-fulltext-2026-10-20`
  - records: 232 (relevant=true: 231, relevant=false: 1)
- Stage53: `H:\GIRuntime\labeling\review-package\labeled-final.jsonl`
  - sha256: `3c4c91456c5356931811b0660b26ba88868b840bcaf3c2cb00da0d68a61260dd`
  - dataset_version: `stage53-out-of-domain-2026-10-21`
  - records: 150 (relevant=true: 64, relevant=false: 86)

## Validation results
- Both files: 0 parse errors, 0 bad records (relevant is real bool, label_status=valid, label_source=human, state present).
- questions.relevant.instructions identical across both.
- id overlap between sets: 0.
- internal exact-text duplicates: 0 in each set.
- cross-set exact-text duplicates (normalized): 0.
- Counts match expected: total 382, true 295, false 87.

## Merge
- Output: `J:\Documents\GlobalIntelligence\data\labeling\labeled-merged-stage50-stage53.jsonl`
- Output sha256: `d7802af05dc2197674118defc2d579c1538f96037c8247376acc3f8c1f4fafa4`
- Total: 382 (true=295, false=87).
- Original files untouched.
- Per-record dataset_version preserved (provenance retained).

## Harness validation of merged file
- `validate` reports: total=382, valid=382, rejected=0, but status=WAITING_FOR_HUMAN_LABELS
  because "dataset_version is not consistent across records" (two distinct versions).
- This is an expected consequence of preserving per-record provenance; it is not a data-integrity defect.
- Per-dataset validation of each source file passes (Stage50: 232 valid; Stage53: 150 valid).

## F04 readiness
- Count requirement (>=200 labeled, >=50 negatives): SATISFIED (382 total, 87 negatives).
- Kev/Laya runtimes: installed but not running (ports 8123/8124 empty); model evaluation not yet executed.
- LOCAL_SCREENING_ENABLED remains False (no model activated, no threshold tuned).

## Remaining blockers for F04
1. Run Kev and Laya runtimes (startup ~50s / ~94s) and execute screening evaluation against the dataset.
2. Calibrate thresholds on dev split; verify on held-out split.
3. Decide whether to allow mixed dataset_version in harness or evaluate per-dataset.