# CHIMERA-FD — Project Report Skeleton

**Status:** Draft outline for Anurag's approval before section-by-section drafting.
**Target:** ~35-45 pages, IBM internship deliverable.
**Style:** Semi-formal engineering + case-study narrative (first-person "I / we"
active voice, honest about what worked and what didn't).
**Deep-dive sections:** 4 (Model), 6 (Testing), 8 (Challenges).
**Brief sections:** 5 (Architecture — no deep frontend/backend code).

---

## Front matter (2-3 pages)

- **Cover page:** Title, author, IBM logo placeholder, submission date,
  supervisor
- **Acknowledgments:** Team + mentor + AI-assisted tooling disclosure
- **Table of contents:** Auto-generated
- **List of figures + tables**
- **Executive Summary (1 page):**
  Two paragraphs — problem + solution, headline numbers, key takeaways.
  Headline numbers: **92.13% decisive accuracy on 3M held-out rows, zero
  engine errors, 12-agent test generation methodology mentor-approved.**

---

## Section 1 — Introduction & Problem Statement (2-3 pages)

### 1.1 Motivation
- Card fraud globally: $33.5B in 2022, ~75% card-not-present
- Why rule engines alone don't work — the three failure modes
  (fraudsters adapt, no generalization, ignore context)
- Constraint stack: class imbalance kills accuracy metric, 200ms
  latency kills deep models, regulatory explainability (PSD2, GDPR
  Article 22, RBI, PCI-DSS) kills black-box models

### 1.2 Project Scope
- Sprint window: 23 June - 30 July 2026 (~5 weeks)
- IBM AI/ML internship deliverable
- Team of 4 (my role: full-stack + system architecture + retrain
  orchestration; teammates roles briefly)
- Live-deployed demo requirement

### 1.3 What I Set Out to Build
- Two-stage detection pipeline (LightGBM Stage 1 + Isotonic Stage 3)
- Live web application (Next.js + FastAPI)
- Multi-tenant B2B portal architecture
- Rigorous testing methodology

### 1.4 Report Structure
- One-paragraph guide to what each section covers

**Diagrams:** none.

**Hinglish tracker items:** origin story, dukaandar analogy for rule engines,
200ms latency, PR-AUC vs accuracy funda.

---

## Section 2 — Research Foundation (3-4 pages)

### 2.1 Corpus Overview
- 16 papers reviewed during first two weeks of the sprint
- Coverage: GNN approaches, XAI in fraud, cross-dataset generalization,
  calibration, cost-sensitive learning

### 2.2 The Five Load-Bearing Papers
Each with 1-paragraph description of what they contributed to CHIMERA-FD:

1. **Zafar & Wu (2026)** — Explainability-Imbalance Paradox
   → cost-sensitive loss over SMOTE (the anchor)
2. **Thivaios et al. (2025)** — ML/DL fraud survey
   → LightGBM Stage 1 justified
3. **Nie et al. (2025)** — Calibrated Risk Scoring
   → isotonic recalibration as first-class concern
4. **Cheng et al. (2024)** — GNN for Fraud Detection Review
   → Stage 2 GraphSAGE exploration + honest null on fusion
5. **Almalki & Masud (2025)** — XAI + Stacking Ensemble
   → three-axis evaluation stance

### 2.3 The Explainability-Imbalance Paradox (extended discussion)
- What SMOTE does to the training distribution
- Why SHAP explanations become invalid on SMOTE-trained models
- Our answer: `scale_pos_weight ≈ 400` — training distribution intact,
  SHAP stays faithful

### 2.4 Where We Diverge (from load-bearing papers)
- Brief 5-row table: paper vs our implementation vs why

**Diagrams:**
- Figure 2.1: **[IMAGE PROMPT]** — SMOTE vs cost-sensitive-loss illustration
  (two-panel comparison, distorted vs faithful SHAP magnifying glass)
- Figure 2.2: **[IMAGE PROMPT]** — 5 papers converging into 5 design pillars
  → CHIMERA-FD shield

**Hinglish tracker items:** Zafar-Wu paradox with mirror analogy, why SMOTE
banned, 5 hero papers simple summary.

---

## Section 3 — Dataset Choice & Analysis (3-4 pages)

### 3.1 The Four Candidate Datasets
Comparison table: IEEE-CIS vs Sparkov vs ULB Kaggle vs PaySim
(realism, feature interpretability, size, fraud rate, use).

### 3.2 Why IEEE-CIS as Research Baseline
- 590,540 real card-not-present transactions from Vesta
- 434 named features → meaningful SHAP
- Time-based 80/10/10 split — never random on time series

### 3.3 Why Sparkov for Live Demo
- ~3.4M simulated transactions
- Named merchant categories map cleanly to a checkout UI
- Sparkov training PR-AUC 0.827 val / 0.805 test
- Brier 0.0008, ECE 0.0006

### 3.4 Why ULB and PaySim Were Rejected
- ULB: PCA-anonymized V1-V28 features → SHAP meaningless
- PaySim: mobile-money transactions, wrong transaction type

### 3.5 A Limitation We Documented Honestly
- Sparkov's simulator doesn't generate card-testing patterns
  → measured empirically: cheapest fraudulent night transaction in
  1.48M training rows is $5.60
- We surface this in Section 8; here we just note it

**Diagrams:**
- Table 3.1: 4-dataset comparison
- Figure 3.1: **[GENERATED FROM DATA — I'll make this]** — dataset size
  vs fraud rate scatter, 4 datasets marked

**Hinglish tracker items:** IEEE-CIS vs Sparkov ka choice, ULB kyu reject.

---

## Section 4 — Model Design & Training (5-6 pages — DEEP DIVE)

### 4.1 Two-Stage Cascaded Design
- Stage 1 LightGBM: fast triage (< 5ms, handles 92% of traffic)
- Stage 3 Isotonic: recalibration
- Rationale for cascaded architecture — Stripe/Visa production-shaped

### 4.2 Stage 1 LightGBM Choice
- Why LightGBM over XGBoost:
  native categorical, lower memory, faster on wide tabular
- Hyperparameters, `scale_pos_weight ≈ 400`, PR-AUC as metric,
  early stopping on val plateau

### 4.3 Sparkov Feature Engineering (30 features from 8 checkout fields)
Full breakdown by group:
- Temporal (hour, dow, is_weekend, is_night, cyclical encoding)
- Amount (log1p, buckets, cents, round-amt flag)
- Geographic (state target-encoded, ZIP prefix, Haversine distance)
- Velocity (cc_num_amt_mean_before, ratio_to_mean, prior_txn_count)
- Categorical encoding (target encoding for high-card, native for low-card)
- Customer profile (demo_profile → prior_mean, prior_count)

**Note on a subtle limitation** (foreshadows Section 8):
- `cc_num_seconds_since_prev` is hardcoded per demo profile at inference
- Only 8 of the 30 features actually respond to the transaction —
  the other 22 are keyed on `demo_profile` or wall-clock

### 4.4 Stage 3 — Isotonic Recalibration
- Why calibration matters for threshold routing
- Isotonic vs Platt (flexible monotone vs fixed sigmoid)
- Result: **Brier 0.0008, Expected Calibration Error 0.0006**

### 4.5 Threshold Selection
- History: v1 (0.005/0.010), v2 (0.010/0.050), v3 post-augmentation
  (0.050/0.300)
- Chosen: approve < 0.05, block > 0.30, else review
- Rationale for the widened range post-augmentation

### 4.6 Training Results
Key numbers for Sparkov (from `sparkov_evaluation.json`):
- Val PR-AUC 0.827, Test PR-AUC 0.805
- Val ROC-AUC 0.984, Test ROC-AUC 0.986
- Training time: 680 s on 3.05 M rows
- Top-10 features by gain importance

### 4.7 Decision Augmenter (Post-Model Safety Nets)
- Design principle: rules only tighten approve → review
- Three rules: card_testing_small_amount, velocity_spike_established,
  evening_new_high_amount
- Shared module architecture — same code called from API, direct
  runner, test suite

**Diagrams:**
- Figure 4.1: **[IMAGE PROMPT]** — Two-stage cascaded pipeline flow
- Figure 4.2: **[GENERATED — feature importance bar chart from data]**
- Figure 4.3: **[GENERATED FROM ROC-AUC SCRIPT]** — ROC curve
- Figure 4.4: **[GENERATED FROM ROC-AUC SCRIPT]** — PR curve
- Figure 4.5: **[GENERATED FROM ROC-AUC SCRIPT]** — Calibration reliability
- Figure 4.6: **[GENERATED FROM ROC-AUC SCRIPT]** — Score distribution histogram
- Figure 4.7: **[IMAGE PROMPT]** — Feature engineering flow (8 checkout fields → 30)
- Figure 4.8: **[IMAGE PROMPT]** — Decision augmenter's three rules

**Hinglish tracker items:** LightGBM vs XGBoost, Isotonic simple mein,
scale_pos_weight, feature engineering, decision augmenter safety net,
velocity feature limitation.

---

## Section 5 — System Architecture (2-3 pages — BRIEF)

### 5.1 High-Level Overview
- End-to-end request flow (one figure worth 1000 words here)

### 5.2 Frontend
- Next.js 15 (App Router, React 19), TypeScript, Tailwind
- Static-exported, served from same Docker image
- Key views: checkout, transactions dashboard, analytics
- ~1 paragraph — no code

### 5.3 Backend
- FastAPI + Uvicorn (async)
- SQLAlchemy 2.0, Postgres (prod) / SQLite (dev)
- JWT auth (HS256, bcrypt cost 12)
- Rate limiting via slowapi
- ~2 paragraphs — no code

### 5.4 Multi-Tenancy (brief — 1 paragraph)
- Every row-owning table has company_id FK
- Router-level `require_company` dependency
- Cross-tenant fetch returns 404 (never 403 — no existence leak)
- Verified by `tests/test_multi_tenancy.py`

### 5.5 Deployment
- Hugging Face Spaces Docker SDK, port 7860
- Single multi-stage Dockerfile
- Postgres external (Render free tier)
- Auto-rebuild on `git push hf main`
- Live URL: `https://undebuggedbit-chimera-fd.hf.space`

**Diagrams:**
- Figure 5.1: **[IMAGE PROMPT]** — System architecture (frontend → backend →
  model service → DB, with SHAP + augmenter side-branches)
- Figure 5.2: **[SCREENSHOT — Anurag provides]** — Checkout page
- Figure 5.3: **[SCREENSHOT — Anurag provides]** — Transactions dashboard
- Figure 5.4: **[SCREENSHOT — Anurag provides]** — Analytics page
- Figure 5.5: **[IMAGE PROMPT]** — HF Space deployment topology

**Hinglish tracker items:** FastAPI+Next.js brief, multi-tenancy funda,
HF Space deployment.

---

## Section 6 — Multi-Agent Test Case Methodology (5-6 pages — DEEP DIVE)

### 6.1 The Testing Problem
- Why aggregate PR-AUC hides typology-level failures
- Need for stress-testing across specific fraud + legit patterns

### 6.2 Multi-Agent Pipeline Architecture
- Per-member: 3 generator agents + 1 validator agent
- Each generator uses a different LLM provider
  (Claude, GPT, Grok, DeepSeek, NVIDIA, Meta, Qwen, Gemini, others)
- Team scale: 3 members × 4 agents = 12 agents active in parallel
- The **validator's 5 checks**: schema, semantic, distribution, duplicate,
  anti-contamination

### 6.3 Anti-Bias Design
- No single provider's blind spot dominates ground truth
- Rotation across batches to prevent stylistic drift
- Rejection + regeneration loop for semantically wrong rows

### 6.4 Isolation Guarantees (from mentor briefing)
- Only 8 checkout fields reach the model — labels held back
- Test cases never stored, never trained on, zero fine-tuning
- Labels + typology metadata used only for post-scoring comparison

### 6.5 Anurag's Quality Gate
- Manual pass on aggregated 12-agent output
- Statistical audit — distribution match to Sparkov, category vocab compliance
- Approve / reject entire batch

### 6.6 The Twelve Typologies
- Five fraud: card_testing, velocity_spike, weekend_spike,
  late_night_bulk_fraud, cross_category_fraud
- Seven legit: routine_grocery, wedding_order, senior_routine,
  high_value_regular, corporate_lunch, fuel_purchase, late_night_hostel

### 6.7 Test Rounds (V1 → V2 → V3)
Batch summary table:
| Round | Rows | Fraud | Legit | Author |
| V1 | 714 | 341 | 373 | Team member A |
| V2 | 150K | 62,119 | 87,881 | Team member B |
| V3 | 3M | 1,250,107 | 1,749,893 | Team member B (new batch) |

### 6.8 Schema Compliance — A Practical Lesson
- One batch received (V3 from another author) with wrong schema
- Rejected, spec doc sent back, lesson recorded
- Reference to `docs/TestCase_Schema_Spec_for_Gurnoor.txt`

**Diagrams:**
- Figure 6.1: **[IMAGE PROMPT]** — Multi-agent pipeline architecture
  (3 lanes × 4 agents, validator loop, aggregator)
- Figure 6.2: **[IMAGE PROMPT]** — 12 diverse agents distinct visualization

**Hinglish tracker items:** 12-agent architecture, held-out guarantee,
V1/V2/V3 rounds, schema drift lesson.

---

## Section 7 — Results & Analysis (5-6 pages)

### 7.1 Aggregate Performance Across Three Test Rounds
- V1 (714 rows): 93.2% decisive accuracy
- V2 (150K rows): 93.4% decisive accuracy
- V3 (3M rows): 92.13% decisive accuracy
- Zero engine errors on 3M

### 7.2 Scale Invariance — The Headline Finding
- Same model, three orders of magnitude, accuracy within 1.3 pp
- What this means: methodology is not overfit to test set size

### 7.3 Per-Typology Breakdown (V3, 3M rows)
Two tables:
- Fraud typologies: block/review/approved percentages
- Legit typologies: approved/review/blocked percentages
- Called out: card_testing 0% blocked / 35% missed = the honest weak spot

### 7.4 Confusion Matrices
Three matrices (V1, V2, V3):
- Fraud: block / review / approved counts
- Legit: approved / review / blocked counts

### 7.5 Calibration Quality
- Brier 0.0008, ECE 0.0006 — reliability diagram (from ROC-AUC script)
- Why calibration matters for threshold routing

### 7.6 SHAP Explanations (real transaction walkthrough)
- One example high-risk transaction
- Top-5 SHAP contributions
- What an analyst sees on the dashboard

**Diagrams:**
- Figure 7.1: **[GENERATED — I'll make]** — Scale invariance chart
  (accuracy vs test set size on log-x axis)
- Figure 7.2: **[GENERATED — I'll make]** — Per-typology stacked bar (V3)
- Figure 7.3: **[GENERATED — I'll make]** — Confusion matrix heatmap (V3)
- Figure 7.4: (Calibration reliability from Section 4)
- Figure 7.5: **[IMAGE PROMPT]** — SHAP waterfall example

**Hinglish tracker items:** V1/V2/V3 scale invariance, per-typology
verdict, calibration matter, SHAP dashboard.

---

## Section 8 — Iterative Improvements & Challenges (4-5 pages — DEEP DIVE)

*This is the honesty section — where the report earns credibility.*

### 8.1 The V3 Audit
- Weak typologies identified: card_testing (0% block, 35% missed),
  high_value_regular (22.9% false-block), late_night_hostel (60% review)
- Full findings referenced from `docs/MODEL_AUDIT_POST_3M.md`

### 8.2 First Attempt — Augmentation-Driven Retrain (2026-07-18)
- What I tried: widen amount range, add legit-rescue rows, retrain
- What happened: 92% → 61% decisive accuracy collapse
- Root cause I diagnosed: **label collision at identical feature signatures**
  — sub-$10 food_dining labelled fraud (card_testing) overlapped with
  sub-$10 food_dining labelled legit (corporate_lunch)
- Full revert executed the same day
- What I learned: tree ensembles amplify label conflicts via
  `scale_pos_weight` — a 5% augmentation share becomes a 20× local
  gradient when scale_pos_weight = 400

### 8.3 The Feasibility Probe (2026-07-19)
- Second attempt: I designed a fresh training dataset via the multi-agent
  pipeline, isolated to `v2-chimera-fd/` folder to protect production
- Before committing 3-5 days to dataset generation, I ran a 45-minute
  read-only feasibility probe
- Findings:
  - 22 of 30 features are constants keyed on `demo_profile`
  - `cc_num_seconds_since_prev` (velocity signal) is hardcoded per profile
  - **46.5% of card_testing feature signatures collide with late_night_hostel**
  - The card_testing typology's defining signal is structurally absent
    from the model's input

### 8.4 The Catch-22 (the intellectual centerpiece)
Three paths for a rule-layer fix, all closed:
- **Training-derived rule** → redundant (model already learned it)
- **Test-derived rule** → contamination (integrity violation)
- **Domain-knowledge-derived rule** → unfalsifiable without evidence

Consequence: this class of defect requires a *feature change*, not a data
or rule change. Out of scope before the 30 July deadline; recorded as an
honest next step.

### 8.5 The Null-Result Rule Experiment
- Rule 4 (`night_micro_amount`) — threshold derived from Sparkov training
  data (integrity-clean chain)
- Zero false positives on 143,060 legit training rows
- On 100K held-out: fired 90 times (predicted ~3,600)
- Root cause: augmenter's `if raw_decision != "approve"` early return —
  the model already routes collision-zone rows to review
- **Actual effect: +0.32 pp handled rate improvement**, target was +10 pp
- 30% precision (63 legit reviewed / 27 fraud caught)
- **Verdict: null result. Shipped disabled by default with documented
  activation path.**

### 8.6 Other Challenges
- Hugging Face Space 10MB storage limit — resolved via
  `git filter-repo` history rewrite
- Multi-tenancy verification — tests as source of truth, not convention
- Test schema drift (V3 wrong schema batch) — spec doc + validator loop

### 8.7 What This Section Represents
The report of a null result with rigorous methodology is a better
deliverable than a small win dressed up as significant. This is the
engineering story I stand behind.

**Diagrams:**
- Figure 8.1: **[GENERATED — I'll make]** — Before/after collapse chart
  (accuracy trajectory across the retrain attempt)
- Figure 8.2: **[IMAGE PROMPT]** — Feature signature collision visualization
  (card_testing vs late_night_hostel overlap)
- Figure 8.3: **[IMAGE PROMPT]** — The catch-22 diagram (3 closed doors)

**Hinglish tracker items:** kal ka failure full story, feasibility probe
kya karta hai, catch-22 finding (bade sikhne wali baat), rule 4 null
result kyu disable kiya, HF storage lesson.

---

## Section 9 — Roadmap & Future Work (2 pages)

### 9.1 Immediate Post-Internship Work
- Real per-card `seconds_since_prev` feature — the identified fix for
  card_testing feature-space gap
- Retrain on augmented Sparkov training data containing card_testing
  patterns (the multi-agent framework post-schema-spec is ready)

### 9.2 Stage 2 GraphSAGE Specialist
- For the review band (~8% of traffic)
- Honest null on IEEE-CIS reported earlier — different topologies
  (money mule networks) would likely benefit

### 9.3 Multi-Agent Dataset Framework (validated infrastructure)
- The 12-agent pipeline is production-ready
- Applicable to other structured-data generation problems in the fraud
  domain and beyond
- Potential post-internship research direction

### 9.4 Frontend Improvements
- SHAP waterfall live in analyst dashboard (data ready, UI pending)
- Per-typology rule-hit breakdown view

### 9.5 Ops Improvements
- Alembic-managed migrations once schema stabilises
- Prometheus metrics endpoint for rule-hit telemetry
- Structured SLOs (review-rate cap, error budget)

**Diagrams:** none needed.

**Hinglish tracker items:** post-internship roadmap, GraphSAGE plan, multi-agent
framework future value.

---

## Section 10 — Conclusion (1 page)

- Three-sentence summary of what the project achieved
- The engineering discipline I applied (documented in Section 8)
- One paragraph acknowledging what I learned that the numbers don't show

Closing sentence:
> CHIMERA-FD is a shippable, defensible fraud detection system that
> understands its own limits — not a Kaggle notebook.

**Diagrams:** none.

---

## References (2 pages)

- 16-paper corpus in author-year IEEE format
- Additional 4 foundational papers added post-briefing:
  Ke et al. 2017 (LightGBM), Lundberg-Lee 2017 (SHAP),
  Niculescu-Mizil-Caruana 2005 (Isotonic), Chawla et al. 2002 (SMOTE)
- Total: 20 references

---

## Appendices (5-8 pages)

- **A. Configuration & Deployment Details** — HF Space secrets, Docker
  build steps, Postgres schema
- **B. Full Per-Typology Results Tables** — V1, V2, V3 with block/review/
  approved counts
- **C. Multi-Agent Pipeline Schema** — the JSON payload spec sent to
  Gurnoor (from docs/TestCase_Schema_Spec_for_Gurnoor.txt)
- **D. Feasibility Probe & Rule 4 Findings** — detailed technical
  reports from `v2-chimera-fd/evaluation/`
- **E. Reference Repository Structure** — file tree with key modules
  called out

---

## Diagram checklist summary

| # | Section | Type | Status |
|---|---------|------|--------|
| 2.1 | Research | IMAGE PROMPT | to write |
| 2.2 | Research | IMAGE PROMPT | to write |
| 3.1 | Dataset | GENERATED | I can make |
| 4.1 | Model | IMAGE PROMPT | to write |
| 4.2 | Model | GENERATED (feature imp) | I can make |
| 4.3 | Model | ROC-AUC SCRIPT | Anurag runs |
| 4.4 | Model | ROC-AUC SCRIPT | Anurag runs |
| 4.5 | Model | ROC-AUC SCRIPT | Anurag runs |
| 4.6 | Model | ROC-AUC SCRIPT | Anurag runs |
| 4.7 | Model | IMAGE PROMPT | to write |
| 4.8 | Model | IMAGE PROMPT | to write |
| 5.1 | Architecture | IMAGE PROMPT | to write |
| 5.2 | Architecture | SCREENSHOT | Anurag adds |
| 5.3 | Architecture | SCREENSHOT | Anurag adds |
| 5.4 | Architecture | SCREENSHOT | Anurag adds |
| 5.5 | Architecture | IMAGE PROMPT | to write |
| 6.1 | Testing | IMAGE PROMPT | to write |
| 6.2 | Testing | IMAGE PROMPT | to write |
| 7.1 | Results | GENERATED (scale invariance) | I can make |
| 7.2 | Results | GENERATED (per-typology) | I can make |
| 7.3 | Results | GENERATED (confusion) | I can make |
| 7.4 | Results | (reuse 4.5) | — |
| 7.5 | Results | IMAGE PROMPT | to write |
| 8.1 | Challenges | GENERATED (regression chart) | I can make |
| 8.2 | Challenges | IMAGE PROMPT | to write |
| 8.3 | Challenges | IMAGE PROMPT | to write |

**Total: 24 figures.**
- 6 need the ROC-AUC script run (Anurag runs on Windows)
- 3 screenshots from Anurag
- 8 data-driven diagrams I can generate from stored evaluation JSONs
- 7 image prompts for external image gen (DALL-E, Midjourney, Firefly)

---

## Approval checkpoint

**Anurag, please confirm:**

1. Structure OK, no section to add/remove/reorder?
2. Deep-dive on Section 4 (Model), 6 (Testing), 8 (Challenges) —
   correct balance?
3. Frontend/backend brief in Section 5 (~2 paragraphs each, no code) —
   agreed?
4. 24 total diagrams manageable? Any you don't want?
5. Executive Summary length: 1 page — OK?
6. Total pages target: 35-45 (excluding appendices) — realistic?

Once you approve this outline, I'll draft Section 1 first (Introduction &
Problem Statement) so you can react to tone/voice. If tone works, I'll
continue with 2 and 3 in the same style.

---

**Hinglish version:** After English report v1 is done, I'll rewrite each
section in Hinglish narrative style using the tracker at
`v2-chimera-fd/HINGLISH_TRACKER.md`.
