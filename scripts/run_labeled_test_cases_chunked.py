"""Chunked, checkpointed runner for very large labeled test-case JSONL files.

WHY THIS EXISTS
---------------
`run_labeled_test_cases_direct.py` loads and scores the whole file in memory.
That works fine for the 150K row V3 file, but breaks down at 3M+ rows:
  * memory blows up
  * a mid-run crash means starting from scratch
  * no way to inspect progress or intermediate results
  * no way to stop early and resume later

This script processes an arbitrary-size JSONL file in 100K-row chunks,
writes a per-chunk summary + gzipped result JSONL, records which chunks
are done in a checkpoint file, and can resume from any completed chunk
after a crash / manual stop.

DESIGN
------
* Streams the input JSONL line by line — never loads the full file.
* Batches into chunks of --chunk-size (default 100,000 rows).
* For each chunk:
    - scores every row using EXACTLY the same score_one function the
      standard direct-runner uses (so results match bit-for-bit)
    - writes chunk_NNNN_results.jsonl.gz  (per-row result)
    - writes chunk_NNNN_summary.json     (aggregated stats)
    - appends chunk-NNNN to checkpoint.json
* On startup, reads checkpoint.json and SKIPS already-completed chunks
  (chunk_NNNN is considered done iff summary.json exists).
* At the very end, reads all chunk summaries and writes
  final_aggregated_summary.json (grand totals + per-typology + per-rule).

DEFAULT SAFETY
--------------
--include-safety-net defaults to TRUE (matches production API behaviour).
Use --no-safety-net to measure raw model quality without rules.

USAGE
-----
    # Quick sanity check on first 1000 rows only (5 seconds)
    python scripts/run_labeled_test_cases_chunked.py ^
        --input evaluation/test_cases/Pankaj30m.jsonl ^
        --output-dir evaluation/results/pankaj_30m ^
        --sample-only

    # Full run (chunked, ~1-2 hours for 3M rows)
    python scripts/run_labeled_test_cases_chunked.py ^
        --input evaluation/test_cases/Pankaj30m.jsonl ^
        --output-dir evaluation/results/pankaj_30m

    # Resume after crash — skips completed chunks automatically
    (same command as above — checkpoint is transparent)

    # Stop after chunk 5 (500K rows) for a mid-way peek
    python scripts/run_labeled_test_cases_chunked.py ^
        --input evaluation/test_cases/Pankaj30m.jsonl ^
        --output-dir evaluation/results/pankaj_30m ^
        --stop-at-chunk 4

OUTPUT LAYOUT
-------------
    evaluation/results/pankaj_30m/
        checkpoint.json                # {"done_chunks": [0, 1, 2, ...]}
        chunk_0000_results.jsonl.gz    # 100K rows of per-case results
        chunk_0000_summary.json        # aggregated stats for chunk 0
        chunk_0001_...
        ...
        final_aggregated_summary.json  # written after last chunk finishes
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Iterator, Optional

# --- Make api/ + src/chimera_fd importable when invoked from repo root -----
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

# Reuse the exact same score_one + helpers as the standard runner so results
# match bit-for-bit. This is important: the API path, the direct-runner, and
# this chunked runner must all agree — that is the whole point of the shared
# decision_augmenter module. See MODEL_AUDIT_POST_TESTING.md issue B-2.
from scripts.run_labeled_test_cases_direct import (  # noqa: E402
    CaseResult,
    sanitize_payload,
    score_one,
    _DECISION_TO_LABEL,
)


# ============================================================================
# Streaming JSONL reader
# ============================================================================

def iter_jsonl(path: Path) -> Iterator[dict]:
    """Yield dicts one at a time from a JSONL file. Skips blank lines."""
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"[warn] line {line_no}: JSON parse error — {e}", file=sys.stderr)
                continue


# ============================================================================
# Per-chunk scoring
# ============================================================================

def _score_chunk(
    rows: list[dict],
    apply_safety_net: bool,
    progress_every: int,
    chunk_idx: int,
    global_start_idx: int,
) -> list[CaseResult]:
    """Score every row in the chunk. Returns list of CaseResult."""
    results: list[CaseResult] = []
    t0 = time.time()

    for i, row in enumerate(rows):
        raw_payload = row.get("payload") or {}
        safe = sanitize_payload(raw_payload)

        expected = row.get("expected_label", "?")
        typology = row.get("typology")
        scenario = row.get("scenario")
        severity = row.get("expected_severity")

        case_id = row.get("id") or f"row_{global_start_idx + i}"

        try:
            score_dict, err = score_one(safe, apply_safety_net=apply_safety_net)
        except Exception as e:
            results.append(CaseResult(
                id=case_id,
                expected=expected,
                predicted="error",
                typology=typology,
                scenario=scenario,
                severity=severity,
                amount=safe.get("amount"),
                hour=safe.get("demo_hour_override"),
                profile=safe.get("demo_profile"),
                category=safe.get("merchant_category"),
                engine_error=f"{type(e).__name__}: {e}",
            ))
            continue

        if err is not None or score_dict is None:
            results.append(CaseResult(
                id=case_id,
                expected=expected,
                predicted="error",
                typology=typology,
                scenario=scenario,
                severity=severity,
                amount=safe.get("amount"),
                hour=safe.get("demo_hour_override"),
                profile=safe.get("demo_profile"),
                category=safe.get("merchant_category"),
                engine_error=err or "score_one returned None",
            ))
            continue

        decision = score_dict["decision"]
        predicted_label = _DECISION_TO_LABEL.get(decision, decision)
        correct = (predicted_label == expected) if expected in ("fraud", "legit") else False
        error_type: Optional[str] = None
        if expected == "fraud" and predicted_label == "legit":
            error_type = "false_negative"
        elif expected == "legit" and predicted_label == "fraud":
            error_type = "false_positive"

        results.append(CaseResult(
            id=case_id,
            expected=expected,
            predicted=predicted_label,
            decision_raw=decision,
            risk_score=score_dict["calibrated_score"],
            raw_score=score_dict["raw_score"],
            latency_ms=score_dict["latency_ms"],
            correct=correct,
            error_type=error_type,
            typology=typology,
            scenario=scenario,
            severity=severity,
            amount=safe.get("amount"),
            hour=safe.get("demo_hour_override"),
            profile=safe.get("demo_profile"),
            category=safe.get("merchant_category"),
            rules_triggered=score_dict.get("rules_triggered"),
        ))

        if progress_every and (i + 1) % progress_every == 0:
            elapsed = time.time() - t0
            rps = (i + 1) / max(elapsed, 1e-9)
            print(
                f"  chunk {chunk_idx}: scored {i+1}/{len(rows)} — "
                f"{rps:.0f} rows/s — elapsed {elapsed:.1f}s",
                flush=True,
            )

    return results


# ============================================================================
# Per-chunk summary
# ============================================================================

def _summarise_chunk(results: list[CaseResult]) -> dict:
    """Aggregate stats for a single chunk."""
    n = len(results)
    correct = sum(1 for r in results if r.correct)
    review = sum(1 for r in results if r.predicted == "review")
    errors = sum(1 for r in results if r.predicted == "error")
    wrong = sum(1 for r in results if r.error_type in ("false_positive", "false_negative"))

    by_expected = Counter(r.expected for r in results)
    by_predicted = Counter(r.predicted for r in results)

    cm: dict[str, int] = defaultdict(int)
    for r in results:
        if r.expected in ("fraud", "legit") and r.predicted in ("fraud", "legit", "review", "error"):
            cm[f"expected_{r.expected}_predicted_{r.predicted}"] += 1

    per_typology: dict[str, dict[str, int]] = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong": 0, "review": 0, "error": 0
    })
    for r in results:
        t = r.typology or "unknown"
        per_typology[t]["total"] += 1
        if r.predicted == "error":
            per_typology[t]["error"] += 1
        elif r.predicted == "review":
            per_typology[t]["review"] += 1
        elif r.correct:
            per_typology[t]["correct"] += 1
        else:
            per_typology[t]["wrong"] += 1

    rule_hits: Counter = Counter()
    for r in results:
        for rid in (r.rules_triggered or []):
            rule_hits[rid] += 1

    strict_acc = correct / n if n else 0
    decisive = correct + wrong
    excl_review_acc = correct / decisive if decisive else 0

    return {
        "n": n,
        "correct": correct,
        "wrong": wrong,
        "review": review,
        "errors": errors,
        "accuracy_strict": round(strict_acc, 4),
        "accuracy_excluding_review_and_errors": round(excl_review_acc, 4),
        "counts_by_expected": dict(by_expected),
        "counts_by_predicted": dict(by_predicted),
        "confusion_matrix": dict(cm),
        "per_typology": dict(per_typology),
        "rule_hits": dict(rule_hits),
    }


# ============================================================================
# Final aggregation across all chunks
# ============================================================================

def _aggregate_summaries(summary_paths: list[Path]) -> dict:
    total_n = 0
    total_correct = 0
    total_wrong = 0
    total_review = 0
    total_errors = 0
    grand_expected: Counter = Counter()
    grand_predicted: Counter = Counter()
    grand_cm: Counter = Counter()
    grand_typology: dict[str, dict[str, int]] = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong": 0, "review": 0, "error": 0
    })
    grand_rules: Counter = Counter()

    for sp in summary_paths:
        d = json.loads(sp.read_text(encoding="utf-8"))
        total_n += d["n"]
        total_correct += d["correct"]
        total_wrong += d["wrong"]
        total_review += d["review"]
        total_errors += d["errors"]
        grand_expected.update(d["counts_by_expected"])
        grand_predicted.update(d["counts_by_predicted"])
        grand_cm.update(d["confusion_matrix"])
        for t, s in d["per_typology"].items():
            for k, v in s.items():
                grand_typology[t][k] += v
        grand_rules.update(d.get("rule_hits", {}))

    decisive = total_correct + total_wrong
    return {
        "total_cases": total_n,
        "correct": total_correct,
        "wrong": total_wrong,
        "review": total_review,
        "errors": total_errors,
        "accuracy_strict": round(total_correct / total_n, 4) if total_n else 0,
        "accuracy_excluding_review_and_errors":
            round(total_correct / decisive, 4) if decisive else 0,
        "counts_by_expected": dict(grand_expected),
        "counts_by_predicted": dict(grand_predicted),
        "confusion_matrix": dict(grand_cm),
        "per_typology": dict(grand_typology),
        "rule_hits": dict(grand_rules),
        "chunks_aggregated": len(summary_paths),
    }


# ============================================================================
# Checkpoint
# ============================================================================

def _load_checkpoint(path: Path) -> set[int]:
    if not path.exists():
        return set()
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return set(d.get("done_chunks", []))
    except Exception:
        return set()


def _save_checkpoint(path: Path, done: set[int]) -> None:
    path.write_text(
        json.dumps({"done_chunks": sorted(done)}, indent=2),
        encoding="utf-8",
    )


# ============================================================================
# Main driver
# ============================================================================

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to labeled JSONL file")
    p.add_argument("--output-dir", required=True, help="Directory to write chunk outputs")
    p.add_argument("--chunk-size", type=int, default=100_000,
                   help="Rows per chunk (default 100,000)")
    p.add_argument("--include-safety-net", dest="safety_net",
                   action="store_true", default=True,
                   help="Apply decision_augmenter (default: on)")
    p.add_argument("--no-safety-net", dest="safety_net", action="store_false",
                   help="Skip decision_augmenter (raw model quality only)")
    p.add_argument("--start-chunk", type=int, default=0,
                   help="Start from chunk index (auto-skips completed)")
    p.add_argument("--stop-at-chunk", type=int, default=None,
                   help="Stop after processing this chunk index (inclusive)")
    p.add_argument("--limit", type=int, default=None,
                   help="Stop after processing this many rows total")
    p.add_argument("--sample-only", action="store_true",
                   help="Score just 1000 rows and exit (quick sanity)")
    p.add_argument("--progress-every", type=int, default=10_000,
                   help="Emit progress line every N rows within a chunk")
    args = p.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        print(f"Input file does not exist: {inp}", file=sys.stderr)
        sys.exit(2)

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    ckpt_path = outdir / "checkpoint.json"

    if args.sample_only:
        # Quick 1K row sanity check — no checkpoint, no chunking
        print("[SAMPLE-ONLY MODE] Processing first 1000 rows...")
        rows = []
        for i, row in enumerate(iter_jsonl(inp)):
            if i >= 1000:
                break
            rows.append(row)
        t0 = time.time()
        results = _score_chunk(rows, args.safety_net,
                               progress_every=0, chunk_idx=-1, global_start_idx=0)
        elapsed = time.time() - t0
        summary = _summarise_chunk(results)
        (outdir / "sample_1000_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(f"\nSample summary written to {outdir / 'sample_1000_summary.json'}")
        print(f"Elapsed: {elapsed:.1f}s  ({1000/elapsed:.0f} rows/s)")
        print(f"Extrapolated full run (3M rows): "
              f"~{3_000_000 * elapsed / 1000 / 60:.1f} minutes")
        print(f"Accuracy strict:            {summary['accuracy_strict']:.4f}")
        print(f"Accuracy excluding review:  {summary['accuracy_excluding_review_and_errors']:.4f}")
        print(f"Rule hits: {summary['rule_hits']}")
        return

    # Warm the model service once — subsequent calls reuse the cached model
    from api.services.model_service import get_model_service
    print("Loading + warming Sparkov model...")
    ms = get_model_service()
    ms.load()
    ms.warmup()
    print("Model ready.\n")

    done = _load_checkpoint(ckpt_path)
    if done:
        print(f"Checkpoint found: chunks already done = {sorted(done)[:10]}"
              f"{' ...' if len(done) > 10 else ''}  ({len(done)} total)")

    chunk_size = args.chunk_size
    chunk_idx = 0
    buf: list[dict] = []
    total_rows_seen = 0
    total_rows_scored = 0
    t_run_start = time.time()

    def flush_chunk(idx: int, rows: list[dict]) -> None:
        nonlocal total_rows_scored

        if idx in done:
            print(f"[chunk {idx}] SKIP — already in checkpoint")
            return
        if idx < args.start_chunk:
            print(f"[chunk {idx}] SKIP — below --start-chunk={args.start_chunk}")
            return

        t0 = time.time()
        global_start = idx * chunk_size
        print(f"[chunk {idx}] scoring {len(rows)} rows (global {global_start}-{global_start+len(rows)-1})...")
        results = _score_chunk(rows, args.safety_net,
                               args.progress_every, idx, global_start)
        summary = _summarise_chunk(results)

        # Write result JSONL (gzipped to save disk)
        rjl = outdir / f"chunk_{idx:04d}_results.jsonl.gz"
        with gzip.open(rjl, "wt", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(asdict(r), default=str) + "\n")

        # Write summary
        sj = outdir / f"chunk_{idx:04d}_summary.json"
        sj.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        done.add(idx)
        _save_checkpoint(ckpt_path, done)

        elapsed = time.time() - t0
        total_rows_scored += len(rows)
        overall_elapsed = time.time() - t_run_start
        rps = total_rows_scored / max(overall_elapsed, 1e-9)
        print(
            f"[chunk {idx}] DONE — {len(rows)} rows in {elapsed:.1f}s "
            f"({len(rows)/elapsed:.0f} rows/s) — "
            f"correct={summary['correct']} wrong={summary['wrong']} "
            f"review={summary['review']} — "
            f"overall {rps:.0f} rows/s\n"
        )

    for row in iter_jsonl(inp):
        buf.append(row)
        total_rows_seen += 1

        if len(buf) >= chunk_size:
            flush_chunk(chunk_idx, buf)
            buf = []
            chunk_idx += 1

            if args.stop_at_chunk is not None and chunk_idx > args.stop_at_chunk:
                print(f"[stop] --stop-at-chunk={args.stop_at_chunk} reached")
                break
            if args.limit is not None and total_rows_seen >= args.limit:
                print(f"[stop] --limit={args.limit} reached")
                break

    # Flush final partial chunk
    if buf and (args.stop_at_chunk is None or chunk_idx <= args.stop_at_chunk):
        flush_chunk(chunk_idx, buf)

    # ---- Aggregate ----
    print("\nAggregating all chunk summaries...")
    summary_paths = sorted(outdir.glob("chunk_*_summary.json"))
    if not summary_paths:
        print("No chunk summaries found — nothing to aggregate.")
        return

    final = _aggregate_summaries(summary_paths)
    final["input_file"] = str(inp)
    final["chunks_processed"] = len(summary_paths)
    final["chunk_size"] = chunk_size
    final["safety_net_applied"] = args.safety_net
    final["total_wall_time_seconds"] = round(time.time() - t_run_start, 1)

    fpath = outdir / "final_aggregated_summary.json"
    fpath.write_text(json.dumps(final, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY  (from {len(summary_paths)} chunks)")
    print(f"{'='*60}")
    print(f"Total cases:            {final['total_cases']:,}")
    print(f"Correct:                {final['correct']:,}")
    print(f"Wrong:                  {final['wrong']:,}")
    print(f"Review:                 {final['review']:,}")
    print(f"Errors:                 {final['errors']:,}")
    print(f"Accuracy (strict):      {final['accuracy_strict']:.4f}")
    print(f"Accuracy (excl review): {final['accuracy_excluding_review_and_errors']:.4f}")
    print(f"Rule hits: {final['rule_hits']}")
    print(f"\nWall time: {final['total_wall_time_seconds']}s "
          f"({final['total_cases']/max(final['total_wall_time_seconds'],1):.0f} rows/s)")
    print(f"\nWritten to: {fpath}")


if __name__ == "__main__":
    main()
