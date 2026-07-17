"""Run a labeled test-case JSONL DIRECTLY against the Sparkov model,
bypassing HTTP, auth, DB, and merchant routing.

WHY THIS EXISTS (alongside run_labeled_test_cases.py)
-----------------------------------------------------
The API script is an *integration* test: HTTP -> auth -> checkout endpoint ->
DB write -> response. Great for smoke-testing the full stack, slow to iterate.

This script is a *unit* test of the model: no server needed, no rate limits,
~5s for 234 cases instead of ~30s. Uses the SAME enrichment logic the checkout
endpoint uses (imports CUSTOMER_PROFILES and _build_sparkov_row directly), so
predictions match production exactly.

DELIBERATE OMISSIONS vs the API path
------------------------------------
* No DB writes  (we're not testing persistence)
* No JWT auth   (no server involved)
* No merchant company_slug routing (not testing multi-tenant plumbing)
* No small-amount safety net (that lives in the API layer; we test the raw
  model decision here — cleaner signal for calibration analysis)

MODEL ISOLATION GUARANTEE
-------------------------
Same as the API script: only the 8 checkout fields end up in the payload the
model sees. `label`, `notes`, `typology`, `scenario`, etc. are read from the
JSONL and used AFTER scoring to compute correctness — never before.

USAGE
-----
    python scripts/run_labeled_test_cases_direct.py \
        --input "test cases_v1_by_Gurnoor.labeled.jsonl"

    # Optional:
    #   --limit 20        # first N rows only
    #   --include-safety-net  # apply the same small-amount safety net the
    #                         # /api/checkout endpoint applies. Off by default.

REQUIREMENTS
------------
Everything the backend already needs: lightgbm, pandas, numpy, scikit-learn.
No extra install needed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Make api/ AND src/chimera_fd importable when invoked from repo root.
# api/main.py does the same sys.path insert for src/ so the chimera_fd
# package can be imported by the model service.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from api.config import get_settings  # noqa: E402
from api.services.model_service import get_model_service  # noqa: E402
from api.services.sparkov_lookups import get_sparkov_lookups  # noqa: E402
from api.services.decision_augmenter import apply_safety_nets  # noqa: E402
from api.routes.checkout import (  # noqa: E402
    CUSTOMER_PROFILES,
    _build_sparkov_row,
)
from api.schemas.checkout import CheckoutRequest  # noqa: E402


_CHECKOUT_ALLOWED_KEYS = frozenset({
    "card_number", "cardholder_name", "amount", "merchant_name",
    "merchant_category", "cust_email", "demo_profile", "demo_hour_override",
})


_DECISION_TO_LABEL = {
    "approve":  "legit",
    "block":    "fraud",
    "review":   "review",
}


@dataclass
class CaseResult:
    id: str
    expected: str
    predicted: str
    decision_raw: Optional[str] = None
    risk_score: Optional[float] = None
    raw_score: Optional[float] = None
    latency_ms: Optional[float] = None
    correct: bool = False
    error_type: Optional[str] = None
    typology: Optional[str] = None
    scenario: Optional[str] = None
    severity: Optional[str] = None
    amount: Optional[float] = None
    hour: Optional[int] = None
    profile: Optional[str] = None
    category: Optional[str] = None
    engine_error: Optional[str] = None
    # V4 addition: which decision_augmenter rules fired (empty list = pure
    # model). Populated only when --include-safety-net is passed.
    rules_triggered: Optional[list] = None


def sanitize_payload(raw_payload: dict) -> dict:
    return {k: v for k, v in raw_payload.items() if k in _CHECKOUT_ALLOWED_KEYS}


def _resolve_profile_local(safe: dict) -> dict:
    """Same rule as api.routes.checkout._resolve_profile, but without the
    Pydantic wrapper — we don't need it here."""
    dp = safe.get("demo_profile")
    if dp and dp in CUSTOMER_PROFILES:
        return CUSTOMER_PROFILES[dp]
    # Fall back to card-last4 match, then "new"
    last4 = "".join(c for c in str(safe.get("card_number", "")) if c.isdigit())[-4:]
    for _, prof in CUSTOMER_PROFILES.items():
        if prof["card_last4"] == last4:
            return prof
    return CUSTOMER_PROFILES["new"]


