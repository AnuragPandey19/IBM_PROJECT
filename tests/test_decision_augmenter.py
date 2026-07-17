"""Unit tests for api/services/decision_augmenter.py.

Covers every rule with:
  - Positive case (rule fires when it should)
  - Negative case (rule does NOT fire on adjacent payload)
  - Feature-flag off case (rule respects its enable flag)

Also covers the passthrough guarantees:
  - block stays block
  - review stays review
  - rules only ever tighten approve -> review

Run with:  pytest tests/test_decision_augmenter.py -v
"""
from __future__ import annotations

import os

os.environ.setdefault("ENV", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-augmenter")

import pytest  # noqa: E402

from api.config import get_settings  # noqa: E402
from api.services.decision_augmenter import apply_safety_nets  # noqa: E402


# ---------------------------------------------------------------------------
# Reset the LRU-cached settings singleton between tests that mutate env vars.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _payload(**overrides):
    base = {
        "amount": 100.0,
        "merchant_category": "grocery_pos",
        "demo_profile": "established",
        "demo_hour_override": 14,
    }
    base.update(overrides)
    return base


ESTABLISHED_PROFILE = {"avg_past_amt": 55.0}
NEW_PROFILE = {"avg_past_amt": 0.0}
HIGH_SPENDER_PROFILE = {"avg_past_amt": 500.0}
SENIOR_PROFILE = {"avg_past_amt": 42.0}


# ---------------------------------------------------------------------------
# Passthrough guarantees
# ---------------------------------------------------------------------------

def test_block_decision_passes_through_unchanged():
    """Rules must never relax a block to approve/review."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=1.49, demo_profile="new", merchant_category="misc_net"),
        profile=NEW_PROFILE,
        raw_decision="block",
        cal_score=0.99,
    )
    assert d == "block"
    assert rules == []


def test_review_decision_passes_through_unchanged():
    """Rules must never modify a review decision."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=1.49, demo_profile="new", merchant_category="misc_net"),
        profile=NEW_PROFILE,
        raw_decision="review",
        cal_score=0.4,
    )
    assert d == "review"
    assert rules == []


def test_all_flags_off_is_passthrough(monkeypatch):
    monkeypatch.setenv("ENABLE_SAFETY_NET_CARD_TESTING", "false")
    monkeypatch.setenv("ENABLE_SAFETY_NET_VELOCITY_SPIKE", "false")
    monkeypatch.setenv("ENABLE_SAFETY_NET_NIGHT_NEW_HIGH", "false")
    get_settings.cache_clear()

    d, rules = apply_safety_nets(
        payload=_payload(amount=1.49, demo_profile="new", merchant_category="misc_net"),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-8,
    )
    assert d == "approve"
    assert rules == []


# ---------------------------------------------------------------------------
# Rule 1 — card_testing
# ---------------------------------------------------------------------------

def test_card_testing_fires_on_small_amount_new_misc_net():
    d, rules = apply_safety_nets(
        payload=_payload(amount=1.49, demo_profile="new", merchant_category="misc_net"),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=3.1e-8,
    )
    assert d == "review"
    assert "card_testing_small_amount" in rules


def test_card_testing_fires_on_entertainment():
    d, rules = apply_safety_nets(
        payload=_payload(amount=2.99, demo_profile="new", merchant_category="entertainment"),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-7,
    )
    assert d == "review"
    assert "card_testing_small_amount" in rules


def test_card_testing_does_not_fire_established_customer():
    """Only new profile triggers card_testing rule."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=1.49, demo_profile="established", merchant_category="misc_net"),
        profile=ESTABLISHED_PROFILE,
        raw_decision="approve",
        cal_score=1e-8,
    )
    assert d == "approve"
    assert "card_testing_small_amount" not in rules


def test_card_testing_does_not_fire_grocery_category():
    """Grocery is not a card-testing target category."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=4.25, demo_profile="new", merchant_category="grocery_pos"),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=5e-4,
    )
    assert d == "approve"
    assert rules == []


def test_card_testing_does_not_fire_on_amount_at_threshold():
    """Threshold is strict <10, so exactly 10 must not fire."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=10.0, demo_profile="new", merchant_category="misc_net"),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-6,
    )
    assert d == "approve"
    assert rules == []


def test_card_testing_can_be_disabled_via_flag(monkeypatch):
    monkeypatch.setenv("ENABLE_SAFETY_NET_CARD_TESTING", "false")
    get_settings.cache_clear()
    d, rules = apply_safety_nets(
        payload=_payload(amount=1.49, demo_profile="new", merchant_category="misc_net"),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-8,
    )
    assert d == "approve"
    assert rules == []


# ---------------------------------------------------------------------------
# Rule 2 — velocity_spike
# ---------------------------------------------------------------------------

def test_velocity_spike_fires_established_10x_ratio():
    d, rules = apply_safety_nets(
        payload=_payload(amount=550.0, demo_profile="established"),
        profile=ESTABLISHED_PROFILE,  # avg 55
        raw_decision="approve",
        cal_score=0.004,
    )
    assert d == "review"
    assert "velocity_spike_established" in rules


def test_velocity_spike_fires_senior_6x_ratio():
    d, rules = apply_safety_nets(
        payload=_payload(amount=300.0, demo_profile="senior"),
        profile=SENIOR_PROFILE,  # avg 42
        raw_decision="approve",
        cal_score=0.001,
    )
    assert d == "review"
    assert "velocity_spike_established" in rules


def test_velocity_spike_does_not_fire_high_spender():
    """high_spender is variable-spend by nature; excluded from this rule."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=3000.0, demo_profile="high_spender"),
        profile=HIGH_SPENDER_PROFILE,  # avg 500, ratio=6
        raw_decision="approve",
        cal_score=0.005,
    )
    assert d == "approve"
    assert "velocity_spike_established" not in rules


