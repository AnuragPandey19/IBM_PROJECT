# EDA + Baseline + Calibration Notes — CHIMERA-FD

Real numbers from full-data runs. Use these in the report and viva.

---

## Dataset Facts (from `python scripts/prepare_data.py`)

- **Total rows (IEEE-CIS train_transaction):** 590,540
- **Total columns raw:** 394 (transaction) + 41 (identity) = 434 merged
- **Identity match rate:** 24.4% (144,233 of 590,540 rows have identity data)
- **Overall fraud rate:** 3.499%
- **Split sizes (time-based 80/10/10):**
  - Train: 472,432 rows, fraud rate 3.514%
  - Val:   59,054 rows,  fraud rate 3.134%
  - Test:  59,054 rows,  fraud rate 3.747%

**Temporal drift signature:** fraud rate rises from 3.13% (val, earlier) to 3.75% (test, later). This is exactly why we never random-split time-series fraud data.

---

## Feature Engineering (from `python scripts/build_features.py`)

- **Original features:** 434
- **Engineered features added:** ~27
- **Total feature columns after engineering:** 461
- **Usable model inputs:** 456

**Engineered feature categories:**
- Temporal: `hour, day_of_week, is_weekend, is_night, days_since_start`
- Amount: `log1p_amount, amount_cents, is_round_amount, amount_bucket`
- Velocity (per card1): `txn_count_before, amt_sum_before, amt_mean_before, seconds_since_prev, amt_ratio_to_mean`
- Missingness: `has_identity_info, missing_DeviceInfo, missing_DeviceType, missing_P_emaildomain, missing_R_emaildomain`
- Encoding: 28 label-encoded categoricals + 8 target-encoded high-cardinality columns

**scale_pos_weight for LightGBM = 27.46** (= 455,833 / 16,599 on train)

---

## Stage 1 Baseline (from `python scripts/train_stage1.py`)

**Full 472,432-row training, 3.5 min compute, LightGBM with 2000 boost rounds.**

| Metric | VAL | TEST |
|---|---|---|
| **PR-AUC (primary)** | **0.5630** | **0.5100** |
| **ROC-AUC** | 0.9009 | 0.8715 |
| **Precision @ 50% Recall** | 0.6462 | 0.4966 |
| **Precision @ 80% Recall** | 0.1460 | 0.1174 |
| **Recall @ 1% FPR** | 0.5127 | 0.4243 |
| **Recall @ 5% FPR** | 0.6996 | 0.6123 |
| **F1 @ chosen threshold** | 0.5670 | 0.5041 |
| **Precision @ chosen threshold** | 0.6853 | 0.6469 |
| **Recall @ chosen threshold** | 0.4835 | 0.4130 |
| **Brier Score (uncalibrated)** | 0.0289 | 0.0490 |
| **ECE (uncalibrated)** | 0.0265 | 0.0474 |
| Chosen threshold | 0.403 (from val argmax-F1) | (same) |
| Best iteration | 1,979 / 2,000 | — |
| Training time | ~210 seconds | — |

**Confusion Matrix on TEST (threshold=0.403):**
- TP = 914  (frauds caught)
- FP = 499  (false alarms)
- TN = 56,342  (legit correctly cleared)
- FN = 1,299  (frauds missed)

---

## Top 10 Features by SHAP (from `python scripts/generate_shap.py`)

| Rank | Feature | Mean \|SHAP\| | Type |
|---|---|---|---|
| 1 | `card1_target_enc` | 1.551 | ⭐ Target-encoded |
| 2 | `C13` | 0.406 | Vesta counting |
| 3 | `C1` | 0.406 | Vesta counting |
| 4 | `card1_amt_mean_before` | 0.323 | ⭐ Engineered velocity |
| 5 | `TransactionAmt` | 0.308 | Raw amount |
| 6 | `card1_amt_sum_before` | 0.307 | ⭐ Engineered velocity |
| 7 | `addr1_target_enc` | 0.274 | ⭐ Target-encoded |
| 8 | `R_emaildomain_target_enc` | 0.241 | ⭐ Target-encoded |
| 9 | `DeviceInfo_target_enc` | 0.239 | ⭐ Target-encoded |
| 10 | `C6` | 0.216 | Vesta counting |

