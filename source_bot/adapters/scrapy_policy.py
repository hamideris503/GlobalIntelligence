"""سیاست اتصال Scrapy — دو لایه روی **هر** درخواست، تا خودِ اتصال.

لایه ۱ (`ConnectionPolicyMiddleware`): هر درخواست — URL شروع، لینک کشف‌شده،
robots.txt و مقصد redirect — پیش از اتصال با `connection_check` سنجیده می‌شود.
رد = `IgnoreRequest` (هیچ اتصالی).

لایه ۲ (`PolicyResolver`): Scrapy resolver خود را با `installResolver` روی
reactor نصب می‌کند و `HostnameEndpoint` نام را از همان resolver می‌گیرد؛ پس
IPی که `vetted_ip` تأیید می‌کند همان IPی است که سوکت به آن وصل می‌شود
(مقصد تأییدشده == مقصد اتصال) و پنجره‌ی DNS-rebinding در این مسیر بسته است.
TLS دست‌نخورده می‌ماند: SNI و بررسی hostname/Certificate از hostname اصلی URL
می‌آید، نه از IP.

seam تست آفلاین: `set_test_origin_hosts` فقط از `_crawl_worker` و فقط وقتی
تست‌ها صریح `authorized_origins` بدهند پر می‌شود؛ runner/تنظیمات/API هیچ‌وقت
مقدار نمی‌دهند، پس در production فهرست تهی و سیاست کامل است.

`assert_policy_settings` تنظیمات **مؤثر** را می‌سنجد: اگر `DNS_RESOLVER` یا
middleware سیاست با یک تنظیم ناسازگار (مثلاً env) جایگزین شده باشد، crawl روشن
متوقف می‌شود، نه اینکه بی‌صدا به مسیر بدون pin برگردد.

محدودیت باقی‌مانده: resolver مثل پیش‌فرض Scrapy فقط IPv4 را برمی‌گرداند؛ مقصدی
که فقط پاسخ AAAA دارد fail-closed است (هیچ اتصالی، فقط DNSLookupError).
"""
from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from scrapy.resolver import CachingThreadedResolver

from source_bot.security import connection_check, vetted_ip

# مسیر middleware سیاست (کلید تنظیمات اسکرپی — یک نقطه‌ی حقیقت)
MIDDLEWARE_PATH = "source_bot.adapters.scrapy_policy.ConnectionPolicyMiddleware"
PROXY_MIDDLEWARE_PATH = "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware"

# میزبان‌های originهای مجازِ تست آفلاین؛ پیش‌فرض تهی = سیاست کامل (production).
_test_origin_hosts: frozenset[str] = frozenset()


def set_test_origin_hosts(origins: Iterable[str] | None) -> None:
    """seam تست: میزبان‌های originهای محلی مجاز. بدون آرگومان ⇒ فهرست تهی."""
    global _test_origin_hosts
    hosts = set()
    for origin in origins or ():
        try:
            host = urlparse(str(origin)).hostname
        except Exception:  # noqa: BLE001
            host = None
        if host:
            hosts.add(host.lower())
    _test_origin_hosts = frozenset(hosts)


class ConnectionPolicyMiddleware:
    """هر درخواست را پیش از اتصال با `connection_check` می‌سنجد."""

    def process_request(self, request, spider):  # noqa: ANN001, ANN201 — امضای Scrapy
        from scrapy.exceptions import IgnoreRequest  # lazy: بدون وابستگی در import

        origins = tuple(getattr(spider, "authorized_origins", ()) or ())
        check = connection_check(getattr(request, "url", None), allow_origins=origins)
        if not check.ok:
            diag = getattr(spider, "diag", None)
            if isinstance(diag, dict):  # شمارش ردها برای تشخیص crawl کاملاً مسدود
                diag["blocked"] = diag.get("blocked", 0) + 1
            raise IgnoreRequest(f"blocked target: {check.reason}")
        return None


def assert_policy_settings(settings) -> None:  # noqa: ANN001 — Settings اسکرپی
    """تنظیمات مؤثر باید دقیقاً همان دو لایه‌ی سیاست باشند؛ وگرنه خطا (توقف اجرا).

    جایگزینی resolver/handler یا روشن‌کردن پروکسی، «مقصد تأییدشده == مقصد
    اتصال» را از بین می‌برد؛ اینجا روشن شکست می‌دهیم تا اجرا بی‌صدا بدون pin
    ادامه ندهد.
    """
    from scrapy.utils.misc import load_object

    resolver = settings.get("DNS_RESOLVER")
    try:
        obj = load_object(resolver) if isinstance(resolver, str) else resolver
    except Exception:  # noqa: BLE001
        obj = None
    if not (isinstance(obj, type) and issubclass(obj, PolicyResolver)):
        raise RuntimeError("unsafe crawl settings: DNS_RESOLVER is not PolicyResolver")
    middlewares = settings.getwithbase("DOWNLOADER_MIDDLEWARES")
    if not middlewares.get(MIDDLEWARE_PATH):
        raise RuntimeError("unsafe crawl settings: connection policy middleware missing")
    if middlewares.get(PROXY_MIDDLEWARE_PATH):
        # پروکسی محیطی اتصال را از IP تأییدشده دور می‌زند
        raise RuntimeError("unsafe crawl settings: proxy middleware enabled")
    if settings.getdict("DOWNLOAD_HANDLERS"):
        raise RuntimeError("unsafe crawl settings: custom download handlers")


class PolicyResolver(CachingThreadedResolver):
    """DNS resolver با سیاست SSRF؛ همان نتیجه‌ی resolve به اتصال می‌رود."""

    def getHostByName(self, name, timeout=()):  # noqa: ANN001, ANN201
        def vetted(ip):  # noqa: ANN001, ANN202
            return vetted_ip(ip, name, allow_hosts=_test_origin_hosts)

        # super() = کش/تایم‌اوت/تردپول Scrapy؛ سیاست روی همان مقدار اجرا می‌شود
        # (حتی روی cache hit)، پس اتصال به چیزی جز IP تأییدشده نمی‌رسد.
        # فقط IPv4 (خود Scrapy): نام با پاسخ تنها-AAAA ⇒ DNSLookupError، بدون اتصال.
        return super().getHostByName(name, timeout).addCallback(vetted)
