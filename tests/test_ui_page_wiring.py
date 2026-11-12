"""Guards for the single-file UI: page renderers, loader containers, number formatting.

STEP 6A.42 browser verification found three defects that no existing check caught:

1. `renderPage()` re-assigned `macro`/`portfolio`/`geopolitics` to the placeholder
   `genericDomain()` after their real renderers ran, so loaders wrote into
   containers that never existed and the pages looked like mock screens.
2. `nfV` existed only as a local helper inside `loadIranBrief`, so the macro,
   geopolitics and portfolio loaders threw `ReferenceError` on their first real
   data row.
3. `nfV` appended the `B`/`M` suffix before `Intl.NumberFormat`, turning large
   values into `NaN` («ناعدد»).

These tests keep all three honest without a browser: static wiring checks over
`backend/static/index.html` plus a real Node run of the `nf`/`nfV` helpers.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parent.parent / "backend" / "static" / "index.html"

# (page id, dedicated renderer function)
DEDICATED_PAGES = (
    ("macro", "macroPage"),
    ("portfolio", "portfolioPage"),
    ("geopolitics", "geopoliticsPage"),
)

# (page renderer, loader that fills its live container) — every data-bearing page.
PAGE_LOADERS = (
    ("dashboard", "loadDashboard"),
    ("macroPage", "loadMacro"),
    ("portfolioPage", "loadPortfolio"),
    ("geopoliticsPage", "loadGeopolitics"),
    ("evaluation", "loadEvaluation"),
    ("alerts", "loadAlerts"),
    ("providersPage", "loadProviders"),
    ("screening", "loadScreening"),
    ("sources", "loadSources"),
    ("inbox", "loadInbox"),
    ("markets", "loadMarkets"),
    ("operationsPage", "loadOperations"),
    ("archivePage", "loadArchive"),
    ("reportsPage", "loadReports"),
    ("settingsPage", "loadSettings"),
    ("aiChatPage", "loadAiChat"),
    ("iranPage", "loadIranBrief"),
    ("evidence", "loadEvidence"),
    ("debate", "loadDebate"),
    ("risk", "loadRisk"),
    ("forecasts", "loadForecasts"),
    ("decisions", "loadDecisions"),
    ("entityGraph", "loadGraph"),
)

_NODE_ASSERTIONS = """\
const assert = require('node:assert');

__HELPERS__

const hasPersianDigits = s => typeof s === 'string' && /[\\u06F0-\\u06F9]/.test(s);

assert.strictEqual(nfV(null), '\\u2014');
assert.strictEqual(nfV(undefined), '\\u2014');
assert.strictEqual(nfV('abc'), '\\u2014');
assert.strictEqual(nfV(NaN), '\\u2014');
assert.strictEqual(nfV(Infinity), '\\u2014');

const big = nfV(30769700000000);
assert.ok(/B$/.test(big), 'billions keep the B suffix: ' + big);
assert.ok(hasPersianDigits(big), 'billions use Persian digits: ' + big);
assert.ok(!/NaN/.test(big) && !big.includes('\\u0646\\u0627\\u0639\\u062F\\u062F'), 'no NaN text: ' + big);

const mid = nfV(2500000);
assert.ok(/M$/.test(mid) && hasPersianDigits(mid), 'millions keep the M suffix: ' + mid);

const small = nfV(0.04375);
assert.ok(!/[BM]$/.test(small), 'small values carry no suffix: ' + small);
assert.strictEqual(small, nf(0.04));
assert.ok(hasPersianDigits(small), 'small values use Persian digits: ' + small);

const negative = nfV(-1.2556766);
assert.ok(hasPersianDigits(negative) && !/[BM]$/.test(negative), 'negative value: ' + negative);
assert.ok(!/NaN/.test(negative), 'negative value never renders NaN: ' + negative);

