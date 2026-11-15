"""قرارداد ناوبری UI: URL، deep-link و پوشش همهٔ صفحات (WP-05.1).

پیش از این، `renderPage` هیچ اثری در URL نداشت: ناوبری با `data-page` و بدون
hash انجام می‌شد، بنابراین refresh صفحه را به overview برمی‌گرداند و
back/forward کار نمی‌کرد. این تست آن قرارداد را قفل می‌کند.
"""
from __future__ import annotations

import re
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "backend" / "static" / "index.html"


def _html() -> str:
    return UI.read_text(encoding="utf-8", errors="ignore")


def _registry_pages(html: str) -> list[str]:
    reg = re.search(r"const pages=\{(.*?)\n\};", html, re.S)
    assert reg, "رجیستری pages پیدا نشد"
    return re.findall(r"^'([a-z\-]+)':", reg.group(1), re.M)


def test_page_from_hash_validates_against_registry() -> None:
    html = _html()
    fn = re.search(r"function giPageFromHash\(\)\{(.*?)\n\}", html, re.S)
    assert fn, "giPageFromHash تعریف نشده است"
    assert "pages[m[1]]" in fn.group(1), "hash باید فقط صفحه‌های ثبت‌شده را بپذیرد"


def test_render_page_syncs_url_and_supports_back_forward() -> None:
    html = _html()
    assert "giSyncUrl(next)" in html, "renderPage آدرس را همگام نمی‌کند"
    assert "history.pushState" in html, "ورود به هر صفحه باید ورودی تاریخچه بسازد"
    assert "addEventListener('popstate'" in html, "back/forward پشتیبانی نمی‌شود"
    assert "giUrlSyncPaused" in html, "حلقهٔ بازگشتی popstate↔render باید مهار شود"


def test_boot_honors_deep_link() -> None:
    html = _html()
    assert "renderPage(giPageFromHash()||'overview')" in html, (
        "بارگذاری اولیه باید صفحهٔ hash را باز کند، نه همیشه overview"
    )
    assert "renderPage(activePage || giPageFromHash() || 'overview')" in html


def test_every_registry_page_has_a_renderer() -> None:
    html = _html()
    pages = _registry_pages(html)
    assert len(pages) == 25, f"تعداد صفحه‌ها تغییر کرده: {len(pages)}"

    renderers = re.search(r"const pageRenderers=\{(.*?)\};", html, re.S)
    assert renderers, "pageRenderers پیدا نشد"
    # هر عضو یا `key:value` است یا shorthand (`debate`).
    mapped = {
        entry.split(":", 1)[0].strip().strip("'\"")
        for entry in renderers.group(1).split(",")
        if entry.strip()
    }
    branches = set(re.findall(r"if\(activePage==='([a-z\-]+)'\)", html))
    covered = mapped | branches
    missing = [p for p in pages if p not in covered]
    assert missing == [], f"صفحه‌های بدون renderer: {missing}"


def test_no_dead_data_actions() -> None:
    """هر دکمهٔ `data-action` باید در delegation واقعاً handler داشته باشد.

    پیش از WP-05.2 پنج دکمه (`debate`, `analysis`, `void`, `ack`, `filter`)
    کلیک‌پذیر بودند اما هیچ کاری نمی‌کردند.
    """
    html = _html()
    used = set(re.findall(r'data-action="([a-zA-Z]+)"', html))
    handled = set(re.findall(r"a==='([a-zA-Z]+)'", html))
    assert used - handled == set(), f"دکمه‌های بدون handler: {sorted(used - handled)}"


def test_unavailable_actions_are_disabled_not_fake() -> None:
    """قابلیت بدون API باید صریحاً غیرفعال/علامت‌خورده باشد، نه نمایشی."""
    html = _html()
    assert "NOT_CONNECTED" in html
    assert 'disabled aria-disabled="true"' in html


def test_evidence_filter_is_local_and_wired() -> None:
    html = _html()
    assert 'id="evidenceFilter"' in html
    assert 'onchange="giSetEvidenceFilter(this.value)"' in html
    assert "function giFilterClaims(" in html
    # فیلتر باید روی دادهٔ کش‌شده/دریافتی اعمال شود، نه با فراخوانی یک endpoint ناموجود.
    assert "/api/claims?" not in html or "giFilterClaims(claims)" in html
    assert "giFilterClaims(claims)" in html


def test_claim_status_bucket_is_token_exact() -> None:
    """«unverified» نباید در سبد «verified» بیفتد (باگ واقعی که در WP-05.3 دیده شد)."""
    html = _html()
    start = html.index("function giClaimStatusBucket(")
    body = html[start : start + 900]
    assert "split(/[^a-z]+/)" in body, "تطبیق باید توکنی باشد نه زیررشته"


def test_markets_fetch_is_wired_to_backend() -> None:
    html = _html()
    assert 'data-action="marketsFetch"' in html
    assert "POST','/api/markets/fetch'" in html


def test_unknown_hash_falls_back_to_overview() -> None:
    html = _html()
    assert "const next=pages[id]?id:'overview';" in html


def test_inline_scripts_parse() -> None:
    """هر بلوک <script> باید از نظر نحوی سالم باشد.

    این تنها بررسی اجراییِ رابط بدون مرورگر است؛ اگر node در دسترس نباشد
    آزمون به‌صورت skip ثبت می‌شود، نه pass.
    """
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node در دسترس نیست؛ بررسی نحو JS اجرا نشد")

    html = _html()
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    assert blocks, "هیچ بلوک script پیدا نشد"
    tmpdir = Path(tempfile.mkdtemp(prefix="gi-ui-check-"))
    for i, block in enumerate(blocks):
        target = tmpdir / f"block{i}.js"
        target.write_text(block, encoding="utf-8")
        result = subprocess.run([node, "--check", str(target)], capture_output=True, text=True)
        assert result.returncode == 0, f"خطای نحو در script block {i}: {result.stderr[-400:]}"
