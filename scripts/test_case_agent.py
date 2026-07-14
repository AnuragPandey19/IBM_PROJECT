"""Autonomous test case generator for CHIMERA-FD.

Reads a YAML config that says how many cases per typology you want, then
runs an LLM in a loop until every target is met. Each generated batch is
schema-validated, deduplicated, and (optionally) live-tested against the
running backend before being appended to your output file.

Usage:
    python scripts/test_case_agent.py --config scripts/agent_config.<yourname>.yaml

Provider setup:
    Set ONE of these env vars (or add to a .env file at project root):
      OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, GROQ_API_KEY
    Ollama needs no key — it talks to http://localhost:11434.

Output:
    tests/authored/<author>.jsonl — the assembled JSONL file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)


# ---------------------------------------------------------------------------
# Schema of a valid test case (subset that we hard-validate)
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "entertainment", "food_dining", "gas_transport",
    "grocery_net", "grocery_pos",
    "health_fitness", "home", "kids_pets",
    "misc_net", "misc_pos", "personal_care",
    "shopping_net", "shopping_pos", "travel",
}
VALID_PROFILES = {"established", "new", "high_spender", "senior"}
VALID_LABELS = {"fraud", "legit"}
VALID_SEVERITIES = {"clear", "borderline", "edge"}

REQUIRED_TOP_FIELDS = {"id", "scenario", "expected_label", "typology", "payload"}
REQUIRED_PAYLOAD_FIELDS = {
    "card_number", "cardholder_name", "amount",
    "merchant_name", "merchant_category", "demo_profile",
}


def validate_case(case: dict[str, Any]) -> tuple[bool, str]:
    """Return (ok, reason). Reason is empty if ok."""
    if not isinstance(case, dict):
        return False, "not a dict"
    missing = REQUIRED_TOP_FIELDS - case.keys()
    if missing:
        return False, f"missing top fields: {sorted(missing)}"
    if case["expected_label"] not in VALID_LABELS:
        return False, f"bad expected_label: {case['expected_label']!r}"
    sev = case.get("expected_severity")
    if sev and sev not in VALID_SEVERITIES:
        return False, f"bad expected_severity: {sev!r}"

    p = case["payload"]
    if not isinstance(p, dict):
        return False, "payload not a dict"
    missing_p = REQUIRED_PAYLOAD_FIELDS - p.keys()
    if missing_p:
        return False, f"missing payload fields: {sorted(missing_p)}"
    if p["merchant_category"] not in VALID_CATEGORIES:
        return False, f"bad merchant_category: {p['merchant_category']!r}"
    if p["demo_profile"] not in VALID_PROFILES:
        return False, f"bad demo_profile: {p['demo_profile']!r}"
    try:
        amt = float(p["amount"])
    except (TypeError, ValueError):
        return False, f"amount not numeric: {p['amount']!r}"
    if amt <= 0:
        return False, f"amount not positive: {amt}"
    h = p.get("demo_hour_override")
    if h is not None:
        try:
            hi = int(h)
        except (TypeError, ValueError):
            return False, f"demo_hour_override not int: {h!r}"
        if not 0 <= hi <= 23:
            return False, f"demo_hour_override out of range: {hi}"

    return True, ""


def case_signature(case: dict[str, Any]) -> str:
    """Rough dedupe key so two near-identical cases don't both survive."""
    p = case.get("payload", {})
    parts = [
        case.get("typology", ""),
        case.get("expected_label", ""),
        f"{float(p.get('amount', 0)):.0f}",
        p.get("merchant_category", ""),
        p.get("demo_profile", ""),
        str(p.get("demo_hour_override", "")),
    ]
    return "|".join(parts)


# ---------------------------------------------------------------------------
# LLM providers — thin wrappers so the agent is provider-agnostic
# ---------------------------------------------------------------------------

