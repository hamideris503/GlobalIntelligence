"""Focused offline tests for the Stage 48 human-labeling workflow."""
from __future__ import annotations

import json
from pathlib import Path

from backend.ai.evaluation.local_screening import (
    BUNDLE_MANIFEST,
    BUNDLE_SAMPLES,
    MIN_LABELED_SAMPLES,
    dataset_fingerprint,
    main,
    merge_bundle,
    prepare_bundle,
    validate_bundle,
    validate_records,
)
from backend.ai.local_screening import (
    QUESTION_ID,
    SCOPE_RULE_VERSION,
    SCREENING_QUESTIONS_V2,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def _samples(count: int) -> list[dict]:
    return [
        {"id": f"sample-{i:04d}", "state": f"article text {i}"}
        for i in range(count)
    ]


def _label(
    sample_id: str,
    value: bool = True,
    *,
    annotator: str = "alice",
    source: str = "human",
    status: str = "valid",
) -> dict:
    row = {
        "id": sample_id,
        "annotator": annotator,
        "label_source": source,
        "label_status": status,
    }
    if status == "valid":
        row["labels"] = {QUESTION_ID: value}
    return row


def _labeled(count: int) -> list[dict]:
    return [
        {
            "id": f"sample-{i:04d}",
            "state": f"article text {i}",
            "labels": {QUESTION_ID: i % 2 == 0},
            "annotator": "alice",
            "label_source": "human",
            "label_status": "valid",
            "dataset_version": "test-v1",
        }
        for i in range(count)
    ]


def _prepare(tmp_path: Path, records: list[dict], name: str = "bundle"):
    source = tmp_path / f"{name}-input.jsonl"
    _write_jsonl(source, records)
    return prepare_bundle(source, tmp_path / name)


def test_prepare_missing_empty_and_malformed_input(tmp_path, capsys) -> None:
    missing = tmp_path / "missing.jsonl"
    assert main([
        "prepare", "--input", str(missing), "--out-dir", str(tmp_path / "missing"),
    ]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "ERROR"

    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    result = prepare_bundle(empty, tmp_path / "empty-bundle")
    assert result.status == "WAITING_FOR_INPUT_DATA"
    assert result.total == 0
    assert not (tmp_path / "empty-bundle" / BUNDLE_MANIFEST).exists()

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text('{"id": "x", "state": "text"}\nnot-json\n', encoding="utf-8")
    result = prepare_bundle(malformed, tmp_path / "malformed-bundle")
    assert result.status == "INVALID_INPUT"
    assert any("invalid JSON" in error for error in result.errors)


def test_prepare_creates_blind_pending_bundle_reproducibly(tmp_path) -> None:
    result = _prepare(tmp_path, _samples(3))
    assert result.status == "READY_FOR_LABELING"
    assert result.valid == 3
    assert result.rejected == 0

    samples = [
        json.loads(line)
        for line in (tmp_path / "bundle" / BUNDLE_SAMPLES).read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert [sample["id"] for sample in samples] == [
        "sample-0000", "sample-0001", "sample-0002",
    ]
    assert all(set(sample) == {"id", "state", "label_status"} for sample in samples)
    assert all(sample["label_status"] == "pending" for sample in samples)
    assert all("labels" not in sample for sample in samples)

    manifest = json.loads(
        (tmp_path / "bundle" / BUNDLE_MANIFEST).read_text(encoding="utf-8")
    )
    assert manifest["question_id"] == QUESTION_ID
    assert manifest["dataset_version"] == result.dataset_version
    assert manifest["samples_sha256"] == result.samples_sha256
    assert manifest["bundle_sha256"] == result.bundle_sha256
    assert validate_bundle(tmp_path / "bundle").valid

    before = {
        path.name: path.read_bytes()
        for path in (tmp_path / "bundle").iterdir()
    }
    assert _prepare(tmp_path, _samples(3)).status == "READY_FOR_LABELING"
    after = {
        path.name: path.read_bytes()
        for path in (tmp_path / "bundle").iterdir()
    }
    assert before == after


def test_bundle_and_merge_record_the_scope_rule_version(tmp_path) -> None:
    _prepare(tmp_path, _samples(1))
    manifest = json.loads(
        (tmp_path / "bundle" / BUNDLE_MANIFEST).read_text(encoding="utf-8")
    )
    assert manifest["scope_rule_version"] == SCOPE_RULE_VERSION
    assert manifest["question"] == SCREENING_QUESTIONS_V2[QUESTION_ID]

    labels = tmp_path / "labels.jsonl"
    _write_jsonl(labels, [_label("sample-0000", False)])
    out = tmp_path / "merged.jsonl"
    assert merge_bundle(tmp_path / "bundle", labels, out).merged == 1
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["questions"] == SCREENING_QUESTIONS_V2
    assert row["scope_rule_version"] == SCOPE_RULE_VERSION


def test_prepare_rejects_existing_labels_and_duplicates(tmp_path) -> None:
    source = tmp_path / "predicted.jsonl"
    _write_jsonl(source, [
        {"id": "a", "state": "text a", "labels": {QUESTION_ID: True}},
    ])
    result = prepare_bundle(source, tmp_path / "predicted-bundle")
    assert result.status == "INVALID_INPUT"
    assert any("non-blind field: labels" in error for error in result.errors)

    duplicate = _samples(3)
    duplicate[1]["id"] = duplicate[0]["id"]
    duplicate[2]["state"] = duplicate[0]["state"]
    result = _prepare(tmp_path, duplicate, "duplicate")
    assert result.status == "INVALID_INPUT"
    assert result.duplicates == 2
    assert any("duplicate id" in error for error in result.errors)
    assert any("duplicate state" in error for error in result.errors)


def test_merge_matches_ids_and_rejects_unknown_ids(tmp_path) -> None:
    _prepare(tmp_path, _samples(2))
    labels = tmp_path / "labels.jsonl"
    _write_jsonl(labels, [
        _label("sample-0001", False),
        _label("sample-0000", True),
        _label("unknown-id", True),
    ])
    out = tmp_path / "merged.jsonl"
    result = merge_bundle(tmp_path / "bundle", labels, out)
    assert result.status == "WAITING_FOR_HUMAN_LABELS"
    assert result.merged == 2
    assert result.unknown_ids == 1
    assert result.labels_sha256

    merged = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in merged] == ["sample-0000", "sample-0001"]
    assert merged[0]["labels"] == {QUESTION_ID: True}
    assert merged[1]["labels"] == {QUESTION_ID: False}
    assert all(row["label_source"] == "human" for row in merged)


def test_merge_does_not_accept_bad_provenance_or_pending(tmp_path) -> None:
    _prepare(tmp_path, _samples(4))
    labels = tmp_path / "labels.jsonl"
    _write_jsonl(labels, [
        _label("sample-0000", True),
        _label("sample-0001", status="pending"),
        _label("sample-0002", source="kev"),
        {"id": "sample-0003", "labels": {QUESTION_ID: "yes"},
         "annotator": "alice", "label_source": "human",
         "label_status": "valid"},
        {"labels": {QUESTION_ID: True}, "annotator": "alice",
         "label_source": "human", "label_status": "valid"},
    ])
    result = merge_bundle(tmp_path / "bundle", labels, tmp_path / "merged.jsonl")
    assert result.merged == 1
    assert result.pending_labels == 1
    assert result.rejected_labels == 3
    assert result.pending_samples == 3
    assert any("id is required" in error for error in result.errors)
    assert any("label_source" in error for error in result.errors)
    assert any("boolean" in error for error in result.errors)


def test_threshold_counts_only_valid_samples() -> None:
    short = validate_records(_labeled(MIN_LABELED_SAMPLES - 1))
    assert not short.valid
    assert short.valid_samples == MIN_LABELED_SAMPLES - 1
    assert short.human_labels == MIN_LABELED_SAMPLES - 1

    exact = validate_records(_labeled(MIN_LABELED_SAMPLES))
    assert exact.valid
    assert exact.valid_samples == MIN_LABELED_SAMPLES

    extra = _labeled(MIN_LABELED_SAMPLES + 1)
    extra[-1]["labels"] = {QUESTION_ID: "yes"}
    check = validate_records(extra)
    assert not check.valid
    assert check.total == MIN_LABELED_SAMPLES + 1
    assert check.valid_samples == MIN_LABELED_SAMPLES
    assert check.human_labels == MIN_LABELED_SAMPLES
    assert check.rejected == 1


def test_dataset_hashes_are_stable_and_change_with_data(tmp_path) -> None:
    first = _samples(2)
    second = [dict(record) for record in first]
    assert dataset_fingerprint(first) == dataset_fingerprint(second)

    result = _prepare(tmp_path, first, "one")
    assert _prepare(tmp_path, second, "two").samples_sha256 == result.samples_sha256

    changed = [dict(record) for record in first]
    changed[0]["state"] = "a genuinely different article"
    changed_result = _prepare(tmp_path, changed, "changed")
    assert changed_result.samples_sha256 != result.samples_sha256


def test_bundle_validation_detects_tampering(tmp_path) -> None:
    _prepare(tmp_path, _samples(2))
    samples_path = tmp_path / "bundle" / BUNDLE_SAMPLES
    samples = [
        json.loads(line)
        for line in samples_path.read_text(encoding="utf-8").splitlines()
    ]
    samples[0]["state"] = "tampered text"
    samples_path.write_text(
        "\n".join(json.dumps(sample) for sample in samples) + "\n",
        encoding="utf-8",
    )
    check = validate_bundle(tmp_path / "bundle")
    assert not check.valid
    assert any("samples_sha256" in error for error in check.errors)


def test_disagreement_is_reported_and_never_silently_merged(tmp_path) -> None:
    _prepare(tmp_path, _samples(2))
    labels = tmp_path / "labels.jsonl"
    _write_jsonl(labels, [
        _label("sample-0000", True, annotator="alice"),
        _label("sample-0000", False, annotator="bob"),
        _label("sample-0001", True, annotator="alice"),
        _label("sample-0001", True, annotator="bob"),
    ])
    out = tmp_path / "merged.jsonl"
    disputes = tmp_path / "disputes.jsonl"
    result = merge_bundle(
        tmp_path / "bundle", labels, out, disputes_path=disputes,
    )
    assert result.merged == 1
    assert result.disputes == 1
    assert result.status == "WAITING_FOR_HUMAN_LABELS"

    merged = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [row["id"] for row in merged] == ["sample-0001"]
    assert merged[0]["annotator"] == "alice,bob"
    assert len(merged[0]["annotations"]) == 2

    conflict = [json.loads(line) for line in disputes.read_text(
        encoding="utf-8"
    ).splitlines()]
    assert conflict[0]["id"] == "sample-0000"
    assert conflict[0]["reason"] == "annotator_disagreement"
    assert len(conflict[0]["annotations"]) == 2


def test_merge_is_idempotent_and_preserves_correction_history(tmp_path) -> None:
    _prepare(tmp_path, _samples(1))
    labels = tmp_path / "labels.jsonl"
    _write_jsonl(labels, [
        _label("sample-0000", True),
        _label("sample-0000", False),
    ])
    out = tmp_path / "merged.jsonl"
    first = merge_bundle(tmp_path / "bundle", labels, out)
    assert first.merged == 1
    assert first.revisions == 1
    before = out.read_bytes()
    second = merge_bundle(tmp_path / "bundle", labels, out)
    assert second.merged == 1
    assert second.revisions == 1
    assert out.read_bytes() == before
    row = json.loads(before.decode("utf-8"))
    assert row["labels"] == {QUESTION_ID: False}
    assert [entry["labels"][QUESTION_ID] for entry in row["annotations"]] == [True, False]


def test_cli_prepare_and_merge(tmp_path, capsys) -> None:
    source = tmp_path / "input.jsonl"
    _write_jsonl(source, _samples(2))
    bundle = tmp_path / "cli-bundle"
    assert main([
        "prepare", "--input", str(source), "--out-dir", str(bundle),
        "--version", "cli-v1",
    ]) == 0
    prepared = json.loads(capsys.readouterr().out)
    assert prepared["status"] == "READY_FOR_LABELING"
    assert prepared["dataset_version"] == "cli-v1"

    labels = tmp_path / "labels.jsonl"
    _write_jsonl(labels, [_label("sample-0000"), _label("sample-0001")])
    out = tmp_path / "merged.jsonl"
    assert main([
        "merge", "--bundle", str(bundle), "--labels", str(labels),
        "--out", str(out),
    ]) == 1
    merged = json.loads(capsys.readouterr().out)
    assert merged["status"] == "WAITING_FOR_HUMAN_LABELS"
    assert merged["merged"] == 2


def test_report_and_validate_exit_codes(tmp_path, capsys) -> None:
    _prepare(tmp_path, _samples(2))
    assert main(["report", str(tmp_path / "bundle")]) == 0
    report_text = capsys.readouterr().out
    payload = json.loads(report_text)
    assert payload["status"] == "READY_FOR_LABELING"
    assert payload["pending"] == 2
    assert "article text" not in report_text

    labels = tmp_path / "labels.jsonl"
    _write_jsonl(labels, [_label("sample-0000"), _label("sample-0001")])
    out = tmp_path / "merged.jsonl"
    assert merge_bundle(tmp_path / "bundle", labels, out).merged == 2
    assert main(["validate", str(out)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "WAITING_FOR_HUMAN_LABELS"
    assert payload["valid_samples"] == 2
    assert payload["rejected"] == 0