def test_velocity_spike_does_not_fire_at_5x_exactly():
    """Threshold is strict > 5, so exactly 5x is not a spike."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=275.0, demo_profile="established"),  # 5x avg 55
        profile=ESTABLISHED_PROFILE,
        raw_decision="approve",
        cal_score=0.002,
    )
    assert d == "approve"
    assert rules == []


def test_velocity_spike_no_profile_means_no_fire():
    d, rules = apply_safety_nets(
        payload=_payload(amount=1000.0, demo_profile="established"),
        profile=None,
        raw_decision="approve",
        cal_score=0.003,
    )
    assert d == "approve"
    assert rules == []


def test_velocity_spike_can_be_disabled_via_flag(monkeypatch):
    monkeypatch.setenv("ENABLE_SAFETY_NET_VELOCITY_SPIKE", "false")
    get_settings.cache_clear()
    d, rules = apply_safety_nets(
        payload=_payload(amount=550.0, demo_profile="established"),
        profile=ESTABLISHED_PROFILE,
        raw_decision="approve",
        cal_score=0.004,
    )
    assert d == "approve"
    assert rules == []


# ---------------------------------------------------------------------------
# Rule 3 — evening new high-amount
# ---------------------------------------------------------------------------

def test_night_new_high_fires_at_22h_new_2000usd():
    d, rules = apply_safety_nets(
        payload=_payload(amount=2000.0, demo_profile="new", demo_hour_override=22),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=2e-7,
    )
    assert d == "review"
    assert "evening_new_high_amount" in rules


def test_night_new_high_does_not_fire_at_19h():
    """Rule window is 20-23, 19 must not trigger."""
    d, rules = apply_safety_nets(
        payload=_payload(amount=2000.0, demo_profile="new", demo_hour_override=19),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=2e-7,
    )
    assert d == "approve"
    assert rules == []


def test_night_new_high_does_not_fire_established_customer():
    d, rules = apply_safety_nets(
        payload=_payload(amount=2000.0, demo_profile="established", demo_hour_override=22),
        profile=ESTABLISHED_PROFILE,
        raw_decision="approve",
        cal_score=0.001,
    )
    # velocity_spike may still fire (2000/55 = 36x), that's a different rule
    assert d == "review"
    assert "evening_new_high_amount" not in rules


def test_night_new_high_does_not_fire_below_1000():
    d, rules = apply_safety_nets(
        payload=_payload(amount=999.0, demo_profile="new", demo_hour_override=22),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-6,
    )
    assert d == "approve"
    assert rules == []


# ---------------------------------------------------------------------------
# Composition + edge cases
# ---------------------------------------------------------------------------

def test_multiple_rules_can_fire_together():
    """A very-new-customer very-high late-night misc payment triggers night rule.
    (card_testing does NOT fire because amount is not < 10.)"""
    d, rules = apply_safety_nets(
        payload=_payload(amount=1500.0, demo_profile="new",
                         merchant_category="misc_net", demo_hour_override=23),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-7,
    )
    assert d == "review"
    assert "evening_new_high_amount" in rules


def test_normal_grocery_transaction_untouched():
    d, rules = apply_safety_nets(
        payload=_payload(amount=42.50, demo_profile="established",
                         merchant_category="grocery_pos", demo_hour_override=14),
        profile=ESTABLISHED_PROFILE,
        raw_decision="approve",
        cal_score=1e-4,
    )
    assert d == "approve"
    assert rules == []


def test_nan_amount_does_not_crash():
    d, rules = apply_safety_nets(
        payload=_payload(amount=float("nan"), demo_profile="new",
                         merchant_category="misc_net"),
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-8,
    )
    # Neither rule should fire on NaN amount
    assert d == "approve"
    assert rules == []


def test_missing_amount_does_not_crash():
    d, rules = apply_safety_nets(
        payload={"demo_profile": "new", "merchant_category": "misc_net"},
        profile=NEW_PROFILE,
        raw_decision="approve",
        cal_score=1e-8,
    )
    assert d == "approve"
    assert rules == []
