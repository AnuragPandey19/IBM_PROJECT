"""Post-model decision augmenter.

WHY THIS EXISTS
---------------
The V1+V2+V3 testing (150,714 rows across three independent authors)
established three systematic blind spots in the Sparkov Stage 1 LightGBM
model that a rule layer can plausibly close without retraining:

  - card_testing         (0.0% recall on 11,785 combined test rows)
  - velocity_spike       (5.0% recall on 12,678 combined)
  - evening new-customer (variable; ~66% recall on weekend_spike)

Rules in this module TAKE THE MODEL'S DECISION AS INPUT and can transform
it into a more conservative decision (approve -> review). They never
transform review -> block or block -> approve — the goal is calibrated
uncertainty, not overriding the model with a rule engine.

WHERE THIS IS CALLED FROM (single source of truth)
--------------------------------------------------
1. api/routes/checkout.py           (public gateway endpoint)
2. api/routes/predict_sparkov.py    (authenticated analyst API)
3. scripts/run_labeled_test_cases_direct.py  (the test runner)

All three sites import THIS function so the safety nets can never drift
between local, deployed, and direct-model-script environments. This is
the direct fix for the class of bugs discovered in the V3 audit
(cf. MODEL_AUDIT_POST_TESTING.md — issue B-2).

FEATURE FLAGS
-------------
Each rule is toggled by a boolean setting in `api.config.Settings`. Ops
can disable a rule via env var + factory rebuild without touching code:

  ENABLE_SAFETY_NET_CARD_TESTING=false
  ENABLE_SAFETY_NET_NIGHT_MICRO=false
  ENABLE_SAFETY_NET_VELOCITY_SPIKE=false
  ENABLE_SAFETY_NET_NIGHT_NEW_HIGH=false

If ALL flags are off, `apply_safety_nets` is a passthrough (returns the
raw model decision unchanged).
"""
from __future__ import annotations

from typing import Optional

from api.config import get_settings


# Categories where a tiny-amount transaction is a plausible card-verification
# attempt. Physical-POS categories excluded because chip+PIN makes them a
# poor card-testing vector.
_CARD_TESTING_TARGET_CATEGORIES = frozenset({
    "misc_net",         # online misc — the classic card-testing category
    "entertainment",    # streaming/gaming subscriptions
    "misc_pos",         # small in-store misc
    "personal_care",    # low-friction online personal-care merchants
})


# Categories with a hard empirical floor on legitimate LATE-NIGHT spending.
#
# DERIVATION (data/processed/sparkov/train_features.parquet, 1,481,915 rows —
# the model's own TRAINING distribution; the held-out Pankaj30m set was not
# consulted, see v2-chimera-fd/evaluation/RULE_CHANGE_PROPOSAL.md):
#
#   In the window hour 0-5, across 143,060 LEGITIMATE transactions:
#       gas_transport : n=74,886  minimum = $17.61   (p01 = $32.20)
#       grocery_pos   : n=68,174  minimum = $10.87   (p01 = $32.61)
#   Zero legitimate training transactions in these two categories fall
#   below $10.00 at night. A sub-$10 night transaction here is outside the
#   support of legitimate spending as the model was trained to see it.
#
#   grocery_net (min $1.44) and food_dining (min $1.06) are DELIBERATELY
#   EXCLUDED — legitimate night-time spending in those categories genuinely
#   reaches ~$1, so a low-amount rule there would fire on real customers.
#
# NOTE ON DIRECTION: this rule is NOT anchored on "small amount = fraud".
# Sparkov's training data contains no card testing whatsoever — the cheapest
# fraudulent night transaction in 1.48M rows is $5.60. The rule is anchored
# on the absence of legitimate traffic, which is measurable, rather than on
# the presence of fraud, which in this dataset is not.
_NIGHT_MICRO_CATEGORIES = frozenset({
    "gas_transport",
    "grocery_pos",
})