@dataclass
class LLMClient:
    provider: str
    model: str
    temperature: float = 0.8

    def complete(self, system: str, user: str) -> str:
        p = self.provider.lower()
        if p == "openai":
            return self._openai(system, user, base_url=None,
                                api_key_env="OPENAI_API_KEY")
        if p == "groq":
            return self._openai(system, user,
                                base_url="https://api.groq.com/openai/v1",
                                api_key_env="GROQ_API_KEY")
        if p == "ollama":
            return self._openai(system, user,
                                base_url="http://localhost:11434/v1",
                                api_key_env=None)
        if p == "anthropic":
            return self._anthropic(system, user)
        if p == "gemini":
            return self._gemini(system, user)
        raise ValueError(f"Unknown provider: {self.provider!r}")

    # ---- OpenAI-compatible (also serves Groq + Ollama) ----
    def _openai(self, system: str, user: str,
                base_url: str | None, api_key_env: str | None) -> str:
        from openai import OpenAI
        key = os.environ.get(api_key_env) if api_key_env else "ollama"
        if api_key_env and not key:
            raise SystemExit(f"Env var {api_key_env} not set.")
        client_kwargs: dict[str, Any] = {"api_key": key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)
        r = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
        )
        return r.choices[0].message.content or ""

    def _anthropic(self, system: str, user: str) -> str:
        import anthropic
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("Env var ANTHROPIC_API_KEY not set.")
        client = anthropic.Anthropic(api_key=key)
        r = client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate text blocks
        return "".join(
            b.text for b in r.content if getattr(b, "type", "text") == "text"
        )

    def _gemini(self, system: str, user: str) -> str:
        from google import genai
        from google.genai import types
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise SystemExit("Env var GEMINI_API_KEY not set.")
        client = genai.Client(api_key=key)
        r = client.models.generate_content(
            model=self.model,
            contents=[user],
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=self.temperature,
            ),
        )
        return r.text or ""


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are generating test cases for a fraud detection ML \
model. You output JSONL — one JSON object per line, no wrapping array, \
no markdown fences, no commentary. Every JSON object must match the \
schema you are told. Every case's expected_label must be one that any \
reasonable human would agree with, given the payload described."""


