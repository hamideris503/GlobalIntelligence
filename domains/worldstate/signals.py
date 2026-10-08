"""Signal functions — pure deterministic mapping data → 0..1 signals (Phase 18).

قرارداد:
- هر سیگنال در بازه‌ی [0, 1] است؛ 0.5 یعنی خنثی/نامشخص.
- هر تابع `(value, method, confidence)` برمی‌گرداند.
- نبود داده → مقدار 0.5 با confidence پایین و method=`no_data` (نه عدد جعلی).
- بدون AI؛ فقط ریاضیات قطعی. تفسیر با LLM در فازهای بعد.

نگاشت‌ها (v1, مستند و ثابت):
- growth_pressure: رشد YoY تولید → (g+0.05)/0.10 (منفی ۵٪→۰، مثبت ۵٪→۱)
- inflation_pressure: تورم سالانه → x/10 (۰٪→۰، ۱۰٪→۱)
- liquidity: تغییر YoY نقدینگی → 0.5 + yoy*2 (انقباض→۰، انبساط→۱)
- financial_stress: میانگین استرس اعتباری (US10Y/10) و استرس سهامی (drawdown)
- geopolitical_risk: 0.3 پایه + 0.4*سهم ادعاهای موردمناقشه + 0.3*میانگین غافلگیری
- energy_risk: میانگین نرمال‌شده‌ی WTI/Brent در بازه‌ی ۵۰ تا ۱۵۰ دلار
- trade_risk: تراز تجاری (٪GDP) → 0.5 - value/20 (مازاد→کم‌ریسک)
- political_risk: 0.2 + 0.8*سهم رویدادهای سیاسی
- social_pressure: 0.2 + 0.8*سهم رویدادهای اجتماعی
"""
from __future__ import annotations

from dataclasses import dataclass

POLITICAL_TYPES = frozenset(
    {"election", "coup", "policy", "sanction", "government", "parliament", "referendum"}
)
POLITICAL_TOPICS = frozenset(
    {"politics", "election", "government", "policy", "sanctions", "diplomacy"}
)
SOCIAL_TYPES = frozenset({"protest", "strike", "unrest", "riot", "migration"})
SOCIAL_TOPICS = frozenset(
    {"protest", "society", "labor", "migration", "unrest", "human_rights"}
)
CONFLICT_TYPES = frozenset({"conflict", "war", "attack", "terrorism", "military"})


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass(frozen=True)
class Signal:
    value: float
    method: str
    confidence: float


def no_data() -> Signal:
    return Signal(value=0.5, method="no_data", confidence=0.1)


def growth_pressure(yoy: float | None) -> Signal:
    """فشار رشد از رشد سالانه‌ی GDP (کسری، مثلاً 0.03)."""
    if yoy is None:
        return no_data()
    return Signal(
        value=_clamp01((yoy + 0.05) / 0.10),
        method="gdp_yoy_linear",
        confidence=0.7,
    )


def inflation_pressure(cpi: float | None) -> Signal:
    """فشار تورمی از تورم سالانه (درصد، مثلاً 2.95)."""
    if cpi is None:
        return no_data()
    return Signal(value=_clamp01(cpi / 10.0), method="cpi_over_10", confidence=0.7)


def liquidity(yoy: float | None) -> Signal:
    """نقدینگی از تغییر سالانه (کسری)."""
    if yoy is None:
        return no_data()
    return Signal(
        value=_clamp01(0.5 + yoy * 2.0), method="liquidity_yoy", confidence=0.6
    )


def financial_stress(yield_10y: float | None, equity_drawdown: float | None) -> Signal:
    """استرس مالی از بازده ۱۰ساله (درصد) و افت شاخص (کسری مثبت)."""
    parts: list[float] = []
    if yield_10y is not None:
        parts.append(_clamp01(yield_10y / 10.0))
    if equity_drawdown is not None:
        parts.append(_clamp01(equity_drawdown / 0.20))
    if not parts:
        return no_data()
    return Signal(
        value=sum(parts) / len(parts),
        method="yield_drawdown_mean",
        confidence=0.6 if len(parts) == 2 else 0.4,
    )


def geopolitical_risk(
    disputed_share: float | None, avg_surprise: float | None, n_events: int
) -> Signal:
    """ریسک ژئوپلیتیک از سهم ادعاهای موردمناقشه و میانگین غافلگیری رویدادها."""
    if n_events == 0:
        return no_data()
    d = disputed_share if disputed_share is not None else 0.0
    s = avg_surprise if avg_surprise is not None else 0.0
    return Signal(
        value=_clamp01(0.3 + 0.4 * d + 0.3 * _clamp01(s)),
        method="dispute_surprise_mix",
        confidence=0.6,
    )


def energy_risk(wti: float | None, brent: float | None) -> Signal:
    """ریسک انرژی از قیمت نفت (۵۰→۰، ۱۵۰→۱)."""
    parts = [_clamp01((p - 50.0) / 100.0) for p in (wti, brent) if p is not None]
    if not parts:
        return no_data()
    return Signal(
        value=sum(parts) / len(parts),
        method="oil_band_50_150",
        confidence=0.7 if len(parts) == 2 else 0.5,
    )


def trade_risk(balance_pct_gdp: float | None) -> Signal:
    """ریسک تجاری از تراز تجاری (٪GDP؛ مازاد→کم‌ریسک)."""
    if balance_pct_gdp is None:
        return no_data()
    return Signal(
        value=_clamp01(0.5 - balance_pct_gdp / 20.0),
        method="trade_balance_gdp",
        confidence=0.6,
    )


def political_risk(share: float | None, n_events: int) -> Signal:
    """ریسک سیاسی از سهم رویدادهای سیاسی."""
    if n_events == 0 or share is None:
        return no_data()
    return Signal(value=_clamp01(0.2 + 0.8 * share), method="event_share", confidence=0.5)


def social_pressure(share: float | None, n_events: int) -> Signal:
    """فشار اجتماعی از سهم رویدادهای اجتماعی."""
    if n_events == 0 or share is None:
        return no_data()
    return Signal(value=_clamp01(0.2 + 0.8 * share), method="event_share", confidence=0.5)


def macro_regime(growth: float, inflation: float) -> str:
    """رژیم کلان از ربع‌بندی رشد×تورم (آستانه‌ی 0.5)."""
    if growth >= 0.5 and inflation >= 0.5:
        return "overheating"
    if growth >= 0.5:
        return "expansion"
    if inflation >= 0.5:
        return "stagflation"
    return "slowdown"


def market_regime(stress: float, liquidity_v: float) -> str:
    """رژیم بازار از استرس و نقدینگی."""
    if stress >= 0.7:
        return "stress"
    if stress <= 0.3 and liquidity_v >= 0.5:
        return "risk_on"
    if liquidity_v < 0.3:
        return "tight"
    return "neutral"


__all__ = [
    "CONFLICT_TYPES",
    "POLITICAL_TOPICS",
    "POLITICAL_TYPES",
    "SOCIAL_TOPICS",
    "SOCIAL_TYPES",
    "Signal",
    "energy_risk",
    "financial_stress",
    "geopolitical_risk",
    "growth_pressure",
    "inflation_pressure",
    "liquidity",
    "macro_regime",
    "market_regime",
    "no_data",
    "political_risk",
    "social_pressure",
    "trade_risk",
]
