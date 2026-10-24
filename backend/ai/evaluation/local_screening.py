"""Offline evaluation and human-labeling workflow for local screening.

The existing evaluation contract stays the same: a labeled JSONL dataset has
``id``, ``state``, ``labels``, ``annotator``, ``label_source``, ``label_status``
and ``dataset_version``. This module adds an offline workflow around it:

``prepare``  unlabeled JSONL → blind bundle (pending samples, no predictions)
``validate`` bundle integrity or labeled-dataset readiness
``merge``    human label rows → final labeled dataset, with disputes kept apart
``report``   counts, hashes and readiness without printing article text

Nothing here calls a model, database, network service or Git command. Label
rows are human declarations; the validator can check their shape and declared
provenance, but cannot independently prove that a human wrote them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from backend.ai.local_screening import (
    CURRENT_QUESTION_SET,
    QUESTION_ID,
    SCOPE_RULE_VERSION,
    SCREENING_QUESTIONS,
    question_set_version,
)

MIN_LABELED_SAMPLES = 200
HUMAN_LABEL_SOURCE = "human"
VALID_LABEL_STATUS = "valid"
PENDING_LABEL_STATUS = "pending"
BUNDLE_FORMAT_VERSION = 1
BUNDLE_MANIFEST = "bundle.json"
BUNDLE_SAMPLES = "samples.jsonl"
BLIND_FORBIDDEN_KEYS = frozenset({
    "labels", "local_screening", "prediction", "predictions",
    "probabilities", "confidence", "decision",
})


@dataclass(frozen=True)
class DatasetCheck:
    total: int
    valid: bool
    valid_samples: int = 0
    human_labels: int = 0
    duplicates: int = 0
    pending: int = 0
    rejected: int = 0
    dataset_sha256: str | None = None
    dataset_version: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BundleCheck:
    total: int
    valid: bool
    pending: int = 0
    dataset_version: str | None = None
    source_sha256: str | None = None
    samples_sha256: str | None = None
    bundle_sha256: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnnotationCheck:
    total: int
    valid: bool
    valid_labels: int = 0
    pending: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PrepareResult:
    status: str
    out_dir: str
    total: int
    valid: int
    rejected: int
    duplicates: int
    dataset_version: str | None
    source_sha256: str | None
    samples_sha256: str | None
    bundle_sha256: str | None
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "out_dir": self.out_dir,
            "total": self.total,
            "valid": self.valid,
            "rejected": self.rejected,
            "duplicates": self.duplicates,
            "dataset_version": self.dataset_version,
            "source_sha256": self.source_sha256,
            "samples_sha256": self.samples_sha256,
            "bundle_sha256": self.bundle_sha256,
            "errors": self.errors[:50],
        }


@dataclass(frozen=True)
class MergeResult:
    status: str
    out_path: str
    disputes_path: str | None
    dataset_version: str | None
    dataset_sha256: str | None
    labels_sha256: str | None
    label_rows: int
    valid_labels: int
    pending_labels: int
    rejected_labels: int
    unknown_ids: int
    pending_samples: int
    revisions: int
    merged: int
    disputes: int
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "out_path": self.out_path,
            "disputes_path": self.disputes_path,
            "dataset_version": self.dataset_version,
            "dataset_sha256": self.dataset_sha256,
            "labels_sha256": self.labels_sha256,
            "label_rows": self.label_rows,
            "valid_labels": self.valid_labels,
            "pending_labels": self.pending_labels,
            "rejected_labels": self.rejected_labels,
            "unknown_ids": self.unknown_ids,
            "pending_samples": self.pending_samples,
            "revisions": self.revisions,
            "merged": self.merged,
            "disputes": self.disputes,
            "errors": self.errors[:50],
        }


@dataclass(frozen=True)
class NoulScore:
    total: int
    scored: int
    abstained: int
    accuracy: float | None
    brier: float | None


@dataclass(frozen=True)
class NoulEvaluation:
    provider: str
    model: str
    dataset_sha256: str | None
    total: int
    scored: int
    abstained: int
    errors: int
    accuracy: float | None
    precision: float | None
    recall: float | None
    brier: float | None
    coverage: float
    latency_ms_total: float
    latency_ms_mean: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "dataset_sha256": self.dataset_sha256,
            "total": self.total,
            "scored": self.scored,
            "abstained": self.abstained,
            "errors": self.errors,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "brier": self.brier,
            "coverage": self.coverage,
            "latency_ms_total": round(self.latency_ms_total, 1),
            "latency_ms_mean": (
                round(self.latency_ms_mean, 1)
                if self.latency_ms_mean is not None else None
            ),
        }


def dataset_fingerprint(records: Sequence[Mapping[str, Any]]) -> str | None:
    """Stable SHA-256 for a dataset; never includes secrets or article bodies."""
    try:
        payload = json.dumps(
            records, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        )
    except TypeError:
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_state(state: Any) -> bool:
    if isinstance(state, str):
        return bool(state.strip())
    if isinstance(state, (dict, list)):
        return bool(state)
    return False


def _state_fingerprint(state: Any) -> str:
    if isinstance(state, str):
        canonical = " ".join(state.split())
    else:
        canonical = json.dumps(
            state, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _label_error(question: Mapping[str, Any], value: Any) -> str | None:
    kind = question.get("type")
    if kind == "noul":
        return None if isinstance(value, bool) else "label must be boolean"
    if kind == "choice":
        criteria = question.get("criteria")
        if not isinstance(criteria, dict) or not criteria:
            return "choice question has no criteria"
        if not isinstance(value, str) or value not in criteria:
            return "label must be one of the criteria keys"
        return None
    if kind == "score":
        criteria = question.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            return "score question has no criteria"
        if (not isinstance(value, int) or isinstance(value, bool)
                or not 0 <= value < len(criteria)):
            return "label must be a level index"
        return None
    return "unknown question type"


def _validate_label_fields(
    record: Mapping[str, Any],
    prefix: str,
    *,
    allow_pending: bool,
    require_version: bool = False,
) -> tuple[list[str], bool, bool]:
    """Validate label/provenance fields shared by datasets and annotations."""
    errors: list[str] = []
    ok = True
    status = record.get("label_status")
    pending = status == PENDING_LABEL_STATUS

    sample_id = record.get("id")
    if not isinstance(sample_id, str) or not sample_id.strip():
        errors.append(prefix + "id is required")
        ok = False
    if record.get("label_source") != HUMAN_LABEL_SOURCE:
        errors.append(prefix + "label_source must be 'human'")
        ok = False
    if not isinstance(record.get("annotator"), str) or not record["annotator"].strip():
        errors.append(prefix + "annotator is required")
        ok = False
    version = record.get("dataset_version")
    if version is None and require_version:
        errors.append(prefix + "dataset_version is required")
        ok = False
    elif version is not None and (
        not isinstance(version, str) or not version.strip()
    ):
        errors.append(prefix + "dataset_version must be a non-empty string")
        ok = False

    if pending and allow_pending:
        return errors, ok, True
    if status != VALID_LABEL_STATUS:
        errors.append(prefix + "label_status must be 'valid'")
        ok = False
        if pending:
            return errors, ok, True
        return errors, ok, pending

    questions = record.get("questions", SCREENING_QUESTIONS)
    if not isinstance(questions, dict) or not questions:
        errors.append(prefix + "questions must be a non-empty object")
        return errors, False, pending
    question_version = question_set_version(questions)
    if question_version is None:
        errors.append(prefix + "questions must match a known screening question set")
        ok = False
    declared_scope = record.get("scope_rule_version")
    if declared_scope is not None and declared_scope != question_version:
        errors.append(prefix + "scope_rule_version does not match questions")
        ok = False
    labels = record.get("labels")
    if not isinstance(labels, dict):
        errors.append(prefix + "labels must be an object")
        return errors, False, pending
    if set(labels) != set(questions):
        errors.append(prefix + "labels must match question ids exactly")
        return errors, False, pending
    for question_id, question in questions.items():
        if not isinstance(question, dict):
            errors.append(prefix + f"question {question_id} is not an object")
            ok = False
            continue
        message = _label_error(question, labels[question_id])
        if message:
            errors.append(prefix + f"question {question_id}: {message}")
            ok = False
    return errors, ok, pending


def validate_records(records: Iterable[Mapping[str, Any]]) -> DatasetCheck:
    """Validate labeled samples. Returns every problem; does not mutate input."""
    items = list(records)
    errors: list[str] = []
    if len(items) < MIN_LABELED_SAMPLES:
        errors.append(
            f"at least {MIN_LABELED_SAMPLES} labeled samples required; got {len(items)}"
        )

    seen_ids: set[str] = set()
    seen_states: set[str] = set()
    versions: set[str] = set()
    valid_samples = 0
    human_labels = 0
    duplicates = 0
    pending = 0

    for index, record in enumerate(items):
        prefix = f"sample {index + 1}: "
        if not isinstance(record, Mapping):
            errors.append(prefix + "not an object")
            continue
        sample_ok = True

        sample_id = record.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            sample_ok = False
        elif sample_id in seen_ids:
            errors.append(prefix + f"duplicate id: {sample_id}")
            duplicates += 1
            sample_ok = False
        else:
            seen_ids.add(sample_id)

        state = record.get("state")
        if not _valid_state(state):
            errors.append(prefix + "state is empty or has an unsupported type")
            sample_ok = False
        else:
            fingerprint = _state_fingerprint(state)
            if fingerprint in seen_states:
                errors.append(prefix + "duplicate state")
                duplicates += 1
                sample_ok = False
            else:
                seen_states.add(fingerprint)

        label_errors, label_ok, is_pending = _validate_label_fields(
            record, prefix, allow_pending=False, require_version=True,
        )
        errors.extend(label_errors)
        if is_pending:
            pending += 1
        if not label_ok:
            sample_ok = False
        version = record.get("dataset_version")
        if isinstance(version, str) and version.strip():
            versions.add(version)
        if sample_ok:
            valid_samples += 1
            if record.get("label_source") == HUMAN_LABEL_SOURCE:
                human_labels += 1

    if len(versions) > 1:
        errors.append("dataset_version is not consistent across records")
    dataset_version = next(iter(versions)) if len(versions) == 1 else None
    return DatasetCheck(
        total=len(items),
        valid=not errors,
        valid_samples=valid_samples,
        human_labels=human_labels,
        duplicates=duplicates,
        pending=pending,
        rejected=len(items) - valid_samples,
        dataset_sha256=dataset_fingerprint(items),
        dataset_version=dataset_version,
        errors=errors,
    )


def validate_annotations(rows: Iterable[Mapping[str, Any]]) -> AnnotationCheck:
    """Validate human label rows; pending rows are counted but are not final."""
    items = list(rows)
    errors: list[str] = []
    valid_labels = 0
    pending = 0
    for index, row in enumerate(items):
        prefix = f"label row {index + 1}: "
        if not isinstance(row, Mapping):
            errors.append(prefix + "not an object")
            continue
        row_errors, row_ok, is_pending = _validate_label_fields(
            row, prefix, allow_pending=True,
        )
        errors.extend(row_errors)
        if is_pending:
            pending += 1
        elif row_ok:
            valid_labels += 1
        else:
            errors.append(prefix + "label row rejected")
    return AnnotationCheck(
        total=len(items),
        valid=not errors,
        valid_labels=valid_labels,
        pending=pending,
        errors=errors,
    )


def read_jsonl(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read JSONL objects; protocol errors are reported, never silently dropped."""
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {line_number}: not an object")
            continue
        records.append(value)
    return records, errors


