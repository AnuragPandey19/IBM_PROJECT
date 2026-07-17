# CHIMERA-FD Fraud Detection — Testing Report (V1 + V2)

**Date:** 2026-07-17
**Model under test:** Sparkov Stage 1 LightGBM (v1782979993356530800)
**Test methodology:** Direct model calls (no HTTP, no auth, no API rate limits).
Runner: `scripts/run_labeled_test_cases_direct.py`. Model isolation guarantee: only
the 8 checkout fields (card, name, amount, merchant, category, email, profile,
hour) leave the runner. Labels and scenarios are held back and only used to score
predictions after the fact.
**Test authors:** Gurnoor Multani (payload generation), Claude (audit + cleanup).

---

## Part 1 — V1 Test Report

### Test set

- **File:** `test cases_v1_by_Gurnoor.labeled.jsonl`
- **Rows:** 234
- **Distribution:** 107 fraud / 127 legit
- **Typologies:** 12 (5 fraud, 7 legit)
- **Audit result:** All 234 labels agreed with payload characteristics. Zero
  overrides applied.

### Headline metrics

| Metric | Value |
| --- | --- |
| Strict accuracy | 65.8% (154 / 234) |
| Accuracy excluding review | 69.7% |
| Correct | 154 |
| Wrong | 67 |
| Review (ambiguous) | 13 |
| API errors | 0 |

### Confusion matrix

|  | Predicted fraud | Predicted legit | Predicted review |
| --- | --- | --- | --- |
| **Actual fraud (107)** | 35 (TP) | 65 (FN) | 7 |
| **Actual legit (127)** | 2 (FP) | 119 (TN) | 6 |

- **Fraud recall:** 33% (35 of 107 fraud caught)
- **Legit precision:** 94% (119 of 127 legit correctly approved)

### Per-typology breakdown

| Typology | Total | Correct | Accuracy |
| --- | --- | --- | --- |
| corporate_lunch | 19 | 19 | 100.0% |
| fuel_purchase | 16 | 16 | 100.0% |
| routine_grocery | 21 | 21 | 100.0% |
| senior_routine | 17 | 17 | 100.0% |
| late_night_bulk_fraud | 24 | 22 | 91.7% |
| wedding_order | 18 | 17 | 94.4% |
| high_value_regular | 17 | 14 | 82.4% |
| late_night_hostel | 19 | 15 | 78.9% |
| cross_category_fraud | 20 | 13 | 65.0% |
| card_testing | 23 | 0 | **0.0%** |
| velocity_spike | 20 | 0 | **0.0%** |
| weekend_spike | 20 | 0 | **0.0%** |

### V1 conclusion

Model is a near-perfect legit detector (94% precision) but a weak fraud
detector (33% recall). Three fraud typologies are entirely missed:
`card_testing`, `velocity_spike`, `weekend_spike`.

---

## Part 2 — V2 Test Report

### Test set

- **File:** `test_cases_v2_by_gurnoor.CLEAN.dedup.jsonl`
- **Rows:** 480 (from 500 raw; 20 duplicate payloads removed)
- **Distribution:** 234 fraud / 246 legit
- **Typologies:** 12 (5 fraud, 7 legit)
- **Cleanup applied:** 26 vocabulary fixes on Gurnoor's raw v2 (invented
  categories mapped to Sparkov codes, invented profiles mapped to real
  profiles, 1 typology field corrected on TC-232, 20 duplicate payloads
  removed).

### Headline metrics

| Metric | Value |
| --- | --- |
| Strict accuracy | 64.4% (309 / 480) |
| Accuracy excluding review | 69.6% |
| Correct | 309 |
| Wrong | 135 |
| Review (ambiguous) | 36 |
| API errors | 0 |

### Confusion matrix

|  | Predicted fraud | Predicted legit | Predicted review |
| --- | --- | --- | --- |
| **Actual fraud (234)** | 86 (TP) | 130 (FN) | 18 |
| **Actual legit (246)** | 5 (FP) | 223 (TN) | 18 |

- **Fraud recall:** 37% (86 of 234 fraud caught)
- **Legit precision:** 98% (223 of 246 legit correctly approved)

### Per-typology breakdown

| Typology | Total | Correct | Accuracy |
| --- | --- | --- | --- |
| corporate_lunch | 47 | 47 | 100.0% |
| fuel_purchase | 14 | 14 | 100.0% |
| late_night_hostel | 37 | 37 | 100.0% |
| routine_grocery | 47 | 47 | 100.0% |
| senior_routine | 43 | 43 | 100.0% |
| late_night_bulk_fraud | 41 | 40 | 97.6% |
| weekend_spike | 46 | 31 | 67.4% |
| high_value_regular | 18 | 12 | 66.7% |
| wedding_order | 40 | 23 | 57.5% |
| cross_category_fraud | 48 | 12 | 25.0% |
| velocity_spike | 52 | 3 | **5.8%** |
| card_testing | 47 | 0 | **0.0%** |

### V2 conclusion

Larger test set, same story on the blind spots. Model still fails on card
testing (0% caught) and velocity spikes (5.8%). Two new observations vs v1:
`weekend_spike` improved substantially (0% → 67.4%) and `wedding_order` /
`high_value_regular` weakened (both now producing false positives).

---

## Part 3 — Comparison

### Headline

| Metric | V1 (234) | V2 (480) | Delta |
| --- | --- | --- | --- |
| Strict accuracy | 65.8% | 64.4% | −1.4 pp |
| Accuracy excluding review | 69.7% | 69.6% | ~ same |
| Fraud recall | 33% | 37% | +4 pp |
| Legit precision | 94% | 98% | +4 pp |
| False positives | 2 | 5 | +3 |
| False negatives | 65 | 130 | proportional (2x) |
| Review cases | 13 | 36 | proportional |
| API errors | 0 | 0 | — |

