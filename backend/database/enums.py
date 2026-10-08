"""انواع شمارشی مشترک (Enums) در دامنه‌ی داده."""
from __future__ import annotations

import enum


class SourceType(str, enum.Enum):
    rss = "rss"
    api = "api"
    dataset = "dataset"
    official = "official"
    scrape = "scrape"
    manual = "manual"
    other = "other"


class VerificationStatus(str, enum.Enum):
    unverified = "unverified"
    single_source = "single_source"
    corroborated = "corroborated"
    contradicted = "contradicted"
    disputed = "disputed"


class EntityType(str, enum.Enum):
    person = "person"
    country = "country"
    company = "company"
    organization = "organization"
    government = "government"
    central_bank = "central_bank"
    asset = "asset"
    commodity = "commodity"
    currency = "currency"
    industry = "industry"
    political_party = "political_party"
    event = "event"
    indicator = "indicator"
    other = "other"


class RelationType(str, enum.Enum):
    owns = "owns"
    controls = "controls"
    exports_to = "exports_to"
    depends_on = "depends_on"
    allies_with = "allies_with"
    sanctions = "sanctions"
    competes_with = "competes_with"
    supplies = "supplies"
    affects = "affects"
    invests_in = "invests_in"
    regulates = "regulates"
    other = "other"


class EvidenceDirection(str, enum.Enum):
    supports = "supports"
    contradicts = "contradicts"


class EconomicIndicator(str, enum.Enum):
    inflation = "inflation"
    gdp = "gdp"
    unemployment = "unemployment"
    interest_rate = "interest_rate"
    trade_balance = "trade_balance"
    liquidity = "liquidity"
    other = "other"


class DataFrequency(str, enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    other = "other"
