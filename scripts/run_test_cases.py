"""Run authored test cases through the CHIMERA-FD checkout endpoint,
compare model decisions with the expected labels, and produce an eval
report.

Usage:
    # 1) Start backend in a separate terminal:
    #    uvicorn api.main:app --reload --port 8000
    # 2) Then run:
    python scripts/run_test_cases.py --dir tests/authored
    # Or pass a specific file:
    python scripts/run_test_cases.py --file tests/authored/anurag.jsonl
    # Or hit a remote deployment:
    python scripts/run_test_cases.py --dir tests/authored \\
        --base-url https://undebuggedbit-chimera-fd.hf.space
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Decision → outcome mapping
# ---------------------------------------------------------------------------
# The checkout endpoint returns one of these statuses:
#   "approved"  - model auto-approved
#   "declined"  - model auto-blocked
#   "review"    - model uncertain
# The test case labels are "fraud" or "legit". We define correctness as:
#   fraud   + declined       → correct
#   fraud   + review         → partial (model was suspicious, sent to human)
#   fraud   + approved       → MISSED FRAUD (bad)
#   legit   + approved       → correct
#   legit   + review         → partial (false alarm sent to human)
#   legit   + declined       → FALSE POSITIVE (bad)

CORRECT = "correct"
PARTIAL = "partial"
MISSED_FRAUD = "missed_fraud"
FALSE_POSITIVE = "false_positive"


def classify(expected_label: str, status: str) -> str:
    exp = expected_label.lower()
    st = status.lower()
    if exp == "fraud":
        if st == "declined":
            return CORRECT
        if st == "review":
            return PARTIAL
        return MISSED_FRAUD
    if exp == "legit":
        if st == "approved":
            return CORRECT
        if st == "review":
            return PARTIAL
        return FALSE_POSITIVE
    return "unknown"


# ---------------------------------------------------------------------------
# Test case loading
# ---------------------------------------------------------------------------

def load_cases(target: Path) -> list[dict[str, Any]]:
    """Load JSONL test cases. `target` can be a file or a directory."""
    files: list[Path] = []
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.glob("*.jsonl"))
    else:
        raise SystemExit(f"Not found: {target}")

    cases: list[dict[str, Any]] = []
    for f in files:
        with open(f, "r", encoding="utf-8") as fp:
            for i, line in enumerate(fp):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  ! {f}:{i+1} — JSON error: {e}", file=sys.stderr)
                    continue
                obj["_source_file"] = f.name
                cases.append(obj)
    return cases


# ---------------------------------------------------------------------------
# Backend caller
# ---------------------------------------------------------------------------

def call_checkout(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/checkout"
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def build_report(rows: list[dict[str, Any]], base_url: str) -> str:
    total = len(rows)
    counts = defaultdict(int)
    per_typology: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    per_severity: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for r in rows:
        outcome = r["outcome"]
        counts[outcome] += 1
        per_typology[r["typology"]][outcome] += 1
        per_severity[r["severity"]][outcome] += 1

    correct = counts[CORRECT]
    partial = counts[PARTIAL]
    missed = counts[MISSED_FRAUD]
    fp = counts[FALSE_POSITIVE]

    accuracy = (correct / total * 100.0) if total else 0.0
    weighted_score = (correct + partial * 0.5) / total * 100.0 if total else 0.0

    lines = []
    lines.append("# CHIMERA-FD · Test Case Evaluation Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.utcnow().isoformat()}Z")
    lines.append(f"- Backend: `{base_url}`")
    lines.append(f"- Total cases: **{total}**")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(f"- **Accuracy**: {accuracy:.1f}%  ({correct}/{total})")
    lines.append(f"- **Partial credit** (routed to REVIEW): "
                 f"{partial}  ({partial/total*100:.1f}%)")
    lines.append(f"- **Missed fraud** (blocked → approved): "
                 f"{missed}  ({missed/total*100:.1f}%)  ← RECALL FAIL")
    lines.append(f"- **False positives** (legit → blocked): "
                 f"{fp}  ({fp/total*100:.1f}%)  ← PRECISION FAIL")
    lines.append(f"- Weighted score (correct + 0.5 × partial): "
                 f"{weighted_score:.1f}%")
    lines.append("")

    lines.append("## Per typology")
    lines.append("")
    lines.append("| Typology | Total | Correct | Partial | Missed | FP |")
    lines.append("|---|---|---|---|---|---|")
    for typ, d in sorted(per_typology.items()):
        t = sum(d.values())
        lines.append(
            f"| `{typ}` | {t} | {d[CORRECT]} | {d[PARTIAL]} | "
            f"{d[MISSED_FRAUD]} | {d[FALSE_POSITIVE]} |"
        )
    lines.append("")

    lines.append("## Per severity")
    lines.append("")
    lines.append("| Severity | Total | Correct | Partial | Missed | FP |")
    lines.append("|---|---|---|---|---|---|")
    for sev, d in sorted(per_severity.items()):
        t = sum(d.values())
        lines.append(
            f"| `{sev}` | {t} | {d[CORRECT]} | {d[PARTIAL]} | "
            f"{d[MISSED_FRAUD]} | {d[FALSE_POSITIVE]} |"
        )
    lines.append("")

    # Detailed mistakes — most useful for debugging
    lines.append("## Cases the model got wrong")
    lines.append("")
    lines.append("| ID | Scenario | Expected | Model | Score | Typology | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        if r["outcome"] in (MISSED_FRAUD, FALSE_POSITIVE):
            lines.append(
                f"| {r['id']} | {r['scenario']} | {r['expected_label']} | "
                f"{r['status']} | {r['risk_score']:.4f} | {r['typology']} | "
                f"{r['notes']} |"
            )
    lines.append("")

    lines.append("## Full log")
    lines.append("")
    lines.append("| ID | Expected | Model | Score | Outcome | File |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['expected_label']} | {r['status']} | "
            f"{r['risk_score']:.4f} | {r['outcome']} | {r['_source_file']} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=str, default=None,
                    help="Directory containing *.jsonl test case files")
    ap.add_argument("--file", type=str, default=None,
                    help="Single JSONL file")
    ap.add_argument("--base-url", type=str,
                    default="http://localhost:8000",
                    help="Base URL of the CHIMERA-FD backend")
    ap.add_argument("--output-dir", type=str, default="tests/results",
                    help="Where to save the evaluation report")
    args = ap.parse_args()

    if not args.dir and not args.file:
        ap.error("pass either --dir or --file")

    target = Path(args.dir or args.file)
    if not target.is_absolute():
        target = ROOT / target

    cases = load_cases(target)
    if not cases:
        raise SystemExit(f"No cases loaded from {target}")

    print(f"Loaded {len(cases)} test cases from {target}")
    print(f"Base URL: {args.base_url}")
    print()

    rows: list[dict[str, Any]] = []
    t_start = time.time()

    for i, case in enumerate(cases, 1):
        payload = case.get("payload") or {}
        expected = case.get("expected_label", "unknown")
        try:
            res = call_checkout(args.base_url, payload)
        except Exception as e:
            print(f"  ✗ {case.get('id', '?')} — request failed: {e}",
                  file=sys.stderr)
            rows.append({
                "id": case.get("id", "?"),
                "scenario": case.get("scenario", ""),
                "expected_label": expected,
                "severity": case.get("expected_severity", ""),
                "typology": case.get("typology", ""),
                "status": "error",
                "risk_score": 0.0,
                "outcome": "error",
                "notes": case.get("notes", ""),
                "_source_file": case.get("_source_file", ""),
            })
            continue

        status = res.get("status", "unknown")
        score = float(res.get("risk_score", 0.0))
        outcome = classify(expected, status)

        rows.append({
            "id": case.get("id", "?"),
            "scenario": case.get("scenario", ""),
            "expected_label": expected,
            "severity": case.get("expected_severity", ""),
            "typology": case.get("typology", ""),
            "status": status,
            "risk_score": score,
            "outcome": outcome,
            "notes": case.get("notes", ""),
            "_source_file": case.get("_source_file", ""),
        })

        marker = {
            CORRECT: "✓",
            PARTIAL: "~",
            MISSED_FRAUD: "✗ MISS",
            FALSE_POSITIVE: "✗ FP",
        }.get(outcome, "?")
        print(
            f"  {marker:>7}  [{i:>3}/{len(cases)}] "
            f"{case.get('id', '?'):<8} exp={expected:<5} "
            f"got={status:<9} score={score:.4f}"
        )

    dt = time.time() - t_start
    print()
    print(f"Done in {dt:.1f}s.  Building report ...")

    report = build_report(rows, args.base_url)
    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    out_path = out_dir / f"eval_{stamp}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {out_path}")

    # Also save the raw predictions for later analysis
    raw_path = out_dir / f"eval_{stamp}.jsonl"
    with open(raw_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"Raw JSONL log saved to {raw_path}")


if __name__ == "__main__":
    main()