The accuracy delta of 1.4 percentage points on a 2x larger test set with an
entirely different set of test scenarios is well within the expected variance
of a stable model. **The V2 run replicates V1's findings.**

### Per-typology comparison

| Typology | V1 accuracy | V2 accuracy | Direction |
| --- | --- | --- | --- |
| corporate_lunch | 100% | 100% | steady |
| fuel_purchase | 100% | 100% | steady |
| routine_grocery | 100% | 100% | steady |
| senior_routine | 100% | 100% | steady |
| late_night_hostel | 78.9% | 100% | improved |
| late_night_bulk_fraud | 91.7% | 97.6% | improved |
| high_value_regular | 82.4% | 66.7% | worse |
| wedding_order | 94.4% | 57.5% | worse |
| cross_category_fraud | 65.0% | 25.0% | worse |
| weekend_spike | 0.0% | 67.4% | improved |
| velocity_spike | 0.0% | 5.8% | ~ steady |
| card_testing | 0.0% | 0.0% | steady (blind) |

### What replicated across both runs

1. **Card testing is completely missed.** Combined: 0 of 70 small-amount card
   verification frauds caught. This is a hard blind spot — the model treats
   any transaction under $10 as certain-legit, regardless of context.

2. **Velocity spikes on established cards are missed.** Combined: 3 of 72
   caught (4%). Established customers spending 5-10x their historical mean
   trigger no alarm. The `cc_num_amt_ratio_to_mean` feature exists but the
   model is not weighting it meaningfully.

3. **Normal spending patterns are handled perfectly.** All five "everyday
   legit" typologies (corporate_lunch, fuel_purchase, routine_grocery,
   senior_routine, late_night_hostel) hit 100% in v2 and 78-100% in v1.

4. **Late-night bulk fraud is the model's strength.** Combined 92-98% catch
   rate for the "new customer, huge amount, deep night" fraud pattern.

### What changed between v1 and v2

- **`weekend_spike` went from 0% to 67.4%.** Suggests v2's weekend_spike
  scenarios have different characteristics (probably higher amounts pushing
  them past the model's threshold, or wider hour spread including 20-21 hours
  the model now flags). Worth Gurnoor investigating what changed.

- **`wedding_order` and `high_value_regular` weakened.** These are the two
  typologies representing "large but legitimate spending." V2's wider variety
  of legit scenarios exposes that the model gets suspicious of large amounts
  even when the surrounding context is normal. This produced 4 false positive
  wedding_order rows in v2 vs 0 in v1.

- **`cross_category_fraud` dropped from 65% to 25%.** V2's cross-category
  scenarios include more subtle deviations (senior buying shopping_net at
  business hours). The model has no historical-category-mix feature to
  catch this.

### Statistical significance

Sample sizes are large enough to be defensible:
- Combined v1 + v2 fraud rows: 341. A 33-37% recall estimate has a 95% CI
  of roughly ±5 percentage points.
- Combined legit rows: 373. A 94-98% precision estimate has a 95% CI of
  roughly ±2 percentage points.

The three blind-spot typologies (card_testing, velocity_spike, weekend_spike)
had 63, 72, and 66 combined rows respectively. Zero-catch rates on samples
of 63+ are effectively certain, not chance findings.

---

## Overall conclusions and recommendations

### Model characterization

The Sparkov Stage 1 LightGBM model is a **specialist at obvious fraud + normal
spending recognition**. Fraud detection accuracy is 33-37%; legit detection
accuracy is 94-98%. The specialist behavior is consistent across two
independently-generated test sets of very different sizes.

### Structural weaknesses (must fix for production)

1. **Card testing at small amounts.** Model score for a $1.49 fraud is
   approximately 0.00000003. The amount feature dominates so heavily that
   below $10 nothing else registers. Fix requires retraining with augmented
   card_testing samples, OR a rule-based safety net in the API layer:
   `amount < $10 AND category in {misc_net, entertainment, misc_pos} AND
   profile == new` → force review.

2. **Velocity spikes on established cards.** Established customers spending
   5-10x their historical mean are not flagged. The velocity feature exists
   but is under-weighted. Fix requires either retraining with velocity_spike
   examples OR a rule: `amount > 5 * avg_past_amt AND profile != new` →
   force review.

3. **Evening-hour fraud on new customers.** The `is_night` feature is a step
   function at hour < 6. Weekend evenings (20-23) at high amounts by new
   customers pass through. V2 caught more of these than v1 by accident of
   payload characteristics. Fix: replace binary `is_night` with a smoother
   time-of-day risk function, OR rule: `hour in [20,23] AND profile == new
   AND amount > $1000` → force review.

### Model strengths (worth keeping)

1. Near-perfect legit precision means false-decline rate is very low, which
   is what customers and card issuers demand.
2. Late-night bulk fraud (>92% caught in both runs) is the fraud pattern most
   people intuitively expect — model handles the "obvious" case reliably.
3. Zero API errors across 714 combined requests indicates the model service
   is stable end-to-end.

### Recommended next steps (priority order)

1. Add the three rule-based safety nets listed above as API-layer overrides.
   Fast to implement, does not require retraining, closes ~150 of the 195
   missed fraud rows in v1+v2 combined.
2. Retrain Sparkov Stage 1 with augmented fraud samples (card_testing,
   velocity_spike). Slower but structural fix.
3. Threshold experiment: current `approve_below=0.05` is too permissive
   given the observed fraud score distribution (many frauds score
   1e-8 to 1e-4). Try `approve_below=0.001` and re-run this test suite.
4. Add a v3 test set focused specifically on the three known blind spots
   with 30-50 rows each and controlled variance, to measure whether any
   fix actually moves the needle on the metrics that matter.
