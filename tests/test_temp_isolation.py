"""F-10: temp dirs must not depend on pytest's shared ``pytest-current`` symlink.

On Windows a stale ``pytest-of-<user>/pytest-current`` directory symlink cannot
be unlinked and the next run dies during temp cleanup (WinError 5). The suite
therefore runs under a private temp root; this test fails if that regresses.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_tmp_path_uses_private_basetemp(tmp_path: Path, pytestconfig: pytest.Config) -> None:
    explicit = pytestconfig.option.basetemp
    if explicit:
        # CI با --basetemp صریح اجرا می‌شود؛ آن مسیر بر env اولویت دارد
        assert tmp_path.resolve().is_relative_to(Path(explicit).resolve())
        return
    root = Path(os.environ["PYTEST_DEBUG_TEMPROOT"])
    assert root.name.startswith(f"gi-pytest-{os.getpid()}-")
    assert root.is_dir()
    # ریشهٔ شماره‌دارِ pytest داخل ریشهٔ اختصاصی همین اجرا ساخته می‌شود
    assert tmp_path.resolve().is_relative_to(root.resolve())