def build_user_prompt(needed: dict[str, int], batch_size: int,
                      existing_signatures: set[str]) -> str:
    # Order under-covered typologies by deficit (largest gap first)
    focus = sorted(needed.items(), key=lambda kv: -kv[1])
    focus_str = ", ".join(f"{name} ({n} more)" for name, n in focus if n > 0)

    example_line = (
        '{"id":"TC-001","scenario":"Late-night electronics fraud",'
        '"description":"New card, $2800 electronics at 3AM",'
        '"expected_label":"fraud","expected_severity":"clear",'
        '"typology":"late_night_bulk_fraud","payload":{'
        '"card_number":"4532111122225678","cardholder_name":"Sarah Johnson",'
        '"amount":2800.00,"merchant_name":"TechMart Electronics",'
        '"merchant_category":"shopping_net","cust_email":"sj@example.com",'
        '"demo_profile":"new","demo_hour_override":3},'
        '"notes":"Textbook stolen-card pattern."}'
    )

    parts = [
        f"Generate exactly {batch_size} test cases as JSONL. No array, no fences, no commentary.",
        "",
        f"Focus this batch on: {focus_str}",
        "",
        "Schema (must match exactly):",
        "  id                  : string, unique — start from TC-100 range or higher for this batch",
        "  scenario            : short human-readable title",
        "  description         : one sentence explaining the scenario",
        f"  expected_label      : one of {sorted(VALID_LABELS)}",
        f"  expected_severity   : one of {sorted(VALID_SEVERITIES)}",
        f"  typology            : one of {sorted(set(needed.keys()))}",
        "  payload:",
        "    card_number         : any 16-digit test number as a string",
        "    cardholder_name     : any name",
        "    amount              : number, USD dollars (not INR)",
        "    merchant_name       : any merchant name (e.g. 'TechMart Electronics', 'Zomato', 'BigBasket')",
        f"    merchant_category   : one of {sorted(VALID_CATEGORIES)}",
        "    cust_email          : any email string",
        f"    demo_profile        : one of {sorted(VALID_PROFILES)}",
        "    demo_hour_override  : integer 0-23 (24h)",
        "  notes               : one-sentence justification of the label",
        "",
        "Rules:",
        "- Amounts are in USD (approx: $1 = ₹80 if you're thinking in INR).",
        "- Small amounts under $12 CANNOT be fraud test cases labeled clear — "
        "the model never auto-blocks small amounts; use 'card_testing' typology and set severity 'clear'.",
        "- Night hours are 0-5 inclusive.",
        "- Business hours are 9-18.",
        "- Do not repeat existing scenarios — vary amounts, merchants, ages, hours.",
        "",
        "Example (one line):",
        example_line,
        "",
        f"Existing scenario signatures already covered ({len(existing_signatures)}):",
    ]
    # Include a random sample of signatures so the LLM sees the diversity floor
    if existing_signatures:
        sample = list(existing_signatures)
        if len(sample) > 30:
            import random
            sample = random.sample(sample, 30)
        parts.append("  " + "\n  ".join(sample))
    parts.append("")
    parts.append(f"Now output exactly {batch_size} JSONL lines and nothing else.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------

def parse_jsonl(text: str) -> list[dict[str, Any]]:
    """Extract JSON objects from LLM output.

    Tolerates:
      - stray markdown fences (```json ... ```)
      - blank lines
      - lines that are pure prose
    """
    out: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


# ---------------------------------------------------------------------------
# Live validation against the backend
# ---------------------------------------------------------------------------

def live_ok(payload: dict[str, Any], base_url: str) -> tuple[bool, str]:
    try:
        r = requests.post(
            f"{base_url.rstrip('/')}/api/checkout",
            json=payload,
            timeout=10,
        )
    except requests.RequestException as e:
        return False, f"network: {e}"
    if r.status_code // 100 == 2:
        return True, ""
    try:
        detail = r.json().get("detail", r.text)
    except Exception:
        detail = r.text
    return False, f"{r.status_code}: {detail[:120]}"


# ---------------------------------------------------------------------------
# Coverage tracking
# ---------------------------------------------------------------------------

@dataclass
class Coverage:
    targets: dict[str, int]
    counts: dict[str, int] = field(default_factory=dict)

    def add(self, typology: str) -> None:
        self.counts[typology] = self.counts.get(typology, 0) + 1

    def needed(self) -> dict[str, int]:
        return {
            k: max(0, self.targets[k] - self.counts.get(k, 0))
            for k in self.targets
        }

    def total_target(self) -> int:
        return sum(self.targets.values())

    def total_have(self) -> int:
        return sum(self.counts.values())

    def done(self) -> bool:
        return all(self.counts.get(k, 0) >= v for k, v in self.targets.items())

    def status_line(self) -> str:
        segs = []
        for typ, target in sorted(self.targets.items()):
            have = self.counts.get(typ, 0)
            marker = "✓" if have >= target else "·"
            segs.append(f"{typ} {have}/{target}{marker}")
        return "  " + "  ".join(segs)


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=str, required=True,
                    help="Path to agent config YAML")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    author = cfg["author"]
    provider = cfg["provider"]
    model = cfg["model"]
    temperature = float(cfg.get("temperature", 0.8))
    targets = cfg["target_counts"]
    batch_size = int(cfg.get("batch_size", 10))
    max_iter = int(cfg.get("max_iterations", 20))
    validate = bool(cfg.get("validate_live", False))
    backend = cfg.get("backend_url", "http://localhost:8000")
    output_dir = Path(cfg.get("output_dir", "tests/authored"))
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{author}.jsonl"

    # ---- Load existing cases (resume support) ----
    existing_cases: list[dict[str, Any]] = []
    existing_sigs: set[str] = set()
    if out_file.exists():
        for line in out_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            existing_cases.append(obj)
            existing_sigs.add(case_signature(obj))

    cov = Coverage(targets=dict(targets))
    for c in existing_cases:
        typ = c.get("typology")
        if typ in cov.targets:
            cov.add(typ)

    print("── CHIMERA-FD test case agent ──")
    print(f"Author        : {author}")
    print(f"Provider      : {provider} ({model})")
    print(f"Target        : {cov.total_target()} cases across {len(targets)} typologies")
    print(f"Existing file : {out_file.relative_to(ROOT)} ({len(existing_cases)} cases)")
    print(f"Live validate : {'yes → ' + backend if validate else 'no'}")
    print()

    if cov.done():
        print("Coverage already met. Nothing to do.")
        print(cov.status_line())
        return

    llm = LLMClient(provider=provider, model=model, temperature=temperature)
    t0 = time.time()

    with open(out_file, "a", encoding="utf-8") as fout:
        for it in range(1, max_iter + 1):
            if cov.done():
                break
            needed = cov.needed()
            user_prompt = build_user_prompt(needed, batch_size, existing_sigs)
            try:
                raw = llm.complete(SYSTEM_PROMPT, user_prompt)
            except Exception as e:
                print(f"[iter {it}] LLM error: {e}")
                continue

            candidates = parse_jsonl(raw)
            n_raw = len(candidates)
            n_schema_ok = 0
            n_unique = 0
            n_live_ok = 0
            n_saved = 0

            for c in candidates:
                ok, reason = validate_case(c)
                if not ok:
                    continue
                n_schema_ok += 1

                sig = case_signature(c)
                if sig in existing_sigs:
                    continue
                n_unique += 1

                if validate:
                    live, why = live_ok(c["payload"], backend)
                    if not live:
                        continue
                    n_live_ok += 1

                # Save
                fout.write(json.dumps(c, ensure_ascii=False) + "\n")
                fout.flush()
                existing_sigs.add(sig)
                if c["typology"] in cov.targets:
                    cov.add(c["typology"])
                n_saved += 1

            live_msg = f"{n_live_ok} live-ok · " if validate else ""
            print(
                f"[iter {it}] LLM → {n_raw} → {n_schema_ok} schema-ok → "
                f"{n_unique} unique → {live_msg}{n_saved} saved"
            )
            print(cov.status_line())

    dt = time.time() - t0
    total = cov.total_have()
    print()
    if cov.done():
        print(f"✓ All targets met. {total} cases in {out_file.relative_to(ROOT)}")
    else:
        print(f"Ran out of iterations. {total}/{cov.total_target()} cases in {out_file.relative_to(ROOT)}")
        print("Rerun to keep adding.")
    print(f"Elapsed: {int(dt)}s")


if __name__ == "__main__":
    main()
