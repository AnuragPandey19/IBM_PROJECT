# CHIMERA-FD Model & Backend Audit — Post 3M-Row Evaluation

**Date:** 2026-07-18
**Author:** Anurag Pandey (with agent-assisted code review)
**Scope:** Model prediction quality, decision-augmenter behaviour, feature
builder correctness, training-pipeline gaps, backend inference-time
distribution mismatches, and observability. Frontend touched only where
schema visibility is required.
**Out of scope:** Auth, CI/CD, security, multi-tenancy (all covered
previously and passed regression).

**Evidence base:**
- V1 (Gurnoor combined, 714 rows) — 93.2 % decisive accuracy
- V2 (Pankaj v1, 150K rows) — 93.4 % decisive accuracy
- V3 (Pankaj v2 / 3M rows, new) — 92.1 % decisive accuracy
- Rule-hit counts + confusion matrices from
  `evaluation/results/pankaj_30m/final_aggregated_summary.json`
- Direct read of:
  - `api/services/model_service.py`
  - `api/services/decision_augmenter.py`
  - `api/routes/checkout.py`
  - `src/chimera_fd/features/sparkov_engineering.py`
  - `scripts/augment_sparkov_training.py`

**Comparison to first audit** (`docs/MODEL_AUDIT_POST_TESTING.md`, 2026-07-17):
- ✅ Resolved: B-2 (shared augmenter module), B-5 (rules_triggered DB column),
  T-1 (card_testing augmentation), T-2 (velocity_spike augmentation),
  T-6 (typology stress eval in training).
- ⚠️ Partially resolved: M-1 (card_testing improved 0 → 65 % review, but
  block rate still 0 %). M-2 (velocity_spike improved 5 % → 95 % handled
  via review, driven by augmenter not by model).
- ❌ Not yet resolved: M-4 (late_night_hostel over-triggered),
  T-3 (typology-aware sample weights), T-5
  (customer-category diversity + hour_risk_smooth features).

## ID Scheme

- **M-x** — model characterisation / prediction quality (visible at inference)
- **T-x** — training-script / training-data problems (root cause upstream)
- **B-x** — backend pipeline problems (feature builder, thresholds, safety
  net, augmenter, model service)
- **F-x** — frontend gaps requiring schema change
- **O-x** — observability, telemetry, ops

Priority: **P0** (ship blocker for next iteration), **P1** (must-do before
final deliverable), **P2** (nice-to-have).

---

## 1. Model-behaviour findings (M-x)

### M-6 — `card_testing` remains structurally uncatchable at scale (P0)

- **Evidence:** V3 (249,607 card_testing rows): 0 blocked · 162,302 review
  (65 %) · 87,305 approved (35 %). **Zero block rate despite retrain.**
- **Where visible:** `final_aggregated_summary.json` → per_typology.card_testing.
- **Interpretation:** the augmented retrain moved the model from
  "confident approve" (raw ~3 × 10⁻⁸) to "uncertain" (raw ~0.05–0.30 band —
  i.e. review bucket). Progress, but insufficient. Model has not learned to
  cross `_SPARKOV_BLOCK_ABOVE = 0.300` for these small-amount patterns.
- **Fix candidates:**
  1. Add an **explicit BLOCK path** in the decision augmenter for the
     most obvious card-testing profile (amount < $3, category strictly
     `misc_net`/`entertainment`, no prior history). This is a rule change,
     not a model change — fast to ship.
  2. Widen the augmentation amount range in
     `scripts/augment_sparkov_training.py:102` — currently
     `beta(1.2, 5.0) * 8.0 + 0.5` gives $0.50–$8. Real card-testing goes
     up to ~$50. See T-7.
  3. Increase augmentation share from 3 % → 5–7 % of training so the model
     sees more of the pattern (see T-8).

### M-7 — `high_value_regular` false-block on legit high-spender (P0)

- **Evidence:** V3 (250,321 high_value_regular rows): 89,472 wrong (57,387
  block + wrong-side of review 41,205). **22.9 % blocked outright.**
  A legit high-value regular customer has a 1-in-4 chance of being
  wrongly blocked in production.
