# CHIMERA-FD Model Audit — Post V1/V2/V3 Testing

**Date:** 2026-07-17
**Scope:** Model prediction problems, training script problems, backend
model-pipeline code. Frontend touched only when a schema change is required.
**Out of scope:** general frontend UI, backend auth/security/CI/logging (all
already handled in V3 audit + Rounds 4-7).
**Evidence base:** V1 (234 rows, Gurnoor), V2 (480 rows dedup, Gurnoor), V3
(150,000 rows, Pankaj). Combined N = 150,714.

## ID scheme

- **M-x** — model characterization / prediction problems (visible at inference)
- **T-x** — training script / training data problems (root cause upstream)
- **B-x** — backend prediction-pipeline problems (feature builder, threshold,
  safety net, model service)
- **F-x** — frontend problems (only if schema change forces UI update)

Priority: **P0** (ship blocker), **P1** (next iteration), **P2** (nice to have).

---

## Model problems (M-x)

### M-1 — Card-testing pattern is completely blind (P0)

- **Evidence:** V1 0/23 caught. V2 0/47 caught. V3 0/11,715 caught.
  Combined 0 / 11,785. Not sampling variance.
- **Model behavior:** for a $1.49 misc_net fraud, calibrated score is
  `3.1 × 10⁻⁸`. Model is fully confident the transaction is legit.
- **Root cause:** `amount` feature dominance. In V3, 8,215 of 11,715
  card_testing cases went to REVIEW rather than APPROVE — model has some
  uncertainty, it just never crosses `block_above = 0.05`.