def score_one(safe_payload: dict, apply_safety_net: bool) -> tuple[dict, Optional[str]]:
    """Return (score_result_dict, error_string).

    score_result_dict on success:
        {"decision": "approve|review|block",
         "calibrated_score": float,
         "raw_score": float,
         "latency_ms": float}
    """
    ms = get_model_service()

    try:
        # Build the same CheckoutRequest shape the endpoint uses so
        # _build_sparkov_row works unmodified.
        req = CheckoutRequest(**safe_payload)
        profile = _resolve_profile_local(safe_payload)

        now = datetime.now(timezone.utc)
        hour = req.demo_hour_override if req.demo_hour_override is not None else now.hour
        day_of_week = now.weekday()

        X = _build_sparkov_row(req, profile, hour, day_of_week)
        result = ms.score_sparkov(X)

        raw = float(result["raw_scores"][0])
        cal = float(result["calibrated_scores"][0])
        decision = result["decisions"][0]
        latency = float(result["latency_ms"])

        rules_triggered: list = []
        # Apply the SAME decision augmenter that /api/checkout uses in
        # production. Same code path, same rules, same flags — so measurement
        # here matches deployed behaviour bit-for-bit. See B-2 in
        # MODEL_AUDIT_POST_TESTING.md.
        if apply_safety_net:
            decision, rules_triggered = apply_safety_nets(
                payload=safe_payload,
                profile=profile,
                raw_decision=decision,
                cal_score=cal,
            )

        return {
            "decision": decision,
            "calibrated_score": cal,
            "raw_score": raw,
            "latency_ms": latency,
            "rules_triggered": rules_triggered,
        }, None
    except Exception as e:
        return {}, f"{type(e).__name__}: {e}"


def classify(case: dict, score: dict, err: Optional[str]) -> CaseResult:
    payload = case.get("payload", {})
    expected = case["label"]

    result = CaseResult(
        id=case.get("id", "?"),
        expected=expected,
        predicted="error",
        typology=case.get("typology"),
        scenario=case.get("scenario"),
        severity=case.get("expected_severity"),
        amount=payload.get("amount"),
        hour=payload.get("demo_hour_override"),
        profile=payload.get("demo_profile"),
        category=payload.get("merchant_category"),
    )

    if err is not None:
        result.error_type = "engine_error"
        result.engine_error = err
        return result

    decision_raw = score.get("decision")
    result.decision_raw = decision_raw
    result.risk_score = score.get("calibrated_score")
    result.raw_score = score.get("raw_score")
    result.latency_ms = score.get("latency_ms")
    result.rules_triggered = score.get("rules_triggered") or None

    predicted = _DECISION_TO_LABEL.get(str(decision_raw).lower(), "error")
    result.predicted = predicted

    if predicted == "review":
        result.error_type = (
            "missed_as_review_fraud" if expected == "fraud"
            else "missed_as_review_legit"
        )
        return result

    if predicted == expected:
        result.correct = True
    else:
        if expected == "legit" and predicted == "fraud":
            result.error_type = "false_positive"
        elif expected == "fraud" and predicted == "legit":
            result.error_type = "false_negative"
        else:
            result.error_type = "unknown_mismatch"
    return result