assert.strictEqual(nfV('12.5'), nf(12.5), 'numeric strings format like numbers');
console.log('nf/nfV assertions OK');
"""


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def _function_body(html: str, name: str) -> str:
    """Return the source of `function name(` up to the next top-level function."""
    match = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", html)
    if match is None:
        return ""
    rest = html[match.end():]
    end = re.search(r"\n(?=(?:async\s+)?function\s)", rest)
    return html[match.start(): match.end() + (end.start() if end else len(rest))]


def _number_helpers(html: str) -> str:
    nf = re.search(r"const nf=n=>[^;]+;", html)
    nfv = re.search(r"const nfV=v=>\{.*?\};", html, re.S)
    assert nf is not None, "nf helper is missing"
    assert nfv is not None, "nfV helper is missing"
    for match in (nf, nfv):
        line_start = html.rfind("\n", 0, match.start()) + 1
        assert html[line_start] not in (" ", "\t"), (
            "nf/nfV must be declared at global scope, not inside another function"
        )
    return nf.group(0) + nfv.group(0)


def test_dedicated_pages_have_no_generic_fallback() -> None:
    html = _html()
    for page, _fn in DEDICATED_PAGES:
        pattern = re.compile(
            r"else if\(\[[^\]]*['\"]"
            + page
            + r"['\"][^\]]*\]\.includes\(activePage\)\)html=genericDomain\(activePage\);"
        )
        assert not pattern.search(html), f"{page} is overridden by genericDomain()"


def test_dedicated_pages_are_wired_into_render_page() -> None:
    html = _html()
    for page, fn in DEDICATED_PAGES:
        assert f"if(activePage==='{page}')html={fn}();" in html, f"{page} render branch missing"
        assert f"{page}:{fn}" in html, f"{page} missing from pageRenderers map"


def test_every_data_page_loader_targets_a_rendered_container() -> None:
    html = _html()
    broken = []
    for page_fn, loader_fn in PAGE_LOADERS:
        page_body = _function_body(html, page_fn)
        loader_body = _function_body(html, loader_fn)
        assert page_body, f"{page_fn}() not found in index.html"
        assert loader_body, f"{loader_fn}() not found in index.html"
        ids = set(re.findall(r'id="([^"]+)"', page_body))
        containers = re.findall(r"getElementById\('([^']+)'\)", loader_body)
        assert containers, f"{loader_fn}() has no container guard"
        if containers[0] not in ids:
            broken.append(f"{loader_fn}() -> #{containers[0]} missing from {page_fn}()")
    assert not broken, "loader/container mismatch: " + "; ".join(broken)


def test_render_page_only_schedules_defined_loaders() -> None:
    html = _html()
    body = _function_body(html, "renderPage")
    assert body, "renderPage() not found"
    scheduled: set[str] = set()
    for arg in re.findall(r"setTimeout\(([^,]+),", body):
        scheduled.update(re.findall(r"\b(load[A-Za-z0-9_]+)\b", arg))
    assert scheduled, "renderPage() schedules no loader"
    undefined = sorted(
        name
        for name in scheduled
        if not re.search(r"(?:async\s+)?function\s+" + name + r"\s*\(", html)
    )
    assert not undefined, f"renderPage() schedules undefined loaders: {undefined}"


def test_nf_suffix_is_applied_after_persian_formatting() -> None:
    html = _html()
    assert "nf(a>=1e9?(n/1e9)" not in html, (
        "suffix must be appended after Intl formatting, otherwise large values render as ناعدد"
    )
    definitions = re.findall(r"const nfV=v=>\{.*?\};", html, re.S)
    assert definitions, "nfV helper is missing"
    for definition in definitions:
        assert "nf(Number((n/1e9).toFixed(2)))" in definition, (
            "every nfV definition must format the numeric part before adding B/M"
        )


def test_number_helpers_format_persian_values(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available in this environment")
    script = tmp_path / "nf_check.js"
    script.write_text(
        _NODE_ASSERTIONS.replace("__HELPERS__", _number_helpers(_html())), encoding="utf-8"
    )
    result = subprocess.run([node, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-1500:]