- **Location:** `_SPARKOV_APPROVE_BELOW = 0.050` and
  `_SPARKOV_BLOCK_ABOVE = 0.300` in `api/services/model_service.py:243–244`
  are model-global. Model is emitting scores in the block band for
  legitimately high amounts on established `high_spender` profiles.
- **Root cause:** augmentation added FRAUD examples of high-ratio spending
  (velocity_spike) but did NOT add LEGIT examples of the same pattern
  (established high spender making a plausible $3–5K purchase — wedding,
  premium electronics). Model now over-fits "high ratio = fraud."
- **Fix candidates:**
  1. **Add legit-rescue augmentation** — synthetic legit rows for
     `high_spender` profile with amounts in [3× avg, 8× avg] labelled
     `is_fraud = 0`. Balances the model's ratio prior. See T-10.
  2. **Profile-aware threshold override** in
     `_decide_sparkov`: if `profile.avg_past_amt > 200` AND amount is
     within a plausible high-spender purchase category (`shopping_net`,
     `travel`, `home`), raise `block_above` to 0.6 for that request only.
  3. **Track "legit rescue"** as a first-class augmenter rule that can
     move `block → review` (currently rules only move `approve → review`).

### M-8 — `late_night_hostel` legit over-blocking still present (P1)

- **Evidence:** V3 (250,058 rows): 0 blocked · 151,201 review (60.5 %) ·
  98,857 approved (39.5 %). No block, but review-rate is 5× wedding_order.
- **Location:** `is_night = int(hour < 6)` in
  `src/chimera_fd/features/sparkov_engineering.py:49` AND in
  `api/routes/checkout.py:286`. Hard binary step-function.
- **Root cause:** the model has learned `is_night = 1` → uncertainty.
  Every legit hostel-worker ordering groceries at 2 AM triggers the same
  uncertainty as a fraudster. `is_night` conveys ZERO gradient — a 3 AM
  purchase and a 5 AM purchase look identical to the model.
- **Fix:** T-5 from previous audit is still open. Replace `is_night` with
  a **continuous `hour_risk_smooth`** feature computed from the training
  distribution: EMA-smoothed per-hour fraud rate ∈ [0, 1]. Retrain.
- **Expected impact:** review-rate on late_night_hostel drops from 60 %
  → 15–25 % (order-of-magnitude of the underlying fraud-rate signal).

### M-9 — `senior_routine` false-block cluster (P1)

- **Evidence:** V3 (249,664 rows): 22,075 blocked (8.84 %). Only fraud-type
  in the legit-typology basket where the model actively BLOCKS in
  significant volume.
- **Interpretation:** the retrained model has learned that
  `demo_profile = "senior"` combined with certain merchant categories
  (likely `shopping_net`, `travel`) is suspicious — because velocity_spike
  augmentation INCLUDES senior profile in its target list
  (`api/services/decision_augmenter.py:134`). Senior + amount > 5× avg is
  what the augmenter flags. The retrain baked this bias in.
- **Fix:** balance velocity_spike augmentation with matching legit-senior
  rows at ratios in [3, 5] labelled `is_fraud = 0`. Or narrow the
  velocity_spike rule to `established` only (see B-10).

### M-10 — Model score distribution is bimodal at scale (P1)

- **Evidence:** looking at chunk-level `counts_by_predicted` across V3 —
  block/review/approve fractions are highly consistent per chunk (std
  dev < 0.5 percentage points across 30 chunks). Distribution is NOT
  shifting mid-run. Confirms deterministic scoring, but ALSO signals
  the model is stuck in three narrow score bands, not smoothly graded.
- **Implication:** threshold-tuning alone cannot close card_testing —
  there is no "just below block" band to push into block.
- **Fix:** deferred — requires deeper structural changes (per-typology
  sample weights, T-3) to spread the score distribution.

---

## 2. Training-pipeline findings (T-x)

### T-7 — `card_testing` augmentation amount range is too narrow (P0)

