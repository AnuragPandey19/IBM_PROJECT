# CHIMERA-FD — v2 Model Dataset Generation Context

**Purpose of this document:** Complete historical and present context for
building a v2 candidate Sparkov model on multi-agent-generated training
data. This is a handoff doc for a fresh chat that has no prior memory
of the project. Read it end-to-end before proposing anything.

**Do NOT execute code without explicit approval from Anurag.**

---

## 1. Project overview (what CHIMERA-FD is)

CHIMERA-FD = *Cascaded Hybrid Inference with Multi-modal Explanations
and Recalibration for Adaptive Fraud Detection*.

- **Owner:** Anurag Pandey (IBM AI/ML intern, 2026 cohort)
- **Team:** Anurag + 3 members (Pankaj, Gurnoor, Sanvi) — team excluded
  from this specific v2 sandbox (Anurag + AI assistant only)
- **Sprint window:** 23 June – 30 July 2026 (about 10-12 days remaining
  at the time this doc was written)
- **Deployment:** Hugging Face Space Docker image at
  `https://undebuggedbit-chimera-fd.hf.space` (FastAPI backend +
  Next.js frontend served on port 7860)
- **Databases:** Postgres (prod on Render) / SQLite (local dev)

**Architecture — model pipeline in 5 stages:**

1. Raw checkout payload (8 fields) → feature builder (30 features)
2. LightGBM Stage 1 (Sparkov, trained on ~3.05M rows with `scale_pos_weight ≈ 400`)
3. Isotonic recalibration → calibrated probability
4. Threshold gate: `approve if p < 0.05`, `block if p > 0.30`, else `review`
5. Decision augmenter (3 post-model safety-net rules) → final decision + rule ids

**Two models loaded in the running service:**
- IEEE-CIS Stage 1 LightGBM + Stage 3 isotonic (research baseline)
- Sparkov Stage 1 LightGBM (the model actually serving `/api/checkout`)

Sparkov is the model this v2 experiment targets.

---

## 2. Current v1 model performance (present state)

The deployed v1 Sparkov model, evaluated on the Pankaj30m 3M-row
held-out labeled set with the decision augmenter turned ON:

| Metric | Value |
|---|---|
| Total cases | 3,000,000 |
| Correct | 1,959,051 (65.30 %) |
| Wrong | 167,384 (5.58 %) |
| Review | 873,565 (29.12 %) |
| Errors | **0** (zero engine errors on 3M rows) |
| Aggregate decisive accuracy (excl review) | **92.13 %** |
| Total fraud handled (block + review) | 93.02 % |

**Per-typology breakdown:**

| Typology | Verdict |
|---|---|
| routine_grocery (LEGIT) | 100 % correctly approved ✓ |
| fuel_purchase (LEGIT) | 100 % correctly approved ✓ |
| senior_routine (LEGIT) | 90.2 % approved (mild 8.84 % false-block issue) |
| corporate_lunch (LEGIT) | 96.7 % approved ✓ |
| wedding_order (LEGIT) | 69.8 % approved, 30 % review — fine |
| high_value_regular (LEGIT) | ⚠️ 60.6 % approve, **22.9 % false-blocked** — worst legit typology |
| late_night_hostel (LEGIT) | ⚠️ 39.5 % approved, **60.5 % review** — over-cautious |
| weekend_spike (FRAUD) | 99.9 % blocked ✓ |
| late_night_bulk_fraud (FRAUD) | 100 % blocked ✓ |
| cross_category_fraud (FRAUD) | 100 % handled (37.6 % blocked, 62.4 % review) |
| velocity_spike (FRAUD) | 100 % handled (mostly via augmenter review) |
| card_testing (FRAUD) | 🚨 **0 % blocked, 65 % review, 35 % MISSED (approved as legit)** — worst overall |

**Historical scale-invariance already proven (mentor briefing material):**
- V1 combined (714 rows): 93.2 % decisive accuracy
- V2 (150K rows): 93.4 %
- V3 = Pankaj30m (3M rows): 92.13 %

**External mentor briefing was DONE and APPROVED.** He specifically
approved the multi-agent-generated test cases as valid held-out
ground truth — on the strict condition that **the test cases are
never used for training / fine-tuning**. That condition must be
honoured throughout this v2 work.