**Story: 6 of top 10 SHAP-important features are ones we engineered.**

Also in top 15: `card1_txn_count_before` and `card1_amt_ratio_to_mean` — both velocity.

---

## Local SHAP Sample Cases

- Top-5 highest-scored transactions: **all actual frauds** (P(fraud) ~ 1.0)
- Top-5 lowest-scored transactions: **all actual legit** (P(fraud) ~ 0.0)
- `card1_target_enc` dominates each explanation (positive when fraud, negative when legit)

---

## Stage 3 Calibration Results (from `python scripts/calibrate.py`)

**Isotonic regression fitted on 59,054 val samples.**

| Metric | Before | After | Relative Change |
|---|---|---|---|
| VAL ECE | 0.0265 | 0.0000 | **-100%** |
| **TEST ECE** | **0.0474** | **0.0093** | **-80.3%** ⭐ |
| VAL Brier | 0.0289 | 0.0238 | -17.6% |
| **TEST Brier** | **0.0490** | **0.0307** | **-37.4%** |

**Target from SWOT:** TEST ECE < 0.04. **Achieved: 0.0093.** Target crushed by 4x.

Reliability diagrams in `reports/calibration/reliability_before_test.png` and `_after_test.png`.

---

## Files Generated (so far)

**Data:**
- `data/processed/ieee_cis/train.parquet` (64 MB)
- `data/processed/ieee_cis/val.parquet` (8.3 MB)
- `data/processed/ieee_cis/test.parquet` (9.1 MB)
- `data/processed/ieee_cis/train_features.parquet` (engineered)
- `data/processed/ieee_cis/val_features.parquet`
- `data/processed/ieee_cis/test_features.parquet`
- `data/processed/ieee_cis/feature_pipeline.pkl` (fitted encoders)
- `data/processed/ieee_cis/feature_columns.txt` (list of 456 features)

**Models:**
- `models/stage1_lightgbm.pkl` (6.9 MB — trained LightGBM)
- `models/stage3_isotonic.pkl` (1 KB — fitted calibrator)

**Reports:**
- `reports/stage1_evaluation.json`
- `reports/stage1_feature_importance.csv`
- `reports/shap/global_summary.csv`
- `reports/shap/global_summary_bar.png`
- `reports/shap/global_summary_beeswarm.png`
- `reports/shap/local_examples.md`
- `reports/shap/shap_values_val_sample.npy`
- `reports/shap/val_sample.parquet`
- `reports/calibration/reliability_before_val.png`
- `reports/calibration/reliability_before_test.png`
- `reports/calibration/reliability_after_val.png`
- `reports/calibration/reliability_after_test.png`
- `reports/calibration/summary.json`

---

## Viva Talking Points (Key Numbers to Memorize)

1. **Data:** 590,540 rows, 3.5% fraud, 434 columns.
2. **Split:** Time-based 80/10/10. Fraud rate drifts from 3.13% (val) to 3.75% (test) — real temporal drift.
3. **Features:** 434 raw → 456 usable. 27 engineered (temporal, amount, velocity, missingness, encoding).
4. **Stage 1:** Test PR-AUC = 0.51, ROC-AUC = 0.87, Recall @ 5% FPR = 0.61. Trained in 3.5 min on CPU.
5. **SHAP:** 6 of top 10 features are engineered. Top-5 flagged/cleared are 100% correct.
6. **Calibration:** Test ECE reduced by 80.3% (0.0474 → 0.0093). Target of 0.04 crushed 4x.
7. **No SMOTE:** class imbalance handled via scale_pos_weight = 27.46. SHAP backgrounds remain faithful.

---

## Next Steps

- [x] Setup, data prep, features, LightGBM baseline
- [x] SHAP explanations (Stage 4 XAI)
- [x] Isotonic Calibration (Stage 3)
- [ ] GraphSAGE Stage 2 (in progress — installing PyTorch GPU)
- [ ] Fusion Head
- [ ] Streamlit dashboard
- [ ] Sparkov cross-dataset test
- [ ] FastAPI service
- [ ] Docker deployment