- **Location:** `scripts/augment_sparkov_training.py:102–103`:
  `amounts = rng.beta(1.2, 5.0, size=n) * 8.0 + 0.50` → range $0.50–$8.50.
- **Problem:** real card-testing patterns extend up to ~$50 (larger
  disposable-good purchases used to verify a stolen card). The Pankaj 3M
  test set has card_testing amounts extending beyond $8, so the trained
  model has never seen "card testing at $15" as fraud → treats it as legit.
- **Fix:** widen to $0.50–$50 with a heavy-lower-tail:
  `beta(1.2, 5.0, size=n) * 50.0 + 0.50` (still concentrated below $10
  but with a long right tail).
- **Also:** category distribution should include `grocery_net` and
  `food_dining` at low weight — card-testing fraudsters use whichever
  category has the lowest per-txn friction that day.

### T-8 — Augmentation share too small for target improvement (P1)

- **Current:** 3 % card_testing + 3 % velocity_spike (default in
  `augment_sparkov_training.py:170–173`).
- **Evidence:** at 3 % share the model sees roughly 91,500 card_testing
  fraud examples in a 3.05 M training set. The 3M eval hit 249K
  card_testing rows and blocked zero. The ratio suggests the model has
  not learned the pattern strongly enough — augmentation is diluted.
- **Fix:** raise to 5 % + 5 % (152K each). Retrain time stays under
  15 min. Expected block-rate improvement on card_testing: 0 % → 20–30 %.
- **Risk:** widening augmentation to > 8 % starts distorting the training
  distribution enough that PR-AUC on the aggregate test set can regress.
  Ceiling is ~7 % per typology per the class-imbalance literature.

### T-9 — No legit-rescue augmentation for over-blocked typologies (P0)

- **Location:** `scripts/augment_sparkov_training.py` — script generates
  only FRAUD (label = 1) augmentation. No corresponding legit-rescue
  generator.
- **Problem:** two legit typologies are being over-blocked in production:
  - `high_value_regular` 22.9 % blocked (see M-7)
  - `senior_routine` 8.84 % blocked (see M-9)
- **Fix:** add a `_make_high_value_legit(base_df, n, rng)` function that:
  - Samples `cc_num` from high-spender profiles (top-decile avg_past_amt)
  - Amounts 3×–8× their historical mean
  - Categories: `shopping_net`, `travel`, `home` (plausible high-spender
    categories)
  - `is_fraud = 0`
  - 2 % of training set (~60K rows)
- **Also add** `_make_senior_legit(base_df, n, rng)` — senior profiles
  purchasing wide category range at 1×–3× their historical mean.

### T-10 — Sample weights are still typology-blind (P1)

- **Location:** `stage1_lightgbm.py` (implicit). Global `scale_pos_weight
  ≈ 400` for Sparkov. Every fraud row weighs the same, whether it is a
  "seen a thousand times" typology (weekend_spike) or a "seen 91K times
  through augmentation" typology (card_testing).
- **Fix:** in the training script, pass a per-row `sample_weight` vector
  that boosts card_testing + velocity_spike augmented rows by 2×. The
  model puts extra loss on getting these right.
- **Where:** modify `chimera_fd/models/stage1_lightgbm.py` to accept a
  `sample_weights` argument and pass it into `lgb.Dataset`. Update the
  training script to set weights per augmented row.

### T-11 — Feature engineering still missing `hour_risk_smooth` and `cust_category_diversity_before` (P1)

- Same as T-5 from previous audit. Not implemented.
- **Priority for next iteration:** these two features address M-8 and
  cross_category_fraud (which V3 shows at 37.6 % blocked — better than
  before but still weak).

### T-12 — Retrain does not automatically regenerate `sparkov_feature_importance.csv` (P2)

- **Symptom:** after augmented retrain, feature-importance snapshot in
  reports/ is stale. Slide 10 of the briefing still shows `card1 target
  encoding` as top feature — that is IEEE-CIS, not Sparkov post-retrain.
- **Fix:** in `scripts/train_sparkov.py`, always write both
  `sparkov_feature_importance.csv` AND update `reports/sparkov_evaluation.json`
  at the end of every retrain (single source of truth).

