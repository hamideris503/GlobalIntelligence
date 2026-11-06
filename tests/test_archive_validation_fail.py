"""Validation failure cases for F13."""
from __future__ import annotations

import os
import tempfile
import zipfile

from domains.archive.service import validate_archive_zip


def test_corrupt_zip():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "bad.zip")
    with open(p, "wb") as f:
        f.write(b"not a zip")
    v = validate_archive_zip(p)
    assert v["ok"] is False
    assert v["errors"]


def test_missing_file():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "partial.zip")
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("manifest.json", "{}")
    v = validate_archive_zip(p)
    assert v["ok"] is False
    assert any("missing file" in e for e in v["errors"])