def load_jsonl(path: str | Path) -> tuple[list[dict[str, Any]], DatasetCheck]:
    """Load labeled JSONL; parsing errors are part of the dataset result."""
    records, parse_errors = read_jsonl(path)
    check = validate_records(records)
    errors = parse_errors + check.errors
    return records, DatasetCheck(
        total=check.total,
        valid=not errors,
        valid_samples=check.valid_samples,
        human_labels=check.human_labels,
        duplicates=check.duplicates,
        pending=check.pending,
        rejected=check.total - check.valid_samples,
        dataset_sha256=check.dataset_sha256,
        dataset_version=check.dataset_version,
        errors=errors,
    )


def _jsonl_text(records: Sequence[Mapping[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(
        json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for record in records
    ) + "\n"


def _write_all_if_unchanged(
    targets: Sequence[tuple[str | Path, str]], *, force: bool,
) -> None:
    """Write only missing/changed targets; refuse silent replacement."""
    pending: list[tuple[Path, str]] = []
    for path, text in targets:
        target = Path(path)
        if target.exists():
            if target.read_text(encoding="utf-8") == text:
                continue
            if not force:
                raise FileExistsError(f"output exists with different content: {target}")
        pending.append((target, text))
    for target, text in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")


def _bundle_fingerprint(
    manifest: Mapping[str, Any], samples: Sequence[Mapping[str, Any]],
) -> str | None:
    base = {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    return dataset_fingerprint([{"manifest": base, "samples": samples}])


def _safe_relative_file(bundle_dir: Path, name: Any) -> Path | None:
    if not isinstance(name, str) or not name.strip():
        return None
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        return None
    return bundle_dir / path


def prepare_bundle(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    version: str | None = None,
) -> PrepareResult:
    """Create a blind labeling bundle from unlabeled local samples."""
    source = Path(input_path)
    out = Path(out_dir)
    source_sha = _source_fingerprint(source)
    records, parse_errors = read_jsonl(source)
    errors = list(parse_errors)
    seen_ids: set[str] = set()
    seen_states: set[str] = set()
    samples: list[dict[str, Any]] = []
    duplicates = 0

    for index, record in enumerate(records):
        prefix = f"sample {index + 1}: "
        sample_ok = True
        sample_id = record.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            errors.append(prefix + "id is required")
            sample_ok = False
        elif sample_id in seen_ids:
            errors.append(prefix + f"duplicate id: {sample_id}")
            duplicates += 1
            sample_ok = False
        else:
            seen_ids.add(sample_id)

        state = record.get("state")
        if not _valid_state(state):
            errors.append(prefix + "state is empty or has an unsupported type")
            sample_ok = False
        else:
            fingerprint = _state_fingerprint(state)
            if fingerprint in seen_states:
                errors.append(prefix + "duplicate state")
                duplicates += 1
                sample_ok = False
            else:
                seen_states.add(fingerprint)

        for key in sorted(BLIND_FORBIDDEN_KEYS):
            if key in record:
                errors.append(prefix + f"input contains non-blind field: {key}")
                sample_ok = False

        if sample_ok:
            samples.append({
                "id": sample_id,
                "state": state,
                "label_status": PENDING_LABEL_STATUS,
            })

    if not records and not errors:
        return PrepareResult(
            status="WAITING_FOR_INPUT_DATA",
            out_dir=str(out), total=0, valid=0, rejected=0, duplicates=0,
            dataset_version=None, source_sha256=source_sha,
            samples_sha256=None, bundle_sha256=None, errors=errors,
        )
    if errors:
        return PrepareResult(
            status="INVALID_INPUT",
            out_dir=str(out), total=len(records), valid=len(samples),
            rejected=len(records) - len(samples), duplicates=duplicates,
            dataset_version=version, source_sha256=source_sha,
            samples_sha256=None, bundle_sha256=None, errors=errors,
        )

    dataset_version = version or f"sha256-{source_sha[:16]}"
    samples_sha = dataset_fingerprint(samples)
    manifest = {
        "format_version": BUNDLE_FORMAT_VERSION,
        "dataset_version": dataset_version,
        "source_sha256": source_sha,
        "samples_sha256": samples_sha,
        "sample_count": len(samples),
        "question_id": QUESTION_ID,
        "question": CURRENT_QUESTION_SET[QUESTION_ID],
        "scope_rule_version": SCOPE_RULE_VERSION,
        "samples_file": BUNDLE_SAMPLES,
    }
    bundle_sha = _bundle_fingerprint(manifest, samples)
    manifest["bundle_sha256"] = bundle_sha
    manifest_text = json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2)
    manifest_text += "\n"
    samples_text = _jsonl_text(samples)

    try:
        _write_all_if_unchanged([
            (out / BUNDLE_MANIFEST, manifest_text),
            (out / BUNDLE_SAMPLES, samples_text),
        ], force=False)
    except FileExistsError as exc:
        errors.append(str(exc))
        return PrepareResult(
            status="OUTPUT_EXISTS",
            out_dir=str(out), total=len(records), valid=len(samples),
            rejected=0, duplicates=duplicates,
            dataset_version=dataset_version, source_sha256=source_sha,
            samples_sha256=samples_sha, bundle_sha256=bundle_sha,
            errors=errors,
        )

    return PrepareResult(
        status="READY_FOR_LABELING",
        out_dir=str(out), total=len(records), valid=len(samples),
        rejected=0, duplicates=duplicates,
        dataset_version=dataset_version, source_sha256=source_sha,
        samples_sha256=samples_sha, bundle_sha256=bundle_sha,
        errors=errors,
    )


def _read_bundle(bundle_dir: str | Path) -> tuple[dict[str, Any] | None, list[dict], list[str]]:
    root = Path(bundle_dir)
    errors: list[str] = []
    manifest_path = root / BUNDLE_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [], [f"cannot read {BUNDLE_MANIFEST}: {exc}"]
    if not isinstance(manifest, dict):
        return None, [], [f"{BUNDLE_MANIFEST} is not an object"]
    samples_path = _safe_relative_file(
        root, manifest.get("samples_file", BUNDLE_SAMPLES),
    )
    if samples_path is None:
        return manifest, [], ["samples_file must be a safe relative path"]
    try:
        samples, parse_errors = read_jsonl(samples_path)
    except (OSError, UnicodeError) as exc:
        return manifest, [], [f"cannot read samples: {exc}"]
    errors.extend(parse_errors)
    return manifest, samples, errors


def validate_bundle(bundle_dir: str | Path) -> BundleCheck:
    """Validate a blind bundle and its reproducible hashes."""
    root = Path(bundle_dir)
    manifest, samples, errors = _read_bundle(root)
    if manifest is None:
        return BundleCheck(total=len(samples), valid=False, errors=errors)

    if manifest.get("format_version") != BUNDLE_FORMAT_VERSION:
        errors.append("unsupported bundle format_version")
    version = manifest.get("dataset_version")
    if not isinstance(version, str) or not version.strip():
        errors.append("dataset_version is required")
    if manifest.get("question_id") != QUESTION_ID:
        errors.append("question_id does not match the screening contract")
    question_version = question_set_version({QUESTION_ID: manifest.get("question")})
    if question_version is None:
        errors.append("question does not match a known screening contract")
    declared_scope = manifest.get("scope_rule_version")
    if declared_scope is not None and declared_scope != question_version:
        errors.append("scope_rule_version does not match question")
    if not isinstance(manifest.get("sample_count"), int):
        errors.append("sample_count must be an integer")
    if not samples:
        errors.append("bundle contains no samples")

    seen_ids: set[str] = set()
    seen_states: set[str] = set()
    for index, sample in enumerate(samples):
        prefix = f"sample {index + 1}: "
        sample_id = sample.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            errors.append(prefix + "id is required")
        elif sample_id in seen_ids:
            errors.append(prefix + f"duplicate id: {sample_id}")
        else:
            seen_ids.add(sample_id)
        state = sample.get("state")
        if not _valid_state(state):
            errors.append(prefix + "state is empty or has an unsupported type")
        else:
            fingerprint = _state_fingerprint(state)
            if fingerprint in seen_states:
                errors.append(prefix + "duplicate state")
            else:
                seen_states.add(fingerprint)
        if sample.get("label_status") != PENDING_LABEL_STATUS:
            errors.append(prefix + "label_status must be 'pending'")
        for key in sorted(BLIND_FORBIDDEN_KEYS):
            if key in sample:
                errors.append(prefix + f"bundle is not blind: {key}")

    samples_sha = dataset_fingerprint(samples)
    if manifest.get("samples_sha256") != samples_sha:
        errors.append("samples_sha256 does not match samples.jsonl")
    if manifest.get("sample_count") != len(samples):
        errors.append("sample_count does not match samples.jsonl")
    if manifest.get("bundle_sha256") != _bundle_fingerprint(manifest, samples):
        errors.append("bundle_sha256 does not match manifest/samples")

    return BundleCheck(
        total=len(samples),
        valid=not errors,
        pending=len(samples),
        dataset_version=version if isinstance(version, str) else None,
        source_sha256=(
            manifest.get("source_sha256")
            if isinstance(manifest.get("source_sha256"), str) else None
        ),
        samples_sha256=samples_sha,
        bundle_sha256=(
            manifest.get("bundle_sha256")
            if isinstance(manifest.get("bundle_sha256"), str) else None
        ),
        errors=errors,
    )


def merge_bundle(
    bundle_dir: str | Path,
    labels_path: str | Path,
    out_path: str | Path,
    *,
    disputes_path: str | Path | None = None,
    force: bool = False,
) -> MergeResult:
    """Attach human labels to a bundle; never auto-adjudicates conflicts."""
    out = Path(out_path)
    disputes_target = (
        Path(disputes_path) if disputes_path is not None
        else out.with_name(f"{out.stem}_disputes.jsonl")
    )
    bundle_check = validate_bundle(bundle_dir)
    if not bundle_check.valid:
        return MergeResult(
            status="INVALID_BUNDLE", out_path=str(out),
            disputes_path=None, dataset_version=bundle_check.dataset_version,
            dataset_sha256=None, labels_sha256=None,
            label_rows=0, valid_labels=0, pending_labels=0,
            rejected_labels=0, unknown_ids=0, pending_samples=0,
            revisions=0, merged=0, disputes=0, errors=bundle_check.errors,
        )

    manifest, samples, _ = _read_bundle(bundle_dir)
    if manifest is None:
        return MergeResult(
            status="INVALID_BUNDLE", out_path=str(out),
            disputes_path=None, dataset_version=None, dataset_sha256=None,
            labels_sha256=None, label_rows=0, valid_labels=0, pending_labels=0,
            rejected_labels=0, unknown_ids=0, pending_samples=0,
            revisions=0, merged=0, disputes=0,
            errors=["bundle manifest became unreadable"],
        )
    rows, parse_errors = read_jsonl(labels_path)
    labels_sha = _source_fingerprint(Path(labels_path))
    merged_questions = {QUESTION_ID: manifest.get("question")}
    errors = list(parse_errors)
    valid_rows: list[dict[str, Any]] = []
    pending_labels = 0
    rejected_labels = 0
    for index, row in enumerate(rows):
        row_errors, row_ok, is_pending = _validate_label_fields(
            row, f"label row {index + 1}: ", allow_pending=True,
        )
        errors.extend(row_errors)
        if is_pending and row_ok:
            pending_labels += 1
        elif row_ok:
            valid_rows.append(row)
        else:
            rejected_labels += 1

    sample_ids = {sample["id"] for sample in samples}
    grouped: dict[str, list[dict[str, Any]]] = {}
    unknown_ids: set[str] = set()
    for row in valid_rows:
        row_id = row["id"]
        if row_id not in sample_ids:
            unknown_ids.add(row_id)
            continue
        grouped.setdefault(row_id, []).append(row)

    merged: list[dict[str, Any]] = []
    disputes: list[dict[str, Any]] = []
    pending_samples = 0
    revisions = 0
    for sample in samples:
        row_id = sample["id"]
        rows_for_id = grouped.get(row_id, [])
        if not rows_for_id:
            pending_samples += 1
            continue
        by_annotator: dict[str, dict[str, Any]] = {}
        for row in rows_for_id:
            annotator = row["annotator"].strip()
            if annotator in by_annotator:
                revisions += 1
            by_annotator[annotator] = row
        current = list(by_annotator.values())
        annotations = [
            {
                "annotator": row.get("annotator"),
                "labels": row.get("labels"),
                "label_source": row.get("label_source"),
                "label_status": row.get("label_status"),
            }
            for row in rows_for_id
        ]
        first_labels = current[0]["labels"]
        if any(row["labels"] != first_labels for row in current[1:]):
            disputes.append({
                "id": row_id,
                "dataset_version": manifest["dataset_version"],
                "reason": "annotator_disagreement",
                "annotations": annotations,
            })
            continue
        annotators = sorted(by_annotator)
        merged.append({
            "id": row_id,
            "state": sample["state"],
            "labels": first_labels,
            "annotator": ",".join(annotators),
            "annotators": annotators,
            "label_source": HUMAN_LABEL_SOURCE,
            "label_status": VALID_LABEL_STATUS,
            "dataset_version": manifest["dataset_version"],
            "questions": merged_questions,
            "scope_rule_version": question_set_version(merged_questions),
            "annotations": annotations,
        })

    check = validate_records(merged)
    merged_text = _jsonl_text(merged)
    disputes_text = _jsonl_text(disputes)
    extras = [(disputes_target, disputes_text)] if disputes else []
    try:
        _write_all_if_unchanged([(out, merged_text), *extras], force=force)
    except FileExistsError as exc:
        errors.append(str(exc))
        return MergeResult(
            status="OUTPUT_EXISTS", out_path=str(out),
            disputes_path=str(disputes_target) if disputes else None,
            dataset_version=manifest["dataset_version"],
            dataset_sha256=check.dataset_sha256,
            labels_sha256=labels_sha,
            label_rows=len(rows), valid_labels=len(valid_rows),
            pending_labels=pending_labels, rejected_labels=rejected_labels,
            unknown_ids=len(unknown_ids), pending_samples=pending_samples,
            revisions=revisions, merged=len(merged), disputes=len(disputes),
            errors=errors,
        )

    if unknown_ids:
        errors.append(f"unknown label ids: {len(unknown_ids)}")
    status = "READY_FOR_EVALUATION" if check.valid else "WAITING_FOR_HUMAN_LABELS"
    return MergeResult(
        status=status, out_path=str(out),
        disputes_path=str(disputes_target) if disputes else None,
        dataset_version=manifest["dataset_version"],
        dataset_sha256=check.dataset_sha256,
        labels_sha256=labels_sha,
        label_rows=len(rows), valid_labels=len(valid_rows),
        pending_labels=pending_labels, rejected_labels=rejected_labels,
        unknown_ids=len(unknown_ids), pending_samples=pending_samples,
        revisions=revisions, merged=len(merged), disputes=len(disputes),
        errors=errors,
    )


def _dataset_report(check: DatasetCheck) -> dict[str, Any]:
    return {
        "kind": "dataset",
        "status": (
            "READY_FOR_EVALUATION" if check.valid
            else "WAITING_FOR_HUMAN_LABELS"
        ),
        "total": check.total,
        "valid_samples": check.valid_samples,
        "human_labels": check.human_labels,
        "rejected": check.rejected,
        "pending": check.pending,
        "duplicates": check.duplicates,
        "dataset_version": check.dataset_version,
        "dataset_sha256": check.dataset_sha256,
        "errors": check.errors[:50],
    }


def _bundle_report(check: BundleCheck) -> dict[str, Any]:
    return {
        "kind": "bundle",
        "status": "READY_FOR_LABELING" if check.valid else "INVALID_BUNDLE",
        "total": check.total,
        "pending": check.pending,
        "dataset_version": check.dataset_version,
        "source_sha256": check.source_sha256,
        "samples_sha256": check.samples_sha256,
        "bundle_sha256": check.bundle_sha256,
        "errors": check.errors[:50],
    }


def _target_report(path: str | Path) -> tuple[dict[str, Any], bool]:
    target = Path(path)
    if target.is_dir():
        check = validate_bundle(target)
        return _bundle_report(check), check.valid
    _, check = load_jsonl(target)
    return _dataset_report(check), check.valid


def score_noul(
    records: Sequence[Mapping[str, Any]],
    predictions: Sequence[float | None],
) -> NoulScore:
    """Score P(yes) predictions against human labels; ``None`` means abstained.

    No value is reported when nothing was scored: accuracy/Brier stay ``None``.
    """
    if len(records) != len(predictions):
        raise ValueError("predictions must match the number of records")
    correct = 0
    brier_sum = 0.0
    scored = 0
    for record, prediction in zip(records, predictions, strict=True):
        label = record.get("labels", {}).get(QUESTION_ID)
        if not isinstance(label, bool):
            raise ValueError("record has no boolean screening label")
        if prediction is None:
            continue
        if (not isinstance(prediction, (int, float)) or isinstance(prediction, bool)
                or not math.isfinite(float(prediction))
                or not 0.0 <= float(prediction) <= 1.0):
            raise ValueError("prediction must be a probability or None")
        probability = float(prediction)
        scored += 1
        if (probability >= 0.5) == label:
            correct += 1
        brier_sum += (probability - (1.0 if label else 0.0)) ** 2
    return NoulScore(
        total=len(records),
        scored=scored,
        abstained=len(records) - scored,
        accuracy=(correct / scored) if scored else None,
        brier=(brier_sum / scored) if scored else None,
    )


def evaluate_noul(
    records: Sequence[Mapping[str, Any]],
    predictions: Sequence[float | None],
    *,
    provider: str,
    model: str,
    errors: int = 0,
    latencies_ms: Sequence[float | None] | None = None,
) -> NoulEvaluation:
    """Evaluate one provider against a fixed dataset; no model is called here."""
    if not isinstance(errors, int) or isinstance(errors, bool) or errors < 0:
        raise ValueError("errors must be a non-negative integer")
    if latencies_ms is not None and len(latencies_ms) != len(records):
        raise ValueError("latencies must match the number of records")
    score = score_noul(records, predictions)

    true_positive = false_positive = false_negative = 0
    for record, prediction in zip(records, predictions, strict=True):
        if prediction is None:
            continue
        label = record["labels"][QUESTION_ID]
        predicted = float(prediction) >= 0.5
        if predicted and label:
            true_positive += 1
        elif predicted and not label:
            false_positive += 1
        elif not predicted and label:
            false_negative += 1

    latency_values: list[float] = []
    if latencies_ms is not None:
        for value in latencies_ms:
            if value is None:
                continue
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(float(value)) or float(value) < 0):
                raise ValueError("latencies must be finite non-negative numbers")
            latency_values.append(float(value))
    latency_total = sum(latency_values)

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive else None
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative else None
    )
    coverage = score.scored / score.total if score.total else 0.0
    return NoulEvaluation(
        provider=provider,
        model=model,
        dataset_sha256=dataset_fingerprint(records),
        total=score.total,
        scored=score.scored,
        abstained=score.abstained,
        errors=errors,
        accuracy=score.accuracy,
        precision=precision,
        recall=recall,
        brier=score.brier,
        coverage=coverage,
        latency_ms_total=latency_total,
        latency_ms_mean=(
            latency_total / len(latency_values) if latency_values else None
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline human-labeling and validation for local screening",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="build a blind label bundle")
    prepare.add_argument("--input", required=True, help="unlabeled JSONL input")
    prepare.add_argument(
        "--out-dir", required=True, help="local directory for bundle files",
    )
    prepare.add_argument(
        "--version", help="dataset version (default: source hash prefix)",
    )

    validate = subparsers.add_parser(
        "validate", help="validate a labeled dataset or bundle directory",
    )
    validate.add_argument("path")

    report = subparsers.add_parser(
        "report", help="print dataset or bundle counts without article text",
    )
    report.add_argument("path")

    merge = subparsers.add_parser(
        "merge", help="attach human label rows to a bundle by stable id",
    )
    merge.add_argument("--bundle", required=True, help="prepared bundle directory")
    merge.add_argument("--labels", required=True, help="human label JSONL")
    merge.add_argument("--out", required=True, help="final labeled JSONL")
    merge.add_argument("--disputes", help="optional disagreement JSONL")
    merge.add_argument(
        "--force", action="store_true", help="replace different output files",
    )
    return parser


def main(
    argv: Sequence[str] | None = None, *, stream: TextIO | None = None,
) -> int:
    """CLI entry point; no article text or secret values are printed."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    if not raw_args or raw_args[0] in {"-h", "--help"}:
        parser.print_help()
        return 0
    if raw_args[0] not in {"prepare", "validate", "merge", "report"}:
        raw_args = ["validate", *raw_args]
    try:
        args = parser.parse_args(raw_args)
    except SystemExit as exc:
        return int(exc.code or 0)
    output = stream or sys.stdout

    try:
        if args.command == "prepare":
            result = prepare_bundle(args.input, args.out_dir, version=args.version)
            print(json.dumps(result.as_dict(), ensure_ascii=False), file=output)
            return 0 if result.status == "READY_FOR_LABELING" else 1
        if args.command == "merge":
            result = merge_bundle(
                args.bundle, args.labels, args.out,
                disputes_path=args.disputes, force=args.force,
            )
            print(json.dumps(result.as_dict(), ensure_ascii=False), file=output)
            return 0 if result.status == "READY_FOR_EVALUATION" else 1
        report, ready = _target_report(args.path)
        print(json.dumps(report, ensure_ascii=False), file=output)
        if args.command == "report":
            return 0
        return 0 if ready else 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}), file=output)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
