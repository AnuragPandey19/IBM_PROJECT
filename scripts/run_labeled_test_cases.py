"""Run a labeled test-case JSONL against the deployed CHIMERA-FD backend.

DESIGN GOALS
------------
1. Zero cheating. Every payload sent to the model contains ONLY the 8 checkout
   fields: card_number, cardholder_name, amount, merchant_name,
   merchant_category, cust_email, demo_profile, demo_hour_override.
   The label, scenario, notes, typology — all held back locally. The model
   decides on its own; we only compare after the fact.

2. Two engines: /api/checkout (Sparkov path, the intended target for these
   checkout-shaped payloads) is run for every row. IEEE-CIS is deliberately
   skipped because the payload schema doesn't map to it — testing it would
   produce noise, not signal. This is called out in the summary.

3. The result filename mirrors the input filename with a `result_` prefix:
     Input:  "test cases_v1_by_Gurnoor.labeled.jsonl"
     Output: "result_test cases_v1_by_Gurnoor.labeled.jsonl"
             "result_test cases_v1_by_Gurnoor.labeled_summary.json"

USAGE
-----
    python scripts/run_labeled_test_cases.py \
        --input "test cases_v1_by_Gurnoor.labeled.jsonl" \
        --backend https://undebuggedbit-chimera-fd.hf.space \
        --email you@example.com \
        --password YOUR_PASSWORD

    # Optional:
    #   --sleep 0.1           # pause between requests (be nice to rate-limits)
    #   --limit 20            # only run first N cases (dry-run / debugging)
    #   --company-slug zomato # tag transactions to a specific merchant slug
    #                         # (routes the txn to that merchant's dashboard)

REQUIREMENTS
------------
    pip install requests

The script talks to your live HF Space. Login uses POST /auth/login with
JSON {"email": ..., "password": ...}. If your account doesn't exist yet,
register via the UI first.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("ERROR: install `requests` first:  pip install requests", file=sys.stderr)
    sys.exit(2)


# ---- Only these 8 keys ever leave this machine ---------------------------
# Everything else in the labeled JSONL (label, original_label, notes,
# typology, scenario, description, id, claude_audit_notes...) is kept local
# and never forwarded to the model.
_CHECKOUT_ALLOWED_KEYS = frozenset({
    "card_number",
    "cardholder_name",
    "amount",
    "merchant_name",
    "merchant_category",
    "cust_email",
    "demo_profile",
    "demo_hour_override",
})


# Map API decision -> comparable label. `review` is neither correct nor wrong
# by itself — treated as a separate bucket and reported explicitly.
_DECISION_TO_LABEL = {
    "approve":  "legit",
    "block":    "fraud",
    "review":   "review",
    "declined": "fraud",   # some codepaths use "declined"
    "approved": "legit",
}


@dataclass
class CaseResult:
    id: str
    expected: str                       # "fraud" | "legit"
    predicted: str                      # "fraud" | "legit" | "review" | "error"
    decision_raw: Optional[str] = None  # backend's literal response
    risk_score: Optional[float] = None
    latency_ms: Optional[float] = None
    correct: bool = False
    error_type: Optional[str] = None    # false_positive | false_negative |
                                        # missed_as_review_fraud |
                                        # missed_as_review_legit |
                                        # api_error
    api_error: Optional[str] = None
    typology: Optional[str] = None
    scenario: Optional[str] = None
    severity: Optional[str] = None
    amount: Optional[float] = None
    hour: Optional[int] = None
    profile: Optional[str] = None
    category: Optional[str] = None


def load_labeled(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(l) for l in f if l.strip()]


def login(backend: str, email: str, password: str, timeout: float = 30.0) -> str:
    """Return JWT access token."""
    url = backend.rstrip("/") + "/auth/login"
    r = requests.post(url, json={"email": email, "password": password}, timeout=timeout)
    if r.status_code != 200:
        raise SystemExit(f"Login failed: HTTP {r.status_code} {r.text[:300]}")
    tok = r.json().get("access_token")
    if not tok:
        raise SystemExit(f"Login response missing access_token: {r.text[:300]}")
    return tok


def sanitize_payload(raw_payload: dict) -> dict:
    """Return only the 8 fields the checkout endpoint expects."""
    return {k: v for k, v in raw_payload.items() if k in _CHECKOUT_ALLOWED_KEYS}


def call_checkout(
    backend: str,
    token: str,
    payload: dict,
    company_slug: Optional[str],
    timeout: float,
) -> tuple[Optional[dict], Optional[str]]:
    url = backend.rstrip("/") + "/api/checkout"
    body = dict(payload)
    if company_slug:
        body["company_slug"] = company_slug
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.RequestException as e:
        return None, f"request_exception: {type(e).__name__}: {e}"
    if r.status_code == 429:
        return None, "rate_limited (HTTP 429) — increase --sleep"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}: {r.text[:300]}"
    try:
        return r.json(), None
    except ValueError:
        return None, f"non-JSON response: {r.text[:300]}"


def classify(case: dict, resp: Optional[dict], api_err: Optional[str]) -> CaseResult:
    payload = case.get("payload", {})
    expected = case["label"]  # "fraud" | "legit"

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

    if api_err is not None:
        result.predicted = "error"
        result.error_type = "api_error"
        result.api_error = api_err
        return result

    decision_raw = (resp or {}).get("status") or (resp or {}).get("decision")
    result.decision_raw = decision_raw
    result.risk_score = (resp or {}).get("risk_score")
    result.latency_ms = (resp or {}).get("decision_time_ms")

    predicted = _DECISION_TO_LABEL.get(str(decision_raw).lower(), "error")
    result.predicted = predicted

    if predicted == "review":
        result.error_type = (
            "missed_as_review_fraud" if expected == "fraud" else "missed_as_review_legit"
        )
        result.correct = False
        return result

    if predicted == expected:
        result.correct = True
        result.error_type = None
    else:
        result.correct = False
        if expected == "legit" and predicted == "fraud":
            result.error_type = "false_positive"
        elif expected == "fraud" and predicted == "legit":
            result.error_type = "false_negative"
        else:
            result.error_type = "unknown_mismatch"
    return result


def summarize(results: list[CaseResult]) -> dict:
    total = len(results)
    correct = sum(1 for r in results if r.correct)
    wrong = sum(1 for r in results if r.error_type in
                ("false_positive", "false_negative", "unknown_mismatch"))
    review = sum(1 for r in results if r.predicted == "review")
    errors = sum(1 for r in results if r.predicted == "error")

    fp = [r for r in results if r.error_type == "false_positive"]
    fn = [r for r in results if r.error_type == "false_negative"]
    missed_fraud_as_review = [r for r in results if r.error_type == "missed_as_review_fraud"]
    missed_legit_as_review = [r for r in results if r.error_type == "missed_as_review_legit"]

    by_expected = Counter(r.expected for r in results)
    by_predicted = Counter(r.predicted for r in results)

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
    accuracy_strict = correct / total if total else 0.0
    accuracy_excluding_review = correct / denom_for_acc if denom_for_acc else 0.0

    return {
        "total_cases": total,
        "correct": correct,
        "wrong": wrong,
        "review_ambiguous": review,
        "api_errors": errors,
        "accuracy_strict":                       round(accuracy_strict, 4),
        "accuracy_excluding_review_and_errors":  round(accuracy_excluding_review, 4),
        "note_ieee": (
            "IEEE-CIS engine not tested: this payload schema is Sparkov-shaped. "
            "Testing IEEE would require anonymised card1/V127/... fields not present here."
        ),
        "counts_by_expected":  dict(by_expected),
        "counts_by_predicted": dict(by_predicted),
        "confusion_matrix": {
            "expected_fraud_predicted_fraud":  len(
                [r for r in results if r.expected == "fraud" and r.predicted == "fraud"]),
            "expected_fraud_predicted_legit":  len(fn),
            "expected_fraud_predicted_review": len(missed_fraud_as_review),
            "expected_legit_predicted_legit":  len(
                [r for r in results if r.expected == "legit" and r.predicted == "legit"]),
            "expected_legit_predicted_fraud":  len(fp),
            "expected_legit_predicted_review": len(missed_legit_as_review),
        },
        "wrong_predictions_detail": [
            {
                "id": r.id,
                "expected": r.expected,
                "predicted": r.predicted,
                "decision_raw": r.decision_raw,
                "risk_score": r.risk_score,
                "error_type": r.error_type,
                "typology": r.typology,
                "scenario": r.scenario,
                "severity": r.severity,
                "amount": r.amount,
                "hour": r.hour,
                "profile": r.profile,
                "category": r.category,
            }
            for r in results
            if r.error_type in ("false_positive", "false_negative", "unknown_mismatch")
        ],
        "per_typology": per_typology,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run labeled fraud-detection test cases against CHIMERA-FD."
    )
    ap.add_argument("--input", required=True,
                    help="Path to the labeled JSONL (must have a `label` field per row).")
    ap.add_argument("--backend", default="https://undebuggedbit-chimera-fd.hf.space",
                    help="Base URL of the deployed API.")
    ap.add_argument("--email", required=True, help="Login email.")
    ap.add_argument("--password", required=True, help="Login password.")
    ap.add_argument("--company-slug", default=None,
                    help="Optional merchant slug for routing (e.g. zomato).")
    ap.add_argument("--sleep", type=float, default=0.15,
                    help="Seconds between requests. Increase if rate-limited.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only run the first N cases (0 = all).")
    ap.add_argument("--timeout", type=float, default=45.0,
                    help="Per-request timeout in seconds.")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.is_file():
        print(f"ERROR: input file not found: {in_path}", file=sys.stderr)
        return 2

    # Result filenames mirror input basename, prefixed with `result_`.
    stem = in_path.stem
    out_jsonl   = in_path.with_name(f"result_{in_path.name}")
    out_summary = in_path.with_name(f"result_{stem}_summary.json")

    print(f"Loading {in_path}...")
    cases = load_labeled(in_path)
    if args.limit > 0:
        cases = cases[:args.limit]
    print(f"  {len(cases)} test cases to run")

    print(f"Logging in to {args.backend} as {args.email}...")
    token = login(args.backend, args.email, args.password, timeout=args.timeout)
    print("  authenticated")

    results: list[CaseResult] = []
    t0 = time.time()

    for i, case in enumerate(cases, start=1):
        raw_payload = case.get("payload", {})
        safe_payload = sanitize_payload(raw_payload)  # <-- strips everything

        resp, api_err = call_checkout(
            args.backend, token, safe_payload,
            company_slug=args.company_slug, timeout=args.timeout,
        )
        cr = classify(case, resp, api_err)
        results.append(cr)

        tag = "OK " if cr.correct else ("ERR" if cr.error_type == "api_error" else "X  ")
        if cr.predicted == "review":
            tag = "?  "
        score_str = f"{cr.risk_score:.4f}" if cr.risk_score is not None else "-"
        print(f"  [{i:3d}/{len(cases)}] {tag} {cr.id:10s} "
              f"expected={cr.expected:5s} predicted={cr.predicted:6s} "
              f"score={score_str} err={cr.error_type or ''}")

        if args.sleep:
            time.sleep(args.sleep)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s.")

    # Per-case result JSONL
    with out_jsonl.open("w") as f:
        for r in results:
            f.write(json.dumps(asdict(r)) + "\n")
    print(f"Wrote per-case results to: {out_jsonl}")

    # Aggregate summary JSON
    summary = summarize(results)
    with out_summary.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote summary to:        {out_summary}")

    # Human-readable console summary
    print("\n===== SUMMARY =====")
    print(f"Total:            {summary['total_cases']}")
    print(f"Correct:          {summary['correct']}")
    print(f"Wrong:            {summary['wrong']}")
    print(f"Review (ambig.):  {summary['review_ambiguous']}")
    print(f"API errors:       {summary['api_errors']}")
    print(f"Strict accuracy:                 {summary['accuracy_strict']:.2%}")
    print(f"Accuracy (ex. review + errors):  {summary['accuracy_excluding_review_and_errors']:.2%}")
    print("\nConfusion matrix:")
    cm = summary["confusion_matrix"]
    print(f"  fraud->fraud  = {cm['expected_fraud_predicted_fraud']:3d}   (true positive)")
    print(f"  fraud->legit  = {cm['expected_fraud_predicted_legit']:3d}   (false negative)")
    print(f"  fraud->review = {cm['expected_fraud_predicted_review']:3d}   (undecided on fraud)")
    print(f"  legit->legit  = {cm['expected_legit_predicted_legit']:3d}   (true negative)")
    print(f"  legit->fraud  = {cm['expected_legit_predicted_fraud']:3d}   (false positive)")
    print(f"  legit->review = {cm['expected_legit_predicted_review']:3d}   (undecided on legit)")

    print("\nPer typology:")
    for t, s in summary["per_typology"].items():
        print(f"  {t:26s}  total={s['total']:3d}  correct={s['correct']:3d}  "
              f"wrong={s['wrong']:3d}  review={s['review']:3d}  err={s['error']:3d}")

    print(f"\nIEEE note: {summary['note_ieee']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