---

## 3. Backend / inference-pipeline findings (B-x)

### B-7 — Two of three augmenter rules never fire at scale (P0)

- **Evidence:** V3 rule_hits — `velocity_spike_established`: 324,657.
  `card_testing_small_amount`: **0**. `evening_new_high_amount`: **0**.
- **Location:** `api/services/decision_augmenter.py:114–122` (R1) and
  `144–153` (R3).
- **Root cause R1 (card_testing):** the rule requires
  `demo_profile == "new"` AND `amount < settings.safety_net_card_testing_max_amount`
  (default $10) AND category in `_CARD_TESTING_TARGET_CATEGORIES` (only
  4 categories). Pankaj 3M card_testing typology mixes ALL profiles and
  spans amounts wider than $10. Rule preconditions almost never hold.
- **Root cause R3 (evening_new_high):** requires profile=new AND
  hour ∈ [20, 23] AND amount > $1000. Very narrow — test data does not
  concentrate here.
- **Fix R1 (P0):**
  - Drop the `profile == "new"` requirement (real fraudsters may use
    stolen cards from any profile).
  - Add a **BLOCK tier**: amount < $3 AND category in target set →
    `block` (not `review`).
  - Keep `review` tier for $3 ≤ amount < $10.
  - Extend target categories to include `food_dining`, `grocery_net`
    (fraudsters test with any low-friction merchant).
- **Fix R3 (P1):** widen hour to [19, 23], amount threshold to $500 (still
  meaningful signal but fires more often), drop hard profile=new.

### B-8 — Small-amount safety net in `_decide_sparkov` is still one-directional (P0)

- **Location:** `api/services/model_service.py:340–345`.
- **Current behaviour:** if amount ≤ $12 AND prob > 0.30 → force review.
  This only fires when the model already WANTED to block. Card-testing
  at $1.49 scores 3 × 10⁻⁸ — safety net never triggers, model returns
  "approve" cleanly.
- **This is the same B-1 finding from the previous audit.** Marked
  "resolved by decision_augmenter" — but the augmenter's own R1 also
  fails to fire (see B-7). So this class of fraud has TWO layers of
  safety net that both silently no-op.
- **Fix:** the augmenter fix in B-7 covers this. Once R1 fires reliably
  with wider preconditions + BLOCK tier, the small-amount safety net can
  be simplified to a comment: "handled by decision_augmenter R1."

### B-9 — `_build_sparkov_row` hardcodes `cust_merch_dist_km = 5.0` (P1)

- **Location:** `api/routes/checkout.py:307`.
- **Problem:** every API-authenticated checkout has a fixed 5 km distance.
  Training data has this feature varying from 0 km to hundreds. Model
  sees a constant at inference — that feature contributes zero variance
  at prediction time.
- **Impact:** limited — `cust_merch_dist_km` is not a top-15 feature in
  Sparkov importance rankings. But it IS a train/serve distribution
  mismatch that we should either fix or explicitly document.
- **Fix:** either
  1. Compute real distance if request carries merchant lat/long
     (unusual for a checkout API but possible for internal integrations).
  2. Draw a plausible distance from a per-profile distribution
     (e.g. sample from `N(15, 20)` km per profile, clipped ≥ 0).
- **Priority:** low — production merchant integration would fix this
  naturally.

### B-10 — Augmenter rules cannot rescue block→review (P1)

- **Location:** `api/services/decision_augmenter.py:106–107` and
  `155–158`. The function has an explicit invariant:
  ```
  if raw_decision != "approve":
      return raw_decision, triggered
  ```
- **Design intent (from module docstring):** "rules never approve or
  unblock — safety through conservatism." Good default.
- **Problem revealed by 3M:** `high_value_regular` is being blocked at
  22.9 % — but there is no path to rescue those. A rule like
  "if profile is established high-spender AND amount is within 5× of
  their avg AND category is `shopping_net`/`travel` → block→review" would
  reduce the customer harm without unblocking every high-amount txn.