- **Interpretation:** the safety net's `_SPARKOV_SMALL_AMOUNT_MAX_BLOCK_USD
  = 12.0` only prevents small-amount BLOCK from happening
  (`api/services/model_service.py:236`). It does NOT force small-amount
  suspicious transactions FROM approve INTO review. Missing rule direction.

### M-2 — Velocity spike on established cards is near-blind (P0)

- **Evidence:** V1 0/20. V2 3/52. V3 633/12,586 (5.0%). Combined 636/12,678.
- **Model behavior:** established customer normally spends ~$55 (per demo
  profile). A $5,000 transaction has `cc_num_amt_ratio_to_mean ≈ 90`.
  Model does not flag it.
- **Root cause 1:** the ratio feature exists but is under-weighted by the
  trained LightGBM. Feature importance ranking is dominated by `amt`,
  `log1p_amt`, `hour`, `category` target encoding, and other bulk features.
- **Root cause 2:** Sparkov training data has velocity_spike frauds
  massively under-represented. The trained model has not seen enough
  examples of "established customer + large single transaction = fraud".

### M-3 — Cross-category deviation weak (P1)

- **Evidence:** V1 65% (sampling noise). V2 25% (sampling noise). V3 37.8%
  on 12,672 rows (statistically firm).
- **Root cause:** there is no per-customer historical category-mix feature.
  A senior customer buying online electronics is indistinguishable from a
  senior customer buying groceries — the model sees only the current
  transaction's category, not what THIS customer usually buys.

### M-4 — Late-night hostel over-flagged (P1)

- **Evidence:** V1 78.9% approved as legit. V2 100%. V3 38.7% on 11,741.
  V3 exposes it because Gurnoor's V1/V2 samples were narrower; Pankaj's
  larger sample stretches into more amount/merchant variety that the model
  gets suspicious of.
- **Root cause:** `is_night = int(hour < 6)` in
  `src/chimera_fd/features/sparkov_engineering.py:49` is a hard binary step
  function. Combined with `is_weekend` and `amt` bucket, model over-triggers
  on legitimate low-amount late-night grocery activity. This produces
  FALSE POSITIVES — worse for customers than false negatives.

### M-5 — Score distribution too narrow to threshold-tune (P1)

- **Evidence:** missed frauds score `1e-8` to `1e-4`. Approved legit
  score `1e-4` to `1e-3`. There is no clean separation to move
  `approve_below` toward.
- **Model behavior:** `_SPARKOV_APPROVE_BELOW = 0.010` and
  `_SPARKOV_BLOCK_ABOVE = 0.05` at
  `api/services/model_service.py:227-228`. The 4-order-of-magnitude gap
  between typical fraud scores (1e-8) and the approve threshold (1e-2)
  means threshold tuning alone can't fix recall. The distribution needs
  to be spread out via retraining.

---

## Training-script problems (T-x)

### T-1 — Sparkov training data does not include card-testing patterns (P0)

- **Evidence for gap:** Sparkov generator produces transactions from a
  simulated population. Card-testing (dozens of $1-$5 charges by a
  fraudster on a stolen card within minutes) is a real-world fraud pattern
  not modelled by the Sparkov simulator. Training data therefore never
  contains a labeled example of "small amount → fraud".
- **Impact:** trained model learns `amount` as an almost purely
  monotonically-increasing risk feature. Below ~$50, fraud probability is
  effectively zero.
- **Fix:** augment the training set with synthetic card-testing samples
  before running `train_sparkov.py`. Suggested minimum: 2-5% of training
  set. Amount distribution $0.50 to $10, weighted toward $1-$3.
- **Where to add:** new file `scripts/augment_sparkov_card_testing.py`
  producing rows that get merged into `data/processed/sparkov/train.parquet`
  before `train_sparkov.py` picks it up.

### T-2 — Velocity-spike samples under-represented (P0)

- **Evidence:** V3 5% recall on 12K samples, on a feature (`amt_ratio_to_mean`)
  that mathematically works. The problem is the model was never trained on
  enough examples where ratio > 5 AND label = fraud.
- **Fix:** augment the training set with synthetic velocity-spike fraud
  rows — established `cc_num` with 100+ prior transactions, then a single
  transaction at 5-15× the historical mean. Suggested count: 3-5% of
  training set. Distribute ratios across `[3, 5, 8, 12, 20]`.
- **Where to add:** same augmentation script as T-1, add a
  `--typology velocity_spike` mode.

### T-3 — Class weight is aggressive but not typology-aware (P1)

- **Evidence:** `stage1_lightgbm.py:79-80` sets `scale_pos_weight = n_neg /
  n_pos ≈ 400` for Sparkov. This global up-weight helps overall recall but
  cannot distinguish "important fraud" (card_testing, velocity_spike) from
  "obvious fraud" (late-night bulk) — treats them equally.
- **Fix:** consider sample-level weights that further boost the augmented
  card_testing + velocity_spike rows during training, so the model puts
  extra loss weight on the patterns we know it misses. Not a large change —
  pass `sample_weight` to LightGBM's `Dataset` constructor.

### T-4 — Training uses `metric="average_precision"` (PR-AUC) but validates
without stress-testing on the three failure patterns (P1)

- **Evidence:** `stage1_lightgbm.py:34` — metric is PR-AUC. Early stopping
  fires when val PR-AUC stops improving. But PR-AUC is an aggregate; the
  model can plateau at 0.5 PR-AUC while still having 0% recall on
  card_testing. Training has no per-typology validation.
- **Fix:** compute per-typology PR-AUC on a held-out validation slice
  drawn from Pankaj-style scenarios (or a synthetic equivalent) at the
  end of training, and log it. Doesn't need to gate early stopping; it
  needs to make the model's blind spots visible in `stage1_evaluation.json`.
- **Where:** modify `scripts/train_sparkov.py` around line 130 to add a
  per-typology evaluation block after `evaluate(y_test, test_score)`.

### T-5 — Feature engineering is not typology-aware (P2)

- **Evidence:** `sparkov_engineering.py` adds temporal, amount, geographic,
  velocity, encoding features. Zero features capture historical-category
  mix or a smooth time-of-day risk.
- **Fix:** two new features to add before retraining:
  - `cust_category_diversity_before` — number of distinct categories THIS
    `cc_num` has transacted in prior to now. Card-testing bursts touch few
    categories; established customers touch many.
  - `hour_risk_smooth` — replace the binary `is_night` with a smoothed
    per-hour risk score computed on training data (e.g. proportion of
    fraud in each hour, EMA-smoothed to avoid overfitting).
- **Where:** `add_sparkov_temporal` and a new `add_sparkov_customer_profile`
  function in `sparkov_engineering.py`.

### T-6 — No holdout for the twelve typologies (P1)

- **Evidence:** train/val/test is a time-based split at 80/10/10. The test
  set is a random slice of Sparkov, not a coverage of the twelve typologies
  used in V1/V2/V3 testing. So `stage1_evaluation.json` reports 0.50 PR-AUC
  and everyone thinks the model works, but the twelve-typology testing
  reveals 3 blind spots.
- **Fix:** hold out a "typology stress" set of 1,000 synthetic rows per
  typology (12,000 total) generated by the same script used to build V1/V2,
  and never train on them. Include per-typology PR-AUC + recall in
  `stage1_evaluation.json`.

---

## Backend model-pipeline problems (B-x)

### B-1 — Safety net only rescues from BLOCK, never from APPROVE (P0)

- **Location:** `api/services/model_service.py:317-330`,
  `_decide_sparkov(prob, amt)`. Current logic:
  ```
  if amt <= 12 and prob > 0.05:  return "review"   # BLOCK → REVIEW
  if prob < 0.010:               return "approve"
  if prob > 0.05:                return "block"
  return "review"
  ```
- **Problem:** the rescue only triggers when the model already wanted to
  block. For card_testing at $1.49 with score `3e-8`, the model wants to
  APPROVE. Safety net doesn't fire. Card testing keeps passing through.
- **Fix:** add rules that push suspicious APPROVE decisions into REVIEW.
  Best home for this is a NEW module `api/services/decision_augmenter.py`
  (see B-2 for module design).
- **Rule 1 (card_testing):**
  ```
  if profile == "new" AND amount < 10 AND category in
     {misc_net, entertainment, misc_pos, personal_care}:
      decision = "review" (was "approve")
  ```
- **Rule 2 (velocity_spike):**
  ```
  if profile in {"established", "high_spender", "senior"}
     AND amount > 5 * profile.avg_past_amt
     AND decision == "approve":
      decision = "review"
  ```
- **Rule 3 (evening new-customer high-amount):**
  ```
  if profile == "new" AND hour in [20, 21, 22, 23]
     AND amount > 1000 AND decision == "approve":
      decision = "review"
  ```

### B-2 — Decision augmenter must be a shared module, not inline in `_decide_sparkov` (P0)

- **Problem:** if rules go into `_decide_sparkov` inside `model_service.py`,
  they run for API traffic (`/api/checkout`, `/api/predict/sparkov`) but
  NOT for `scripts/run_labeled_test_cases_direct.py` unless the script
  explicitly opts in via `--include-safety-net`. This creates a three-way
  drift risk: local API says X, direct script says Y, deployed says Z.
- **Fix:** create `api/services/decision_augmenter.py`:
  ```python
  def apply_safety_nets(
      payload: dict,          # 8 checkout fields
      profile: dict,          # resolved CUSTOMER_PROFILES entry
      raw_decision: str,      # "approve" | "review" | "block"
      cal_score: float,
      enabled: dict[str, bool] | None = None,
  ) -> tuple[str, list[str]]:
      """Returns (final_decision, list_of_triggered_rule_ids)."""
  ```
- **All three call sites use this same function:**
  1. `api/routes/checkout.py` after `ms.score_sparkov(X)` and before
     `Transaction` insert.
  2. `api/routes/predict_sparkov.py` after `ms.score_sparkov(X)`.
  3. `scripts/run_labeled_test_cases_direct.py` in `score_one()` after
     `ms.score_sparkov(X)` when `--include-safety-net` is passed (default
     ON for realistic measurement, OFF for measuring raw model quality).
- **Feature flags per rule:** each rule reads from `Settings` (env var):
  ```python
  enable_safety_net_card_testing: bool = True
  enable_safety_net_velocity_spike: bool = True
  enable_safety_net_night_new_high: bool = True
  ```
  Ops can disable a misbehaving rule via env var + factory rebuild without
  a code change.

### B-3 — `demo_profile` fixed-history at inference means velocity_spike is not observable for `new` (P1)

- **Location:** `api/routes/checkout.py:96-114` (CUSTOMER_PROFILES) +
  `api/routes/checkout.py:258-260` (`_build_sparkov_row`).
- **Problem:** for `demo_profile = "new"`, `avg_past_amt = 0.0` and
  `prior_transaction_count = 0`. `amt_ratio` code falls back to `1.0`.
  Model can NEVER see a velocity ratio for new customers — the feature is
  literally always the same value.
- **Impact:** velocity_spike rule cannot fire for `new` profile. That's OK
  because velocity_spike is definitionally about established customers.
  But the model is also using this feature as a proxy for other patterns
  — the constant `1.0` for new customers is a training/inference
  distribution mismatch.
- **Fix:** at demo/inference time, replace the constant `1.0` with a
  reasonable prior estimate (e.g., `amount / typical_new_customer_first_amount`)
  OR document this explicitly and stop pretending the ratio feature is
  active for new customers.

### B-4 — `cc_num` is one of exactly 4 values in demo mode (P2)

- **Location:** `checkout.py:279` — `cc_num = int(profile["card_number_full"][:12])`.
  There are 4 demo profiles → 4 unique `cc_num` values ever seen at
  demo-inference time.
- **Impact:** any feature the model derived from `cc_num` diversity at
  training time is meaningless in demo. `cc_num` isn't in the top-15
  training features per `sparkov_feature_importance.csv`, so impact is
  low, but this is a train/inference distribution mismatch we should log.
- **Fix:** log a warning in `ModelService.warmup()` if fewer than N distinct
  `cc_num` values are expected. Alternatively, add "which demo profile was
  used" as an explicit categorical to `raw_features` so post-hoc analysis
  can separate demo synthetic traffic from real traffic.

### B-5 — No structured way to record "rule triggered" in the DB (P1)

- **Location:** `Prediction` table in `api/db/models.py`. Currently stores
  `raw_score`, `calibrated_score`, `decision`, `model_version`, `shap_top`,
  `latency_ms`. Nothing captures "the model wanted APPROVE but the
  card_testing safety net pushed it to REVIEW."
- **Impact:** analytics dashboard cannot show "how often did each safety
  net fire". Impossible to tune rules without this data.
- **Fix:** add a nullable column `Prediction.rules_triggered: JSON` (list
  of rule IDs). Populate from the augmenter's return value. Alembic
  migration required (or SQLite dev-mode auto-add). See F-1 for the
  frontend implication.

### B-6 — `stage1_evaluation.json` does not include Sparkov typology breakdown (P1)

- **Location:** `scripts/train_sparkov.py:140-152` writes the eval JSON.
  Only global PR-AUC / ROC-AUC / test metrics.
- **Fix:** after training, run the twelve-typology stress set (see T-6)
  and write per-typology PR-AUC + recall into `sparkov_evaluation.json`.
  Every retrain produces a comparable baseline number so we can quantify
  whether an intervention worked.

---

## Frontend problems requiring schema change (F-x)

### F-1 — Transactions dashboard needs a "rule triggered" column (P1)

- **Depends on:** B-5 (DB column added).
- **Change:** `frontend/src/app/transactions/page.tsx` — add a compact
  column showing rule IDs that fired for this prediction (e.g., a red
  badge "card_testing"). Existing column layout has room.
- **API:** `TransactionSummary` schema in `api/schemas/transactions.py`
  needs to expose `rules_triggered` in the response.
- **Impact:** analyst can quickly see which decisions were augmenter-driven
  vs pure model. Otherwise no way to tell.

### F-2 — Optional: SHAP waterfall footnote for augmented decisions (P2)

- **Depends on:** B-5.
- **Change:** when `rules_triggered` is non-empty, add a small note above
  the SHAP waterfall: "This decision was augmented by rule X. Model's
  raw preference was Y." Preserves explainability transparency.

---

## Recommended execution order

**Week 1 — foundation (retraining not required)**

1. **B-2 first:** build `decision_augmenter.py` skeleton with feature
   flags, wire into checkout + predict_sparkov + direct-runner. No rules
   inside yet — just plumbing.
2. **Unit tests + integration tests + CI green.** Multi-tenancy tests
   must still pass.
3. **B-1 Rule 1 (card_testing):** add to augmenter. Expected V3 impact:
   card_testing recall 0% → ~70% (8,215 previously-review rows now blocks,
   plus safety-net targets pull in the remaining 3,500 approve rows).
4. **B-1 Rule 2 (velocity_spike):** add. Expected V3 impact: velocity_spike
   recall 5% → ~50%.
5. **B-1 Rule 3 (night + new + high):** add. Expected V3 impact:
   weekend_spike + late_night_bulk_fraud lift 5-15 points.
6. **Regression test:** re-run direct model on Pankaj 150K with rules ON
   vs OFF. Publish delta.
7. **Ship. Smoke-test HF Space.**

**Week 2 — data + retraining**

8. **T-1 + T-2 augmentation script.** Generate 3-5% synthetic
   card_testing + velocity_spike rows. Merge into training input.
9. **T-6 typology holdout:** 12,000-row stress set (1,000 per typology)
   never seen by model.
10. **Retrain Sparkov.** Compare per-typology recall vs pre-augmentation
    baseline stored in `sparkov_evaluation.json`.
11. **Regression test:** direct model on Pankaj 150K.
12. **If retrained model beats rules-only version → consider disabling
    rules to reduce complexity. If both add value → keep both.**

**Week 3 — structural improvements**

13. **T-5:** add `cust_category_diversity_before` + `hour_risk_smooth`.
14. **T-3:** sample weights for augmented rows.
15. **T-4:** per-typology validation output in training script.
16. **Second retrain.** Compare.

**Week 4 — observability + threshold**

17. **B-5:** add `rules_triggered` column to Prediction table + Alembic
    migration + populate from augmenter.
18. **F-1:** dashboard column for `rules_triggered`.
19. **B-3:** fix or document the `new`-profile velocity feature constant.
20. **M-5:** re-run threshold experiment now that score distribution has
    spread. Try `approve_below = 0.001`.

---

## Testing plan (all fixes go through this)

For every fix (M-x, T-x, B-x, F-x):

1. **Unit test.** `tests/test_decision_augmenter.py` — every rule has +ve
   case (fires when it should) and −ve case (does not fire when it
   should not). Rule flags default-on and default-off tested.
2. **Integration test.** `tests/test_multi_tenancy.py` must still pass.
   Add `tests/test_checkout_safety_nets.py` — POST to `/api/checkout`
   with a fraud payload, assert response status matches expected rule
   trigger.
3. **Regression test.** Run
   `scripts/run_labeled_test_cases_direct.py --include-safety-net --input pankaj.jsonl`
   before and after each change; diff the summary JSONs. Both direct and
   API paths must show the same numbers.
4. **Smoke test on HF Space.** After push, `curl -X POST
   https://undebuggedbit-chimera-fd.hf.space/api/checkout -d '{...}'`
   for 5 hand-crafted payloads (card_testing $1.49, velocity_spike
   $5000-on-established, normal $50 grocery, wedding $3000-high_spender,
   and one edge case). Verify decisions match direct-model output.

Every fix that touches all three environments (local API, direct model,
deployed) must pass all four layers. Any layer failure ⇒ do not ship.

---

## Success criteria (how we know we're done)

For **safety nets alone** (week 1 target):

- V3 card_testing recall ≥ 65% (from 0%).
- V3 velocity_spike recall ≥ 40% (from 5%).
- V3 legit precision on non-review predictions ≥ 96% (must not regress).
- V3 review rate ≤ 20% (must not explode).
- Zero engine errors.

For **retrained model** (week 3 target):

- V3 card_testing recall ≥ 60% even with safety nets OFF (model alone).
- V3 velocity_spike recall ≥ 50% with safety nets OFF.
- V3 overall accuracy ≥ 70% (from 64.7%).
- No regression on legit typologies (all five 100%-approved typologies
  must remain 100%).
- Cold-start latency does not increase.

For **observability + dashboard** (week 4 target):

- Every prediction has `rules_triggered` populated (empty list if none).
- Dashboard displays rules column.
- Analytics summary shows per-rule fire counts.
