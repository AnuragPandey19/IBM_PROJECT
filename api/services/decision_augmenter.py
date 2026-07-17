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
    if settings.enable_safety_net_card_testing:
        if (
            demo_profile_key == "new"
            and amount is not None
            and amount < settings.safety_net_card_testing_max_amount
            and category in _CARD_TESTING_TARGET_CATEGORIES
        ):
            triggered.append("card_testing_small_amount")

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