- **Fix:** add an optional `legit_rescue` rule tier. Preserve the "never
  approve" invariant, but ALLOW `block → review` for narrowly-defined
  legit patterns. Feature-flagged so ops can disable.
- **Alternative:** address at training data level (T-9) so the model
  itself stops emitting block for these patterns. Slower but cleaner.

### B-11 — Threshold constants are class attributes, not `Settings` (P2)

- **Location:** `api/services/model_service.py:243–244`:
  ```
  _SPARKOV_APPROVE_BELOW = 0.050
  _SPARKOV_BLOCK_ABOVE = 0.300
  ```
  Class-level constants. Not overridable via env var.
- **Impact:** cannot A/B two threshold sets in production without a code
  change + redeploy. Not a big deal today, but future ops burden.
- **Fix:** move to `Settings` as `sparkov_approve_below` and
  `sparkov_block_above`. Keep the class constants as defaults.

### B-12 — Model warmup does not exercise the augmenter (P2)

- **Location:** `api/services/model_service.py:104–124`.
- **Problem:** warmup calls `score_sparkov(dummy)` — the raw model. The
  augmenter is never touched at startup. If the augmenter has a bug
  (e.g. missing settings key), first real request will crash.
- **Fix:** in warmup, also invoke `apply_safety_nets(dummy_payload,
  dummy_profile, "approve", 0.01)`. Ensures the module is import-clean
  and the settings keys resolve.

---

## 4. Frontend findings (F-x)

### F-3 — Analyst dashboard does not show per-typology rule fire counts (P1)

- **Depends on:** B-5 (already in place — `rules_triggered` column exists).
- **Missing:** a `/analytics/rules` view showing counts broken down by
  typology label (available in the `Transaction.raw_features` JSON as
  `demo_profile` + inferable from the row).
- **Value:** would let the ops team see which typologies each rule is
  actually catching (e.g. is card_testing_small_amount catching the right
  pattern or is it firing on legit small purchases?). Directly enables the
  augmenter tuning cycle.
- **Fix:** add a `/api/analytics/rule-hits-by-typology` route that
  aggregates from the Prediction table, and a small stacked bar chart on
  the analytics page.

### F-4 — SHAP waterfall for augmented decisions doesn't show which rule fired (P2)

- **Location:** `frontend/src/app/transactions/[id]/page.tsx` (assumed).
- **Current:** SHAP waterfall shown as-is. `rules_triggered` badge shown
  separately.
- **Missing:** when a rule fires, the SHAP waterfall should include a
  footer note: "This decision was augmented by rule X. The model's raw
  preference was Y." Preserves interpretability transparency and helps
  analysts understand the two decision layers.

---

## 5. Observability findings (O-x)

### O-1 — No per-typology telemetry in production (P1)

- **Symptom:** we discovered card_testing 0-block only after running the
  labeled test suite offline. If real production traffic hit the same
  pattern, we would not see it in the analytics dashboard because
  production transactions don't carry a `typology` label.
- **Fix:** add a lightweight `heuristic_typology` field computed
  server-side from the checkout payload:
  - amount < $10 + misc_net/entertainment → `card_testing_like`
  - amount > 5× profile avg → `velocity_spike_like`
  - hour 20-23 + new profile + amount > 1000 → `evening_new_high_like`
  - else → `unclassified`
  Persist to `Transaction.raw_features` so analytics can aggregate.
- **Value:** ops team can watch the block-rate for `card_testing_like`
  in real time. If it drifts below expected floor, alarm.

### O-2 — Rule-hit counter is a Counter, not persisted to a metrics store (P2)

- Currently `rule_hits` is only in `Prediction.rules_triggered` (per-row).
  Aggregate metrics require SQL queries.
- **Fix:** add a lightweight in-memory counter in `ModelService` that
  increments per rule fire, exposed via `/metrics`. Prometheus-compatible
  text format.

### O-3 — No SLO / SLA definition for the review-bucket cap (P2)

- **Current:** V3 review rate 29.1 % — analyst funnel is very large.
- **Missing:** an operational SLO like "review rate must stay below 25 %
  of total traffic; if breach, alert." Right now we have no target and
  no alarm.