def apply_safety_nets(
    payload: dict,
    profile: Optional[dict],
    raw_decision: str,
    cal_score: float,
) -> tuple[str, list[str]]:
    """Apply post-model safety-net rules to a Sparkov decision.

    Parameters
    ----------
    payload : dict
        The 8-field checkout payload. Expected keys: amount, demo_profile,
        demo_hour_override, merchant_category. Other keys are ignored.
    profile : dict | None
        The resolved CUSTOMER_PROFILES entry, if any. Used for
        velocity-spike math (needs avg_past_amt). Pass None if unknown —
        velocity rule will simply not fire.
    raw_decision : str
        The model's raw decision: "approve" | "review" | "block".
    cal_score : float
        The calibrated fraud probability (0.0–1.0). Currently unused by
        the rules but accepted for future extensions.

    Returns
    -------
    (final_decision, triggered_rule_ids)
        final_decision : same type as raw_decision, potentially tightened.
        triggered_rule_ids : list of strings identifying which rules
            actually fired for this transaction. Empty if none.

    Behaviour guarantees
    --------------------
    * Rules NEVER relax a decision. block stays block; review stays review
      or moves to block only if a rule explicitly demands (currently no
      such rule exists).
    * Rules can ONLY move approve -> review. They cannot force a block.
      This preserves the "review" bucket as the conservative-uncertainty
      layer and avoids one bad rule causing legitimate customers to be
      declined.
    * If cal_score is not sensible (NaN, negative), rules still fire
      based on payload structure — the rules are structural, not
      score-dependent.
    """
    settings = get_settings()
    triggered: list[str] = []

    # Passthrough short-circuit — nothing to do for non-approve decisions.
    if raw_decision != "approve":
        return raw_decision, triggered

    amount = _safe_float(payload.get("amount"))
    demo_profile_key = payload.get("demo_profile")
    category = payload.get("merchant_category")
    hour = _safe_int(payload.get("demo_hour_override"))

    # -------- Rule 1: card_testing (small amount + new + suspicious cat) --
    # The `demo_profile == "new"` guard below looks removable — the post-3M
    # audit shows this rule firing zero times. It is NOT removable. In these
    # four categories, 32.6% of all LEGITIMATE training transactions are
    # under $10.00 and every category has a legit minimum of $1.00. Dropping
    # the profile guard would fire the rule on roughly a third of legitimate
    # traffic in these categories — the same failure mode as the 2026-07-18
    # augmentation regression. Widen the rule only with new evidence.
    if settings.enable_safety_net_card_testing:
        if (
            demo_profile_key == "new"
            and amount is not None
            and amount < settings.safety_net_card_testing_max_amount
            and category in _CARD_TESTING_TARGET_CATEGORIES
        ):
            triggered.append("card_testing_small_amount")

    # -------- Rule 4: late-night micro-amount (card_testing) --------------
    # Fires on transactions below the empirical floor of legitimate
    # night-time spending (see _NIGHT_MICRO_CATEGORIES for the derivation).
    # Intentionally profile-agnostic: the feasibility probe found
    # card_testing spread across `established` and `senior`, and the floor is
    # a property of the category and hour, not of the cardholder.
    if settings.enable_safety_net_night_micro:
        if (
            amount is not None
            and amount < settings.safety_net_night_micro_max_amount
            and category in _NIGHT_MICRO_CATEGORIES
            and hour is not None
            and settings.safety_net_night_micro_hour_start
            <= hour
            <= settings.safety_net_night_micro_hour_end
        ):
            triggered.append("night_micro_amount")

    # -------- Rule 2: velocity_spike (established customer sudden large) --
    # DELIBERATELY EXCLUDES high_spender profile: high_spender customers
    # legitimately spend variable large amounts (weddings, luxury purchases,
    # premium electronics) at ratios of 5-10x their average, and empirically
    # ~all their high-ratio transactions are legit. Flagging them creates
    # false positives on the exact customer segment we most want to retain.
    # Only established (avg ~$55) and senior (avg ~$42) trigger — their
    # baselines are low enough that a 5x ratio is a real anomaly.
    if settings.enable_safety_net_velocity_spike:
        if (
            demo_profile_key in ("established", "senior")
            and profile is not None
            and amount is not None
        ):
            avg_past = _safe_float(profile.get("avg_past_amt"))
            if avg_past is not None and avg_past > 0:
                ratio = amount / avg_past
                if ratio > settings.safety_net_velocity_spike_ratio:
                    triggered.append("velocity_spike_established")

    # -------- Rule 3: night + new + high amount ---------------------------
    if settings.enable_safety_net_night_new_high:
        if (
            demo_profile_key == "new"
            and amount is not None
            and amount > settings.safety_net_night_new_high_min_amount
            and hour is not None
            and 20 <= hour <= 23
        ):
            triggered.append("evening_new_high_amount")

    if triggered:
        return "review", triggered

    return raw_decision, triggered


def _safe_float(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # NaN check
    return f if f == f else None


def _safe_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
