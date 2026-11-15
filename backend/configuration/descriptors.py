"""Configuration descriptor contract (F03.0 — الزام ۲.۱ و ۲.۴).

- یک قرارداد مشترک برای پیکربندی: فیلد، نوع، اجباری‌بودن، گزینه‌ها.
- رجیستری adapter (`source_bot.registry`) تنها منبع حقیقت است: فهرست adapterها
  و قابلیت preview از همان‌جا می‌آید و انتخاب adapter با `pick_adapter` انجام
  می‌شود؛ این ماژول منطق انتخاب را بازنویسی نمی‌کند.
- هیچ اتصال شبکه‌ای در این ماژول نیست (اعتبارسنجی URL فقط نحوی/سیاستی است).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from types import SimpleNamespace

from source_bot.registry import ADAPTERS, PREVIEW_ADAPTERS, pick_adapter
from source_bot.security import validate_url

from backend.configuration.errors import NeedsAdapter, UnknownKind

DESCRIPTOR_VERSION = "1"

SOURCE_TYPES = ("rss", "api", "dataset", "official", "scrape", "manual", "other")
COLLECTION_METHODS = ("rss", "api", "dataset", "scrape", "manual", "other")
GEOGRAPHIES = ("global", "country", "region")


@dataclass(frozen=True)
class FieldSpec:
    """یک فیلد قابل‌پیکربندی؛ `secret` یعنی مقدار هرگز در پاسخ برنمی‌گردد."""

    name: str
    label: str
    kind: str  # text | url | bool | enum | json
    required: bool = False
    choices: tuple[str, ...] = ()
    max_length: int | None = None
    secret: bool = False
    help: str = ""


@dataclass(frozen=True)
class Descriptor:
    """قرارداد یک kind قابل‌پیکربندی.

    `adapter_state` تنها دو مقدار مجاز دارد:
    - ``ready``: descriptor + validation + تست/activation + مصرف‌کنندهٔ runtime دارد.
    - ``needs_adapter``: گروه تنظیمات شناخته شده است اما adapter/مصرف‌کننده ندارد؛
      فقط برای نمایش صادقانه برگردانده می‌شود و ذخیرهٔ پیکربندی برایش ممکن نیست.
    """

    kind: str
    label: str
    version: str
    fields: tuple[FieldSpec, ...]
    adapters: tuple[str, ...] = ()
    preview_adapters: tuple[str, ...] = ()
    adapter_state: str = "ready"
    note: str = ""

    @property
    def creatable(self) -> bool:
        return self.adapter_state == "ready"

    def as_dict(self) -> dict:
        data = asdict(self)
        data["creatable"] = self.creatable
        return data


SOURCE_DESCRIPTOR = Descriptor(
    kind="source",
    label="Source configuration",
    version=DESCRIPTOR_VERSION,
    adapters=tuple(ADAPTERS),
    preview_adapters=tuple(PREVIEW_ADAPTERS),
    fields=(
        FieldSpec("name", "نام منبع", "text", required=True, max_length=255),
        FieldSpec("type", "نوع منبع", "enum", required=True, choices=SOURCE_TYPES),
        FieldSpec(
            "collection_method", "روش جمع‌آوری", "enum",
            required=True, choices=COLLECTION_METHODS,
        ),
        FieldSpec("feed_url", "نشانی فید RSS", "url", max_length=2048),
        FieldSpec("rss_url", "نشانی RSS جایگزین", "url", max_length=2048),
        FieldSpec("api_url", "نشانی API", "url", max_length=2048),
        FieldSpec("homepage_url", "نشانی صفحهٔ اصلی", "url", max_length=2048),
        FieldSpec("data_download_url", "نشانی دانلود داده", "url", max_length=2048),
        FieldSpec(
            "endpoint_config", "پیکربندی endpoint (JSON)", "json",
            help="کلید فقط با نام متغیر محیطی؛ مقدار secret هرگز ذخیره نمی‌شود",
        ),
        FieldSpec("category", "دسته", "text", max_length=64),
        FieldSpec("geography", "دامنهٔ جغرافیایی", "enum", choices=GEOGRAPHIES),
        FieldSpec("active", "فعال", "bool"),
    ),
)

_REGISTRY: dict[str, Descriptor] = {SOURCE_DESCRIPTOR.kind: SOURCE_DESCRIPTOR}

# گروه‌های تنظیمات که هنوز adapter/مصرف‌کنندهٔ runtime ندارند (WP-06 بند ۱۲).
# این‌ها فقط برای نمایش صادقانه در UI هستند: هیچ instance/revision برایشان ساخته
# نمی‌شود و هیچ secretی در این مسیر ذخیره نمی‌گردد. گروه‌هایی که مصرف‌کنندهٔ
# موجود دارند در همین لیست نیستند (AI Providers → /api/settings/providers،
# General/Processing → /api/settings/app، Archive/Retention → /api/retention).
NEEDS_ADAPTER_KINDS: dict[str, tuple[str, str]] = {
    "email": (
        "Email / SMTP",
        "پیکربندی از env خوانده می‌شود (SMTP_*)؛ adapter تنظیمات و تست بدون ارسال واقعی ندارد.",
    ),
    "telegram": (
        "Telegram",
        "ارسال از env خوانده می‌شود (TELEGRAM_*); مسیر test-deliver در /api/alerts جداگانه است.",
    ),
    "scheduling": (
        "Scheduling",
        "زمان‌بندی Jobها در این نسخه از n8n/BackgroundTasks می‌آید؛ adapter پیکربندی ندارد.",
    ),
    "ui_preferences": (
        "UI Preferences",
        "ترجیحات UI در localStorage مرورگر است، نه پیکربندی سرور.",
    ),
    "access_security": (
        "Access / Security",
        "سیاست‌های امنیتی از env و /api/auth کنترل می‌شوند؛ adapter پیکربندی ندارد.",
    ),
}


def needs_adapter_definitions() -> list[dict]:
    """تعریف‌های نمایشی برای kindهای بدون adapter (بدون فیلد قابل‌ذخیره)."""
    return [
        {
            "kind": kind,
            "label": label,
            "version": DESCRIPTOR_VERSION,
            "fields": [],
            "adapters": [],
            "preview_adapters": [],
            "adapter_state": "needs_adapter",
            "creatable": False,
            "note": note,
        }
        for kind, (label, note) in NEEDS_ADAPTER_KINDS.items()
    ]

_URL_FIELDS = ("feed_url", "rss_url", "api_url", "homepage_url", "data_download_url")


def all_definitions() -> list[dict]:
    """همهٔ descriptorها برای مصرف UI/کلاینت (ready + needs_adapter)."""
    ready = [d.as_dict() for d in _REGISTRY.values()]
    return ready + needs_adapter_definitions()


def definition(kind: str) -> Descriptor:
    desc = _REGISTRY.get(kind)
    if desc is not None:
        return desc
    if kind in NEEDS_ADAPTER_KINDS:
        raise NeedsAdapter(
            f"configuration kind '{kind}' has no adapter (NEEDS_ADAPTER); "
            "it cannot be stored from the control plane"
        )
    raise UnknownKind(f"unknown configuration kind: {kind}")


SECRET_VALUE_PREFIXES = ("sk-", "ghp_", "AIza", "Bearer ")


def _looks_like_secret(value: object) -> bool:
    return isinstance(value, str) and value.startswith(SECRET_VALUE_PREFIXES)


def redact(kind: str, payload: dict) -> dict:
    """حذف مقدار فیلدهای secret از payload خروجی.

    علاوه بر فیلدهای `secret`، مقدار `endpoint_config.api_key_env` هم اگر شبیه
    کلید باشد (نه نام متغیر env) ماسک می‌شود؛ وگرنه همان مقداری که validation
    رد می‌کند از مسیر GET بازخوانی و افشا می‌شد.
    """
    desc = _REGISTRY.get(kind)
    if desc is None:
        return dict(payload)
    secret_names = {f.name for f in desc.fields if f.secret}
    out: dict = {}
    for k, v in payload.items():
        if k in secret_names and v not in (None, ""):
            out[k] = "***"
        elif k == "endpoint_config" and isinstance(v, dict):
            cfg = dict(v)
            if _looks_like_secret(cfg.get("api_key_env")):
                cfg["api_key_env"] = "***"
            out[k] = cfg
        else:
            out[k] = v
    return out


def resolve_adapter(payload: dict) -> dict:
    """انتخاب adapter با همان تابع رجیستری (بدون بازنویسی منطق)."""
    cfg = payload.get("endpoint_config")
    endpoint_config = (
        json.dumps(cfg, ensure_ascii=False) if isinstance(cfg, dict) else None
    )
    source_like = SimpleNamespace(
        name=payload.get("name") or "",
        type=payload.get("type") or "other",
        collection_method=payload.get("collection_method") or "",
        feed_url=payload.get("feed_url"),
        rss_url=payload.get("rss_url"),
        api_url=payload.get("api_url"),
        homepage_url=payload.get("homepage_url"),
        data_download_url=payload.get("data_download_url"),
        endpoint_config=endpoint_config,
    )
    plan = pick_adapter(source_like)
    return {"adapter": plan.adapter, "url": plan.url, "reason": plan.reason}


def _issue(field_name: str, code: str, message: str) -> dict:
    return {"field": field_name, "code": code, "message": message}


def _blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _check_field(spec: FieldSpec, value: object) -> list[dict]:
    issues: list[dict] = []
    if spec.kind == "text":
        if not isinstance(value, str):
            issues.append(_issue(spec.name, "type", f"{spec.label} must be a string"))
        elif spec.max_length and len(value) > spec.max_length:
            issues.append(
                _issue(spec.name, "too_long", f"{spec.label} exceeds {spec.max_length} chars")
            )
    elif spec.kind == "url":
        if not isinstance(value, str):
            issues.append(_issue(spec.name, "type", f"{spec.label} must be a string"))
        else:
            check = validate_url(value)
            if not check.ok:
                issues.append(
                    _issue(spec.name, "unsafe_url", f"{spec.label}: {check.reason}")
                )
    elif spec.kind == "enum":
        if not isinstance(value, str) or value not in spec.choices:
            issues.append(
                _issue(spec.name, "bad_choice", f"{spec.label} must be one of {list(spec.choices)}")
            )
    elif spec.kind == "bool":
        if not isinstance(value, bool):
            issues.append(_issue(spec.name, "type", f"{spec.label} must be a boolean"))
    elif spec.kind == "json":
        if not isinstance(value, dict):
            issues.append(_issue(spec.name, "type", f"{spec.label} must be an object"))
        else:
            key_env = value.get("api_key_env")
            if key_env is not None and not isinstance(key_env, str):
                issues.append(
                    _issue(spec.name, "type", "api_key_env must be an env var name")
                )
            if isinstance(key_env, str) and key_env.startswith(
                ("sk-", "ghp_", "AIza", "Bearer ")
            ):
                # مقدار secret به‌جای نام متغیر: رد می‌شود، ذخیره نمی‌شود.
                issues.append(
                    _issue(spec.name, "secret_value", "api_key_env must be a var name, not a key")
                )
    return issues


def validate(kind: str, payload: object) -> dict:
    """اعتبارسنجی قطعی و بدون I/O؛ خروجی همیشه JSON-serializable است."""
    desc = definition(kind)
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "issues": [_issue("payload", "not_object", "payload must be an object")],
            "adapter": None,
            "url_origin": None,
            "descriptor_version": desc.version,
        }
    specs = {f.name: f for f in desc.fields}
    issues: list[dict] = [
        _issue(key, "unknown_field", f"unknown field: {key}")
        for key in payload
        if key not in specs
    ]
    for spec in desc.fields:
        value = payload.get(spec.name)
        if _blank(value):
            if spec.required:
                issues.append(_issue(spec.name, "required", f"{spec.label} is required"))
            continue
        issues.extend(_check_field(spec, value))
    if issues:
        return {
            "ok": False,
            "issues": issues,
            "adapter": None,
            "url_origin": None,
            "descriptor_version": desc.version,
        }
    plan = resolve_adapter(payload)
    if plan["adapter"] == "skip":
        issues.append(
            _issue("endpoint", "no_usable_endpoint", plan["reason"] or "no usable endpoint")
        )
    return {
        "ok": not issues,
        "issues": issues,
        "adapter": plan["adapter"],
        "url_origin": _origin(plan["url"]),
        "descriptor_version": desc.version,
    }


def _origin(url: str | None) -> str | None:
    """فقط scheme://host[:port]؛ مسیر/کوئری (احتمال توکن) افشا نمی‌شود."""
    from source_bot.security import url_origin

    return url_origin(url) or None


__all__ = [
    "COLLECTION_METHODS",
    "DESCRIPTOR_VERSION",
    "FieldSpec",
    "Descriptor",
    "NEEDS_ADAPTER_KINDS",
    "SOURCE_DESCRIPTOR",
    "all_definitions",
    "definition",
    "needs_adapter_definitions",
    "redact",
    "resolve_adapter",
    "validate",
]