---

## 3. The problem v2 is trying to solve

The v1 model has three specific weaknesses documented in
`docs/MODEL_AUDIT_POST_3M.md`:

**FRAUD side (recall problems):**
- **card_testing** — model catches 0 % via block, 65 % via review, 35 %
  slips through as approve. Root cause: Sparkov training data has zero
  card-testing examples ($1-$5 online misc purchases). The model
  learned `amount` as a monotonically-increasing risk feature — below
  ~$50 the fraud probability is effectively zero regardless of context.

**LEGIT side (false-block problems):**
- **high_value_regular** — 22.9 % of legit high-spender purchases get
  blocked. The model over-fits "high amount = fraud" because
  augmentation added FRAUD examples of high-ratio spending but no
  matching LEGIT counter-examples for premium cardholders making
  plausible $3-5K purchases (weddings, luxury retail, travel).
- **late_night_hostel** — 60 % of legit late-night hostel/worker
  purchases get sent to review (over-cautious). Root cause: the
  `is_night = int(hour < 6)` feature is a hard binary step function —
  it conveys zero gradient inside the "night" window, so the model
  cannot distinguish a 3 AM grocery run from a 5 AM one.

**Augmenter rule coverage gap (also documented in audit):**
- Rule R1 (`card_testing_small_amount`) fires **zero times** on the
  3M eval. The rule required `demo_profile == "new"` AND category in
  4 online categories, but the test data card_testing typology uses
  food_dining / grocery_net / gas_transport / grocery_pos across all
  profiles. Wrong assumption in the rule design.
- Rule R3 (`evening_new_high_amount`) also fires zero times. Very
  narrow trigger conditions.
- Only R2 (`velocity_spike_established`) fires — 324,657 times on 3M.

---

## 4. Previous failed attempt — read this carefully

**Yesterday** (2026-07-18), an augmentation-driven retrain was attempted
based on the audit's recommended fixes. The exact changes:

1. Widened `_make_card_testing()` amount range from `$0.50-$8`
   (`beta * 8 + 0.5`) to `$0.50-$50` (`beta * 50 + 0.5`).
2. Extended `_CARD_TESTING_CATEGORIES` from 4 categories to 6 — added
   `food_dining` and `grocery_net`.
3. Raised augmentation share defaults from 3 % + 3 % to 5 % + 5 %.
4. Added two new legit-rescue generator functions:
   `_make_high_value_legit()` (top-decile spenders at 3-8x avg,
   `is_fraud=0`) and `_make_senior_legit()` (mid-range spenders at
   1-3x avg, `is_fraud=0`), each at 2 % share.
5. Rewrote decision augmenter R1 with a two-tier block+review structure
   (block for amount < $3 in strict categories, review for $3-$10 in
   wider categories), dropped profile check.
6. Loosened R3 (hour window 20-23 → 19-23, amount threshold $1000 → $500,
   dropped profile check).

**Result: catastrophic regression.**

On the very first chunk of the 3M re-eval:

| Metric | Before | After | Delta |
|---|---|---|---|
| Correct | 65,220 | 38,173 | **-27,047** |
| Wrong | 5,608 | **24,268** | **+18,660** |
| Decisive accuracy | 92.13 % | **61.13 %** | **-31 pp** |

**Per-typology damage:**
- **high_value_regular:** was 22.9 % false-block, became **90.5 % false-block** — legit rescue augmentation made it WORSE
- **weekend_spike (fraud):** was 99.9 % blocked, became **67.6 % wrongly approved** — model forgot how to catch these
- **late_night_bulk_fraud (fraud):** was 100 % blocked, became **84.3 % wrongly approved** — same regression
- **corporate_lunch (LEGIT):** was 97 % approve, became **32.7 % wrongly blocked** — because widened card_testing augmentation labeled sub-$10 food_dining as fraud, and the model then blocked legit sub-$10 corporate lunches