def summarize(results: list[CaseResult], max_wrong_detail: int = 200) -> dict:
    total = len(results)
    correct = sum(1 for r in results if r.correct)
    wrong = sum(1 for r in results if r.error_type in
                ("false_positive", "false_negative", "unknown_mismatch"))
    review = sum(1 for r in results if r.predicted == "review")
    errors = sum(1 for r in results if r.predicted == "error")

    fp = [r for r in results if r.error_type == "false_positive"]
    fn = [r for r in results if r.error_type == "false_negative"]

    per_typology = {}
    typos = sorted({r.typology for r in results if r.typology})
    for t in typos:
        sub = [r for r in results if r.typology == t]
        per_typology[t] = {
            "total":   len(sub),
            "correct": sum(1 for r in sub if r.correct),
            "wrong":   sum(1 for r in sub if r.error_type in
                          ("false_positive", "false_negative", "unknown_mismatch")),
            "review":  sum(1 for r in sub if r.predicted == "review"),
            "error":   sum(1 for r in sub if r.predicted == "error"),
        }

    denom_for_acc = total - review - errors
    return {
        "engine": "sparkov (direct model call, no HTTP)",
        "total_cases": total,
        "correct": correct,
        "wrong": wrong,
        "review_ambiguous": review,
        "engine_errors": errors,
        "accuracy_strict": round(correct / total, 4) if total else 0.0,
        "accuracy_excluding_review_and_errors":
            round(correct / denom_for_acc, 4) if denom_for_acc else 0.0,
        "note_ieee": (
            "IEEE-CIS engine not tested: payload schema is Sparkov-shaped."
        ),
        "counts_by_expected":  dict(Counter(r.expected for r in results)),
        "counts_by_predicted": dict(Counter(r.predicted for r in results)),
        "confusion_matrix": {
            "expected_fraud_predicted_fraud":
                sum(1 for r in results if r.expected == "fraud" and r.predicted == "fraud"),
            "expected_fraud_predicted_legit":  len(fn),
            "expected_fraud_predicted_review":
                sum(1 for r in results if r.expected == "fraud" and r.predicted == "review"),
            "expected_legit_predicted_legit":
                sum(1 for r in results if r.expected == "legit" and r.predicted == "legit"),
            "expected_legit_predicted_fraud":  len(fp),
            "expected_legit_predicted_review":
                sum(1 for r in results if r.expected == "legit" and r.predicted == "review"),
        },
        # Full wrong list can be huge at 150K rows; cap detail size for the
        # summary JSON but keep every wrong prediction in the per-case JSONL.
        "wrong_predictions_detail_truncated_to": max_wrong_detail,
        "wrong_predictions_detail": (
            lambda wr: (wr if max_wrong_detail <= 0 else wr[:max_wrong_detail])
        )([
            {
                "id": r.id, "expected": r.expected, "predicted": r.predicted,
                "decision_raw": r.decision_raw, "risk_score": r.risk_score,
                "raw_score": r.raw_score, "error_type": r.error_type,
                "typology": r.typology, "scenario": r.scenario, "severity": r.severity,
                "amount": r.amount, "hour": r.hour, "profile": r.profile,
                "category": r.category,
            }
            for r in results
            if r.error_type in ("false_positive", "false_negative", "unknown_mismatch")
        ]),
        "per_typology": per_typology,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run labeled test cases directly against the Sparkov model."
    )
    ap.add_argument("--input", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--include-safety-net", action="store_true",
                    help="Apply the small-amount safety net that /api/checkout uses.")
    ap.add_argument("--progress-every", type=int, default=0,
                    help="Print per-row progress every N rows. "
                         "Default 0 = auto (every row up to 500 rows, "
                         "every 1000 rows for larger files). Use 1 for verbose, "
                         "-1 to suppress per-row prints entirely.")
    ap.add_argument("--max-wrong-detail", type=int, default=200,
                    help="Cap the wrong_predictions_detail list in the summary "
                         "JSON to this many rows. Full per-case results are still "
                         "in the JSONL file. Default 200. Use 0 for unlimited.")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        print(f"ERROR: input file not found: {in_path}", file=sys.stderr)
        return 2

    stem = in_path.stem
    out_jsonl   = in_path.with_name(f"result_{in_path.name}")
    out_summary = in_path.with_name(f"result_{stem}_summary.json")

    print(f"Loading {in_path}...")
    with in_path.open() as f:
        cases = [json.loads(l) for l in f if l.strip()]
    if args.limit > 0:
        cases = cases[:args.limit]
    print(f"  {len(cases)} test cases")

    print("Loading Sparkov model + lookups...")
    ms = get_model_service()
    ms.load()
    get_sparkov_lookups().load()
    if ms.sparkov_model is None:
        print("ERROR: Sparkov model not available. Check models/stage1_sparkov.pkl", file=sys.stderr)
        return 3
    print(f"  model ready: {ms.sparkov_model_version}")

    # Decide progress cadence
    total = len(cases)
    if args.progress_every == 0:
        progress_every = 1 if total <= 500 else max(1, total // 100)  # ~100 lines
    else:
        progress_every = args.progress_every

    results: list[CaseResult] = []
    t0 = time.time()
    running_correct = 0
    running_wrong = 0
    running_review = 0
    running_err = 0

    for i, case in enumerate(cases, start=1):
        safe = sanitize_payload(case.get("payload", {}))
        score, err = score_one(safe, apply_safety_net=args.include_safety_net)
        cr = classify(case, score, err)
        results.append(cr)

        if cr.correct:
            running_correct += 1
        elif cr.predicted == "review":
            running_review += 1
        elif cr.predicted == "error":
            running_err += 1
        else:
            running_wrong += 1

        should_print = (progress_every > 0 and
                        (i == 1 or i == total or i % progress_every == 0))
        if should_print:
            rate = i / max(time.time() - t0, 0.001)
            eta = (total - i) / rate if rate > 0 else 0
            acc_so_far = running_correct / i * 100
            print(f"  [{i:>7d}/{total}] "
                  f"correct={running_correct:>7d} wrong={running_wrong:>6d} "
                  f"review={running_review:>5d} err={running_err:>4d}  "
                  f"acc={acc_so_far:5.2f}%  {rate:6.1f} rows/s  ETA {eta:6.1f}s")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s ({total/elapsed:.0f} rows/s).")

    with out_jsonl.open("w") as f:
        for r in results:
            f.write(json.dumps(asdict(r)) + "\n")
    print(f"Per-case results: {out_jsonl}")

    summary = summarize(results, max_wrong_detail=args.max_wrong_detail)
    with out_summary.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"Summary:          {out_summary}")

    print("\n===== SUMMARY (direct model, no HTTP) =====")
    print(f"Total:            {summary['total_cases']}")
    print(f"Correct:          {summary['correct']}")
    print(f"Wrong:            {summary['wrong']}")
    print(f"Review (ambig.):  {summary['review_ambiguous']}")
    print(f"Engine errors:    {summary['engine_errors']}")
    print(f"Strict accuracy:                 {summary['accuracy_strict']:.2%}")
    print(f"Accuracy (ex. review + errors):  {summary['accuracy_excluding_review_and_errors']:.2%}")

    cm = summary["confusion_matrix"]
    print("\nConfusion matrix:")
    print(f"  fraud->fraud  = {cm['expected_fraud_predicted_fraud']:3d}   (true positive)")
    print(f"  fraud->legit  = {cm['expected_fraud_predicted_legit']:3d}   (false negative)")
    print(f"  fraud->review = {cm['expected_fraud_predicted_review']:3d}")
    print(f"  legit->legit  = {cm['expected_legit_predicted_legit']:3d}   (true negative)")
    print(f"  legit->fraud  = {cm['expected_legit_predicted_fraud']:3d}   (false positive)")
    print(f"  legit->review = {cm['expected_legit_predicted_review']:3d}")

    print("\nPer typology:")
    for t, s in summary["per_typology"].items():
        total_t = s["total"]
        pct = f"{s['correct'] / total_t * 100:5.1f}%" if total_t else "  n/a"
        print(f"  {t:26s}  total={s['total']:>6d}  correct={s['correct']:>6d} ({pct})  "
              f"wrong={s['wrong']:>6d}  review={s['review']:>5d}  err={s['error']:>4d}")

    print(f"\nIEEE note: {summary['note_ieee']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