- **Fix:** define SLOs in `docs/OPERATIONS.md`:
  - Decisive accuracy ≥ 90 % (excl review)
  - Review rate ≤ 25 % of traffic
  - Zero engine errors per 100K requests
  - Rule-hit fraction ≥ 5 % of `approve` decisions (i.e. safety net
    is doing real work)

---

## 6. Recommended execution order (post-briefing, pre-July-30)

### Week 1 (2–3 days) — high-leverage rule + augmentation fixes

1. **B-7:** Rewrite decision_augmenter R1 with BLOCK tier + wider preconditions.
2. **B-7:** Loosen R3 (evening_new_high) hour + amount thresholds.
3. **T-7 + T-8:** Widen card_testing augmentation to $50 range, raise share to 5 %.
4. **T-9:** Add legit-rescue augmentation for high_value_regular + senior_routine.
5. **Retrain Sparkov Stage 1** (~15 min).
6. **Run V3 3M eval** again (~2 hrs) — compare before/after.

**Success target:**
- card_testing block-rate 0 % → 20 %+ (with augmenter block tier)
- high_value_regular false-block 22.9 % → < 10 %
- senior_routine false-block 8.84 % → < 4 %
- Decisive accuracy holds ≥ 91 %

### Week 2 (2–3 days) — structural features

7. **T-11:** Add `hour_risk_smooth` + `cust_category_diversity_before`.
8. **T-10:** Sample weights on augmented rows.
9. **Second retrain + V3 re-eval.**

**Success target:**
- late_night_hostel review rate 60 % → 25 %
- cross_category_fraud block rate 37.6 % → 55 %

### Week 3 (2 days) — ops, observability, dashboard

10. **O-1:** heuristic_typology field in Transaction.raw_features.
11. **F-3:** per-typology rule-hits view in analytics dashboard.
12. **F-4:** SHAP waterfall footer note when augmenter fires.
13. **O-3:** SLOs written into OPERATIONS.md.
14. **B-11 + B-12:** thresholds via Settings, warmup exercises augmenter.

### Buffer (2 days)

15. Written project report.
16. Video demo recording.
17. Viva prep.

---

## 7. Success criteria for the next iteration

**Model level (post-retrain #3):**
- card_testing block-rate ≥ 20 % (currently 0 %)
- card_testing missed-rate ≤ 20 % (currently 35 %)
- velocity_spike block+review ≥ 95 % (currently 100 % via review — keep)
- high_value_regular false-block ≤ 10 % (currently 22.9 %)
- senior_routine false-block ≤ 4 % (currently 8.84 %)
- late_night_hostel review-rate ≤ 30 % (currently 60.5 %)
- Aggregate decisive accuracy on V3 ≥ 92 % (currently 92.13 %)

**Backend level:**
- All three augmenter rules fire at least 1000 times on V3 3M eval
  (currently R1=0, R2=324K, R3=0)
- No hardcoded feature values remaining in `_build_sparkov_row` except
  where documented
- Threshold constants moved to `Settings`

**Frontend level:**
- Analytics page shows rule-hit breakdown per typology
- Transaction detail page shows rule attribution alongside SHAP waterfall

**Ops level:**
- SLO definitions written to `docs/OPERATIONS.md`
- `heuristic_typology` field persisted for every prediction
- Warmup covers the full inference path including augmenter

---

## 8. What to NOT do this iteration

- **Stage 2 GraphSAGE + Fusion.** Ambitious, ~2 weeks. Deadline-risky.
  Ship Stage 1 fixes first; leave GraphSAGE for post-internship as
  continued research.
- **Alembic migration setup.** Auto-migration works; Alembic is polish,
  not correctness. Move to backlog.
- **Retraining IEEE-CIS Stage 1.** No new evidence it is broken.
  Focus resources on Sparkov (the deployed model).

---

*Document is the source of truth for iteration planning through
2026-07-30. Any change of priority or new finding should be appended
as an M-/T-/B-/F-/O- section below, not by editing existing findings.*
