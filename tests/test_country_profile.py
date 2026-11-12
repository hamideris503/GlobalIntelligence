"""Tests for Country Profile (Stage 99)."""

from __future__ import annotations

import pytest

from domains.country_profile import get_profile, list_profiles, register_profile
from domains.country_profile.profile import CountryProfile
from domains.country_profile.registry import IR_PROFILE
from domains.iran import matching as mt


@pytest.fixture(autouse=True)
def _reset_active_profile():
    original = mt.get_active_profile()
    yield
    mt.set_active_profile(original)


def test_ir_profile_is_default():
    assert get_profile("IR") is IR_PROFILE
    assert IR_PROFILE.code == "IR"
    assert IR_PROFILE.macro_country_code == "IRN"


def test_ir_matching_unchanged():
    # behavior identical to before
    assert mt.is_iran_country("IR")
    assert mt.is_iran_country("irn")
    assert not mt.is_iran_country("US")
    assert mt.is_iran_name("Iran")
    assert mt.is_iran_name("iranian")
    assert not mt.is_iran_name("China")
    assert mt.is_iran_target("IRN oil")
    assert mt.is_iran_source("Iran Daily", None)
    assert mt.is_iran_source(None, "example.ir")


def test_second_country_via_config_only():
    # Add a second country without changing engine code
    cn = CountryProfile(
        code="CN",
        country_codes=frozenset({"CN", "CHN"}),
        name_keywords=frozenset({"china", "chinese"}),
        target_keywords=("chn", "china"),
        source_domain_suffixes=(".cn",),
        macro_country_code="CHN",
        version="v1",
    )
    register_profile(cn)
    assert get_profile("CN") is cn
    assert get_profile("cn") is cn  # case-insensitive
    # matching works for the new profile
    assert cn.matches_country("CN")
    assert cn.matches_country("chn")
    assert cn.matches_name("China")
    assert cn.matches_name("chinese")
    assert not cn.matches_name("Iran")
    assert cn.matches_target("CHN index")
    assert cn.matches_source("China Daily", None)
    assert cn.matches_source(None, "news.cn")
    assert not cn.matches_source("Iran", "example.com")
    # profile version recorded
    assert cn.as_dict()["version"] == "v1"
    # IR still works
    assert get_profile("IR") is IR_PROFILE


def test_profile_not_found():
    assert get_profile("ZZ") is None


def test_list_profiles_includes_ir():
    codes = {p.code for p in list_profiles()}
    assert "IR" in codes


def test_profile_switching_keeps_ir_default():
    # switching active profile and restoring
    cn = CountryProfile(
        code="CN",
        country_codes=frozenset({"CN", "CHN"}),
        name_keywords=frozenset({"china", "chinese"}),
        target_keywords=("chn", "china"),
        source_domain_suffixes=(".cn",),
        macro_country_code="CHN",
        version="v1",
    )
    register_profile(cn)
    original = mt.get_active_profile()
    mt.set_active_profile(cn)
    assert mt.is_iran_country("CN")
    assert not mt.is_iran_country("IR")
    mt.set_active_profile(original)
    assert mt.is_iran_country("IR")
    assert not mt.is_iran_country("CN")