**Root cause diagnosis (this is CRUCIAL to understand before designing
v2's dataset):**

The augmentation script generated FRAUD examples whose **feature
signatures overlapped with LEGIT examples the model was supposed to
approve**. Specifically:

- We told the model "sub-$10 food_dining = card_testing = FRAUD"
- The Pankaj30m test set contains legit corporate_lunch rows with
  amount=$5-$8 and category=food_dining
- Model correctly learned the augmentation pattern, but that pattern
  is INDISTINGUISHABLE from a corporate_lunch legit signature by
  the features it has access to

**The failure mode was NOT bad code. It was bad dataset design.**

Full revert was executed: all code changes rolled back, `augment_sparkov_training.py`
restored to original, `models/stage1_sparkov.pkl` restored via
`git checkout HEAD -- models/stage1_sparkov.pkl`, tests reverted.
Verified back to 96.55 % decisive accuracy on V1 (baseline restored).

**Do not repeat this class of mistake.** The v2 dataset's core
requirement is that **fraud rows must not share feature signatures with
legit rows** — every fraud example needs a matched legit counter-example
so the model learns what actually distinguishes them.

---

## 5. Why we're building a fresh dataset (not another augmentation)

Augmentation is a band-aid — we're taking an existing training set and
adding a small slice on top. The share is constrained by
`scale_pos_weight` mechanics and by the need to preserve the original
distribution. Small-percentage augmentation can either be too weak
(model doesn't learn) or too aggressive (yesterday's regression).

A **freshly-generated training dataset** built with our multi-agent
pipeline lets us:

1. **Design the distribution intentionally** — we control every row's
   fraud/legit ratio, category mix, profile mix, amount distribution,
   hour distribution.
2. **Guarantee paired examples** — for every fraud row, a matched legit
   counter-example with the same category + amount range but different
   profile / prior history, so the model learns the distinguisher is
   NOT the category alone (this directly prevents yesterday's failure
   mode).
3. **Anti-contaminate against the held-out test set** — every row
   goes through a check that rejects (amount, category, profile, hour)
   tuples that also appear in the Pankaj30m held-out data. **Zero train/test
   leakage by construction.**
4. **Match Sparkov's real distribution** — using statistical templates
   extracted from Sparkov's training data instead of synthetic
   distributions invented on the fly.

**The multi-agent pipeline is proven** — it's the same architecture that
produced the 3M held-out test set the mentor already approved. The only
difference is the dataset's PURPOSE (training vs held-out evaluation)
and its DESIGN (paired examples, distribution matching, anti-contamination).

---

## 6. Previous test-case generation methodology (for reference)

This is a description of how the TEST cases were built. The v2 training
dataset will use the SAME architecture but must serve a DIFFERENT
purpose, so the design constraints differ (see section 8).

**Multi-agent pipeline architecture (per team member):**

- **3 generator agents** running in parallel, each using a different
  LLM provider (Claude, GPT, Grok, DeepSeek, NVIDIA, Meta, Qwen, Gemini,
  Kimi, ByteDance, Microsoft — mix and rotate)
- **1 validator agent** (4th agent) that checks each generated row for:
  - schema (field names + types)
  - scenario ↔ label consistency
  - feature schema conformance
  - JSONL row shape
  - Fixable errors → auto-corrected in place
  - Semantically wrong rows → sent back to originating agent to regenerate

**Team scaling:**
- 3 team members each run this 4-agent pipeline in parallel
- Total: **12 diverse LLM agents active simultaneously**

**Anurag's quality gate:**
- All 12-agent output lands with Anurag
- Manual pass — sanity-check labels, spot drift, resolve conflicts
- Only after this gate does the batch enter scoring

**Model isolation guarantees enforced everywhere:**
- Only the 8 checkout fields reach the model — labels held back
- Test cases never stored or trained on — **zero fine-tuning**
- Labels + typology metadata used only for post-scoring comparison

**This produced three test batches so far:**
- V1 (Gurnoor): 714 rows combined
- V2 (Pankaj v1): 150,000 rows
- V3 (Pankaj30m): 3,000,000 rows — the current held-out gold standard

A separate V3 batch (Gurnoor 1M) was received with a **completely
different schema** (fields the model can't consume, categories in Title
Case, different label vocabulary). Rejected and schema spec sent back
for regeneration. See `docs/TestCase_Schema_Spec_for_Gurnoor.txt` for
the exact schema every payload must follow — this same schema applies
to v2 training rows.

---

## 7. Constraints that MUST be respected while building v2's dataset

**Isolation constraints (hard rules — never break):**

- **Work ONLY inside `v2-chimera-fd/`.** Never modify any file outside
  this folder. Not `../api/`, not `../models/*.pkl` (except reading v1
  as baseline reference), not `../scripts/*`, not `../src/`, not
  `../frontend/`, not `../tests/`, not `../data/` (except read-only
  access to `../data/processed/sparkov/train_features.parquet` for
  extracting statistical templates).

- **Anti-contamination is mandatory.** Every generated row must be
  checked against `../evaluation/test_cases/Pankaj30m.jsonl` and any
  other file in `../evaluation/test_cases/`. Reject any row whose
  (amount, category, profile, hour) tuple exactly matches a test row.
  This is a hard requirement for the "zero fine-tuning" mentor claim.

- **v1 model file is sacred.** `../models/stage1_sparkov.pkl` is the
  deployed model. Do NOT overwrite it. Read-only reference OK. When v2
  is ready to promote, a dedicated `promote.py` script will copy the
  v2 pkl into the v1 location — not before, not manually.

- **Never touch the held-out test cases.** They are held out from
  training by mentor-approved policy. Not for training, not for
  fine-tuning, not for reference, not for validation-set style splits.
  They are strictly for post-training evaluation only.

- **v2 folder is `.gitignore`d + `.dockerignore`d.** Nothing generated
  in this folder should ever reach a git remote or a Docker image.
  Verify this with `git check-ignore` if unsure.

**Design constraints (from the audit + yesterday's failure):**

- **Statistical templates first.** Extract amount / hour / category
  distributions per typology per profile from the actual Sparkov
  training data (`../data/processed/sparkov/train_features.parquet`).
  Feed these to agents as constraints. Do NOT invent distributions.
  Yesterday's failure was directly caused by using the developer's
  opinion of what "card testing" looks like instead of statistical
  reality.

- **Paired generation.** Every generated fraud row needs a matching
  legit counter-example. Same category, similar amount, different
  profile / prior history / hour. The model must learn what
  distinguishes fraud from legit at the same feature signature —
  category alone or amount alone are insufficient.

- **Balanced batches per typology.** Weak fraud typologies (card_testing,
  velocity_spike, cross_category_fraud) get more rows. Weak legit
  typologies (high_value_regular, senior_routine, late_night_hostel)
  get legit-rescue rows. Strong typologies (routine_grocery,
  fuel_purchase, weekend_spike, late_night_bulk_fraud) get minimal
  maintenance rows to prevent regression.

- **Schema strictness.** Every row conforms exactly to the Sparkov
  payload schema documented in `docs/TestCase_Schema_Spec_for_Gurnoor.txt`.
  Categories from the Sparkov snake_case vocabulary only. Profiles
  from `{new, established, senior, high_spender}`. Labels
  `{fraud, legit}`. Severity `{clear, borderline, edge}`. Typology
  from the canonical 12.

- **Provider diversity.** At least 5 different LLM providers across
  each batch — not just Meta + Qwen. Mentor briefing explicitly claims
  12-agent diversity; this dataset must live up to that story.

- **Multi-check validator.** Schema check + semantic check + distribution
  check + duplicate check + anti-contamination check. Yesterday's
  validator only did schema — that's insufficient.

- **Small experiments first.** 5K rows initial, then 30K, then 65K.
  Never generate a 100K + batch as the first attempt. Every batch runs
  through v2 training on a smaller labeled set (V1, 714 rows, 30 seconds)
  to spot-check for regression before scaling up.

- **Strict promotion gate.** v2 is promoted ONLY if it beats v1 on
  the Pankaj30m held-out set AND no legit typology regressed by more
  than 1 pp AND card_testing block-rate improved by ≥ 10 pp AND
  no false-block rate increased by more than 3 pp. If ANY criterion
  fails, v2 discarded, v1 continues serving.

---

## 8. Working directory + folder layout

**All work happens in `v2-chimera-fd/` — this folder ONLY.**

Already created (see `v2-chimera-fd/README.md` for full spec):

```
v2-chimera-fd/
├── README.md                             ← isolation rules, promotion criteria
├── models/
│   └── stage1_sparkov_v1_baseline.pkl    ← copy of deployed v1 (comparison baseline)
├── dataset_generation/
│   ├── prompts/                          ← per-typology agent prompts (to write)
│   ├── validators/                       ← multi-check validator (to write)
│   ├── templates/                        ← Sparkov statistical templates JSON (to extract)
│   └── output/                           ← generated JSONL dataset (to produce)
├── scripts/                              ← v2-specific retrain + eval + promote scripts
└── evaluation/                           ← v1 vs v2 comparison outputs
```

**Reference files elsewhere in the repo (READ-ONLY):**

| Purpose | Path |
|---|---|
| Model audit (why we're doing this) | `docs/MODEL_AUDIT_POST_3M.md` |
| Schema spec (exact format for every row) | `docs/TestCase_Schema_Spec_for_Gurnoor.txt` |
| Project journal (broader context) | `docs/PROJECT_JOURNAL.md` |
| Decision augmenter (rule reference) | `api/services/decision_augmenter.py` |
| Model service (thresholds, decision logic) | `api/services/model_service.py` |
| Feature builder (`_build_sparkov_row`) | `api/routes/checkout.py:239-318` |
| Customer profile constants | `api/routes/checkout.py:80-157` |
| Sparkov feature engineering | `src/chimera_fd/features/sparkov_engineering.py` |
| Original training script (do not modify) | `scripts/train_sparkov.py` |
| Original augmentation script (do not run) | `scripts/augment_sparkov_training.py` |
| Held-out test set (never train on) | `evaluation/test_cases/Pankaj30m.jsonl` |
| Sparkov training data (for template extraction) | `data/processed/sparkov/train_features.parquet` |

---

## 9. Deadline + priority context

- **Internship deadline:** 30 July 2026 (~10-12 days remaining)
- **Mentor briefing:** DONE, approved
- **External mentor's stance:** synthetic test cases are OK for
  continued evaluation IF training isolation is preserved. He was
  specific about this.

**Concurrent priorities (Anurag is juggling):**
- Written project report (~2 days) — mandatory deliverable
- Video demo recording (~3 hours) — portfolio value
- v2 dataset experiment — 3-5 days if it works, ~30 seconds to discard
  if it doesn't

If the v2 experiment shows early signs of regression on the small
labeled set (V1, 714 rows), STOP and switch back to report work.
Sunk-cost fallacy is not welcome here.

---

## 10. What NOT to do

- Do not modify anything outside `v2-chimera-fd/`
- Do not overwrite `../models/stage1_sparkov.pkl`
- Do not use held-out test cases as training data
- Do not generate rows without running them through the multi-check
  validator
- Do not skip anti-contamination checks
- Do not scale up batch size before a small batch has been trained
  + evaluated
- Do not promote v2 until the strict gate criteria pass
- Do not `pip install` — reuse the parent `.venv`
- Do not commit anything from `v2-chimera-fd/` — it's ignored
- Do not push to HF Space — v2 folder is in `.dockerignore`
- Do not execute code without Anurag's explicit approval

---

## 11. What to do first (starter checklist)

1. Re-read this document top to bottom.
2. Re-read `v2-chimera-fd/README.md`.
3. Skim `docs/MODEL_AUDIT_POST_3M.md` for the full audit context.
4. Skim `docs/TestCase_Schema_Spec_for_Gurnoor.txt` for the exact
   payload schema.
5. Look at how `_build_sparkov_row` in `api/routes/checkout.py`
   converts a payload into 30 features — that's what the model
   ultimately consumes.
6. Look at `scripts/augment_sparkov_training.py` to understand
   yesterday's (failed) approach — so you know what NOT to do.
7. Confirm your understanding back to Anurag in your own words:
   - What went wrong yesterday
   - Why a fresh dataset is different from augmentation
   - What isolation and anti-contamination guarantees you'll enforce
   - Which folder is the only one you'll touch
8. Once confirmed, propose the extract-templates step (small script
   that reads Sparkov training parquet, computes per-typology
   distributions, writes JSON to `dataset_generation/templates/`).
9. Do NOT execute anything yet — wait for Anurag's approval on each
   step.

---

## 12. One-line summary

Build a synthetic multi-agent-generated training dataset inside
`v2-chimera-fd/` that matches Sparkov's statistical distribution,
generates fraud + paired legit counter-examples, anti-contaminates
against the held-out 3M test set, and passes a strict per-typology
promotion gate — without touching any file outside the sandbox.
