# CHIMERA-FD — Project Report Skeleton (v3 — final)

**Changes in v3 (per Anurag's 2026-07-20 feedback):**
1. Internship start corrected to **10 June 2026**; 15-26 June is a
   dedicated research phase (before development).
2. Report framed as **team project throughout** — "we" voice, explicit
   role attribution, Sanvi's Sparkov dataset acquisition credited.
3. Section 9 restructured as **stages of iterative development** rather
   than "Audit V1 / V2 / V3." Each stage: what we did → what problem we
   identified → how we responded. This avoids the "what was V1 vs V2"
   question from the mentor.

**Target format:** Microsoft Word (`.docx`) at
`docs/CHIMERA-FD_Project_Report.docx`. This skeleton stays in MD.

**Length target:** 40-50 pages.

---

## Team roles (for use throughout the report)

| Member | Primary role |
|--------|--------------|
| Anurag Pandey | Full-stack architecture, backend, frontend, deployment, retrain orchestration, model service integration, decision augmenter, multi-tenancy |
| Pankaj Singh | Model research, feature engineering review, test case authoring at scale, iteration analysis |
| Gurnoor Multani | Literature review (16-paper corpus + 4 foundational), dataset justification, test case authoring |
| Sanvi Bharadwaj | Dataset acquisition (Sparkov survey + selection), test case authoring support, quality gate assistance |

Every section references team members by role where relevant. First-person
plural ("we", "our") throughout; individual attribution only where a
specific member led a decision.

---

## Front matter (2-3 pages)

- Cover page (title, all 4 authors, IBM logo placeholder, submission date)
- Acknowledgments — team + mentor + AI-assisted tooling (honest disclosure)
- Table of contents
- List of figures + tables
- **Executive Summary (1 page):** headline numbers, methodology
  contribution, honest note on the identified structural limit.

---

## Section 1 — Introduction & Problem Statement (3-4 pages)

### 1.1 Motivation
- $33.5B global card fraud (2022), 75% card-not-present
- Three failure modes of rule engines
- Constraint stack: class imbalance, 200ms latency, regulatory
  explainability (PSD2, GDPR Art. 22, RBI, PCI-DSS)

### 1.2 Project Timeline & Team

**Internship window:** 10 June - 30 July 2026 (~7 weeks total).

**Two phases:**

- **Phase 1 — Research (15-26 June, ~2 weeks)**
  - Literature review (16 papers) — led by Gurnoor
  - Dataset survey and evaluation — led by Sanvi
  - Architecture design and technology stack decisions — Anurag
  - Model methodology selection (LightGBM + cost-sensitive learning
    + isotonic calibration) — Pankaj

- **Phase 2 — Development, Testing, Iteration (27 June - 30 July, ~5 weeks)**
  - System build (backend + frontend + deployment)
  - Multi-agent test case generation pipeline design + execution
  - Progressive testing at increasing scale (small → large)
  - Iterative improvement cycles (documented in Section 9)

Team of 4; distinct responsibilities as listed above.

### 1.3 What We Set Out to Build
- Two-stage cascaded fraud detection pipeline
- Multi-tenant B2B live web application
- Live-deployed demo on Hugging Face Spaces
- Rigorous multi-agent test methodology with mentor-defensible isolation

### 1.4 Report Structure

**Diagrams:**
- Figure 1.1: **[IMAGE PROMPT]** — Sprint Gantt chart (10 June - 30 July
  timeline, research phase 15-26 June clearly marked)
- Figure 1.2: **[IMAGE PROMPT]** — Team organization / role split
  (4 members, primary responsibilities)

**Hinglish tracker:** timeline explanation, team role split, rule engines
failure modes with dukaandar analogy.

---

## Section 2 — Research Foundation (4-5 pages)

*Phase 1 output. Led by Gurnoor with team review.*

### 2.1 Corpus Overview (16 papers)
### 2.2 The Five Load-Bearing Papers (Zafar-Wu, Thivaios, Nie, Cheng, Almalki)
### 2.3 Explainability-Imbalance Paradox — extended discussion
### 2.4 Where Our Approach Diverges from the Corpus

**Diagrams:**
- Figure 2.1: **[IMAGE PROMPT]** — SMOTE vs cost-sensitive-loss illustration
- Figure 2.2: **[IMAGE PROMPT]** — 5 papers → 5 design pillars → CHIMERA-FD

**Hinglish tracker:** Zafar-Wu paradox mirror analogy, 5 hero papers simple.

---

## Section 3 — Dataset Selection & Analysis (3-4 pages)

*Phase 1 output. Led by Sanvi with team decision.*

### 3.1 The Dataset Question
- Why the choice of dataset is a first-order decision for the whole
  project (features drive interpretability drive SHAP quality)

### 3.2 Sanvi's Dataset Survey
- **Sanvi surveyed candidate datasets:** IEEE-CIS (Vesta),
  Sparkov (simulator), ULB Kaggle, PaySim
- Evaluation criteria: realism, feature interpretability, size,
  fraud rate, licensing, alignment with checkout-flow schema
- Comparison table produced by Sanvi

### 3.3 Why IEEE-CIS as Research Baseline
- 590K real card-not-present transactions from Vesta
- 434 named features → meaningful SHAP
- Time-based 80/10/10 split

### 3.4 Why Sparkov for Live Demo — Sanvi's Recommendation
- **Sanvi identified and acquired the Sparkov dataset** from its public
  release, ran initial exploration, and recommended it as the live-demo
  dataset because its named merchant categories map 1:1 to a
  real checkout payload (unlike IEEE-CIS's anonymized card1-card6)
- Team accepted the recommendation after design review

### 3.5 Datasets Rejected — with Reasons
- ULB Kaggle rejected (PCA-anonymized features kill SHAP)
- PaySim rejected (mobile-money — wrong transaction type)

### 3.6 A Limitation Documented Early
- During Phase 1 exploration, Sanvi + Pankaj noted that Sparkov's
  simulator does not generate card-testing patterns (measured later
  in Phase 2 — cheapest fraudulent night transaction in 1.48M
  training rows is $5.60)
- Recorded as a known limitation, surfaced empirically in Section 9

**Diagrams:**
- Table 3.1: 4-dataset comparison (Sanvi's original survey)
- Figure 3.1: **[GENERATED]** — dataset size vs fraud rate scatter

**Hinglish tracker:** Sanvi ne kya kiya (Sparkov dataset), IEEE vs Sparkov
choice, ULB kyu reject, Sparkov ki known limitation.

---

## Section 4 — Model Design & Training (6-7 pages — DEEP DIVE)

*Phase 1 methodology, Phase 2 execution. Led by Pankaj with Anurag
integrating into service.*

### 4.1 Two-Stage Cascaded Design
### 4.2 Stage 1 LightGBM (why over XGBoost)
### 4.3 Sparkov Feature Engineering (30 features from 8 fields)
### 4.4 Stage 3 Isotonic Recalibration
### 4.5 Threshold Selection (history + rationale)
### 4.6 Training Results (val PR-AUC 0.827, test 0.805, Brier 0.0008)
### 4.7 Decision Augmenter (post-model safety nets)

**Diagrams:**
- Figure 4.1: **[IMAGE PROMPT]** — Two-stage cascaded pipeline flow
- Figure 4.2: **[GENERATED]** — Feature importance bar chart (top-10)
- Figure 4.3: **[FROM ROC-AUC SCRIPT ✓]** — ROC curve
- Figure 4.4: **[FROM ROC-AUC SCRIPT ✓]** — PR curve
- Figure 4.5: **[FROM ROC-AUC SCRIPT ✓]** — Calibration reliability
- Figure 4.6: **[FROM ROC-AUC SCRIPT ✓]** — Score distribution histogram
- Figure 4.7: **[IMAGE PROMPT]** — Feature engineering flow (8→30)
- Figure 4.8: **[IMAGE PROMPT]** — Decision augmenter's three rules
- Figure 4.9: **[IMAGE PROMPT]** — **State diagram** — transaction lifecycle

**Hinglish tracker:** LightGBM vs XGBoost, Isotonic simple, feature
engineering, velocity feature limitation (mentioned briefly here,
elaborated in Section 9).

---

## Section 5 — System Architecture (6-7 pages)

*Phase 2 execution. Led by Anurag.*

### 5.1 High-Level Architecture Overview
### 5.2 Use Case Analysis (5 actors, 12 use cases)
### 5.3 Request Lifecycle (Sequence Diagram)
### 5.4 Class Diagram (ModelService, ORM models)
### 5.5 Component Diagram
### 5.6 Data Flow Diagram (DFD Level 1)
### 5.7 Activity Diagram (transaction processing)
### 5.8 Entity-Relationship (ER) Diagram
### 5.9 Frontend Overview (brief)
### 5.10 Backend Overview (brief)
### 5.11 Multi-Tenancy Enforcement (brief)

**Diagrams:**
- Figure 5.1: **[IMAGE PROMPT]** — Master architecture
- Figure 5.2: **[IMAGE PROMPT]** — Use Case Diagram (UML)
- Figure 5.3: **[IMAGE PROMPT]** — Sequence Diagram (UML)
- Figure 5.4: **[IMAGE PROMPT]** — Class Diagram (UML)
- Figure 5.5: **[IMAGE PROMPT]** — Component Diagram (UML)
- Figure 5.6: **[IMAGE PROMPT]** — Data Flow Diagram (DFD)
- Figure 5.7: **[IMAGE PROMPT]** — Activity Diagram (UML)
- Figure 5.8: **[IMAGE PROMPT]** — Entity-Relationship (ER)
- Figure 5.9: **[SCREENSHOT — Anurag adds]** — Checkout page
- Figure 5.10: **[SCREENSHOT — Anurag adds]** — Transactions dashboard
- Figure 5.11: **[SCREENSHOT — Anurag adds]** — Analytics page

**Hinglish tracker:** UML diagrams role, multi-tenancy funda.

---

## Section 6 — Deployment & Operations (3-4 pages)

*Phase 2 execution. Led by Anurag.*

### 6.1 Deployment Target — Why Hugging Face Spaces
### 6.2 Docker Image Strategy (multi-stage: Node → Python)
### 6.3 Configuration & Secrets
### 6.4 External Dependencies (Postgres on Render)
### 6.5 CI/CD Pipeline (GitHub Actions + dual-remote push)
### 6.6 Startup Sequence (init_db + auto-migration + warmup)
### 6.7 Live URL + Access
### 6.8 Rollback Strategy
### 6.9 Post-Deployment Verification Checklist

**Diagrams:**
- Figure 6.1: **[IMAGE PROMPT]** — Deployment Diagram (UML)
- Figure 6.2: **[IMAGE PROMPT]** — Network Topology
- Figure 6.3: **[IMAGE PROMPT]** — CI/CD Pipeline
- Figure 6.4: **[IMAGE PROMPT]** — Multi-stage Dockerfile stages

**Hinglish tracker:** HF Space simple, Docker single-image funda,
Postgres on Render, CI/CD kya karta.

---

## Section 7 — Multi-Agent Test Case Methodology (5-6 pages — DEEP DIVE)

*Phase 2 execution. Team pipeline — Anurag designed the orchestration
pattern; all four members ran the 4-agent instance during test rounds;
Pankaj + Gurnoor + Sanvi authored + validated test batches.*

### 7.1 Testing Problem — Aggregate PR-AUC Hides Failures
### 7.2 Multi-Agent Pipeline Architecture (12 agents = 3 members × 4 agents each)
### 7.3 Anti-Bias Design (LLM provider diversity)
### 7.4 Isolation Guarantees (mentor-approved)
### 7.5 Manual Quality Gate (Anurag + team review)
### 7.6 The Twelve Typologies
### 7.7 Progressive Test Rounds (increasing scale)
### 7.8 Schema Compliance — Practical Lesson

**Diagrams:**
- Figure 7.1: **[IMAGE PROMPT]** — Multi-agent pipeline (3 lanes × 4 agents)
- Figure 7.2: **[IMAGE PROMPT]** — 12 diverse agents visualization
- Figure 7.3: **[IMAGE PROMPT]** — Validator's 5-check flowchart

**Hinglish tracker:** 12-agent full story, held-out guarantee,
progressive testing.

---

## Section 8 — Results & Analysis (5-6 pages)

*Phase 2 execution. Team analysis.*

### 8.1 Aggregate Performance Across Progressive Test Scales
### 8.2 Scale Invariance — Headline Finding
### 8.3 Per-Typology Breakdown (large-scale round)
### 8.4 Confusion Matrices (three scales)
### 8.5 Calibration Quality
### 8.6 SHAP Explanations (real transaction walkthrough)

**Diagrams:**
- Figure 8.1: **[GENERATED]** — Scale invariance chart (log-x axis)
- Figure 8.2: **[GENERATED]** — Per-typology stacked bar
- Figure 8.3: **[GENERATED]** — Confusion matrix heatmap
- Figure 8.4: (reuse Figure 4.5)
- Figure 8.5: **[IMAGE PROMPT]** — SHAP waterfall example

**Hinglish tracker:** scale invariance, per-typology verdict, SHAP dashboard.

---

## Section 9 — Iterative Development & Findings (5-6 pages — DEEP DIVE)

*This section replaces the "Audit V1/V2/V3" framing with a chronological
stage-based narrative. Each stage: what we did → what we identified →
how we responded. This is the honest engineering story of Phase 2.*

### 9.1 Overview
We executed testing and improvement in progressive stages, each one
informing the next. Stage numbers are chronological, not test-suite
version numbers.

### 9.2 Stage 1 — Initial Deployment + Small-Scale Testing

**What we did:**
- Deployed Stage 1 LightGBM (Sparkov) + Isotonic on HF Space
- Anurag integrated the model into the FastAPI service
- Ran first test batch (~700 rows, small labeled set covering all 12
  typologies)

**What we found:**
- Aggregate ~93% decisive accuracy — encouraging headline
- All strong typologies performed as expected
- Two weak signals appeared: `card_testing` missed some rows,
  `high_value_regular` flagged more often than expected

**What we did about it:**
- Flagged the signals but did not respond yet — small sample sizes,
  waited for larger-scale evidence

### 9.3 Stage 2 — Scaling Up Test Coverage

**What we did:**
- Pankaj authored a mid-scale test batch (~150K rows) using our
  multi-agent pipeline
- Anurag ran the scoring pipeline end-to-end
- Team reviewed per-typology results

**What we found:**
- 93.4% aggregate — scale-invariant with the small batch (good)
- Weak-typology signals confirmed: `card_testing` 0% blocked and
  35% silently approved; `late_night_hostel` over-reviewed;
  `high_value_regular` false-block rate rising

**What we did about it:**
- Team decided to attempt a data-level intervention (see Stage 3)
- Documented findings in a formal engineering audit before acting

### 9.4 Stage 3 — Attempted Data Augmentation

**What we did:**
- Extended the augmentation script to broaden card_testing amount
  ranges and category coverage
- Added synthetic "legit-rescue" rows for high-spender profiles
- Raised augmentation share from 3% to 5%
- Retrained the Sparkov Stage 1 model on the augmented data

**What we found:**
- On the very first re-evaluation chunk, aggregate accuracy collapsed
  from 92% to 61%
- Root cause diagnosed by the team: **label collision at identical
  feature signatures.** Sub-$10 food_dining rows labelled fraud
  (card_testing) overlapped with sub-$10 food_dining rows labelled
  legit (corporate_lunch). LightGBM cannot separate points at the
  same location in feature space with opposite labels;
  `scale_pos_weight = 400` amplified the local gradient conflict
  globally, poisoning tree splits far from the augmented region

**What we did about it:**
- Reverted the retrain the same day
  (`git checkout HEAD -- models/stage1_sparkov.pkl`)
- Restored the deployed model to its pre-augmentation state
- Wrote a post-mortem — this class of failure requires a different
  approach than another augmentation attempt

### 9.5 Stage 4 — Larger-Scale Testing to Confirm Weakness Reproducibility

**What we did:**
- Pankaj authored a large-scale test batch (~3M rows) to confirm the
  Stage 2 findings at a scale where sampling noise is negligible
- Anurag built a chunked runner to score 3M rows without memory issues
  (100K per chunk, checkpointed, resumable)
- Full run completed in ~2 hours

**What we found:**
- 92.13% aggregate accuracy — scale-invariant across three orders
  of magnitude of test set size (700 → 150K → 3M)
- Weak-typology signals confirmed at scale (statistically firm):
  - `card_testing`: 0% blocked, 35% silently approved
  - `high_value_regular`: 22.9% false-block
  - `late_night_hostel`: 60.5% review rate
- Zero engine errors across 3 million rows

**What we did about it:**
- Team decided to attempt a rule-layer fix, but only after doing due
  diligence — a feasibility probe before committing days to another
  potentially-failing intervention

### 9.6 Stage 5 — Feasibility Probe Before Any Further Intervention

**What we did:**
- Isolated the exploration in a fully-sandboxed folder
  (`v2-chimera-fd/`) with `.gitignore` and `.dockerignore` protecting
  the deployed system
- Ran a 30-45 minute read-only probe on the model's feature builder,
  the model artifact, and the training + held-out distributions

**What we found:**
- **Only 8 of the model's 30 features respond to the transaction.**
  The other 22 are constants keyed on `demo_profile` or wall-clock noise
- `cc_num_seconds_since_prev` — the feature that would express
  card-testing velocity — is hardcoded per profile
- **46.5% of card_testing feature signatures collide with legitimate
  `late_night_hostel` rows** at the level of information the model
  actually consumes
- The **catch-22 finding**: a training-derived rule is redundant
  (the model has already learned that boundary from the same data);
  a test-derived rule is contamination (integrity violation of the
  held-out guarantee); a purely domain-derived rule is unfalsifiable
  without evidence. All three doors are closed for this class of defect
  at the rule layer

**What we did about it:**
- Team decided that closing card_testing's block-rate gap requires
  a **feature-space change** (real per-card `seconds_since_prev`
  computed at inference), not a data change or rule change
- That feature change is out of scope for the internship window
  (would require inference-time state management infrastructure)
- Recorded as the honest next step and updated our promotion criteria
  to reflect what is achievable within the current feature space

### 9.7 Stage 6 — Null-Result Rule Experiment

**What we did:**
- Derived a threshold rule from the model's training distribution
  (not from the held-out test set — clean integrity chain)
- Added `night_micro_amount` as a fourth rule in the decision augmenter
- Ran a 100K row experiment before committing to full-scale evaluation

**What we found:**
- Rule fired 90 times in 100K rows (predicted ~3,600)
- Root cause: the augmenter contractually only fires when the model
  decision is "approve." The model already routes most collision-zone
  rows to review, so the rule finds few eligible rows to act on
- **Actual handled-rate improvement: +0.32 percentage points**
  (target was +10 pp — short by a factor of 31)
- Precision 30% (63 legit rows moved to review to catch 27 card-testing
  probes)

**What we did about it:**
- Team decided the rule works exactly as designed but does not deliver
  meaningful operational value at this precision level
- Shipped the rule **disabled by default** with a flag
  (`ENABLE_SAFETY_NET_NIGHT_MICRO=false`), the derivation chain fully
  documented, and an activation path for business teams whose
  review-queue economics may make the trade-off worthwhile
- Recorded the null result with the same rigor as we would a
  successful intervention

### 9.8 Other Challenges Encountered

- **Hugging Face Space storage limit** (10 MB non-LFS blocked pushes
  with large evaluation artifacts) — resolved via `git filter-repo`
  history rewrite + gitignore hardening
- **Multi-tenancy correctness** — protected by dedicated integration
  tests rather than convention; regression caught early
- **Test schema drift** — one late test batch arrived with an
  incompatible schema; team responded with a formal schema spec doc
  and a validator loop for future batches

### 9.9 What This Section Represents

The engineering story of a team that investigated its own findings
rigorously, admitted when interventions failed, and reported null
results with the same discipline as positive ones.

**Diagrams:**
- Figure 9.1: **[GENERATED]** — Stage 3 regression trajectory chart
  (accuracy over the retrain attempt: baseline → augmented → reverted)
- Figure 9.2: **[IMAGE PROMPT]** — Feature signature collision
  visualization (card_testing vs late_night_hostel overlap)
- Figure 9.3: **[IMAGE PROMPT]** — Catch-22 diagram (three closed doors:
  training-derived / test-derived / domain-derived)
- Figure 9.4: **[GENERATED]** — Stage 6 rule fire distribution
  (predicted vs actual + precision breakdown)

**Hinglish tracker:** stages framing (not V1/V2/V3), Stage 3 collapse
full story, feasibility probe kya karta, catch-22 finding — bade sikhne
wali baat, rule 4 null result kyu disabled, HF storage lesson.

---

## Section 10 — Roadmap & Future Work (2 pages)

### 10.1 Immediate Next Step — Real `seconds_since_prev` Feature
### 10.2 Stage 2 GraphSAGE Specialist
### 10.3 Multi-Agent Dataset Framework as Post-Internship Research
### 10.4 Frontend Improvements (SHAP waterfall live)
### 10.5 Ops Improvements (Alembic, metrics, SLOs)

**Diagrams:**
- Figure 10.1: **[IMAGE PROMPT]** — Post-internship roadmap timeline

---

## Section 11 — Conclusion (1 page)

- Three-sentence summary
- Engineering discipline the team applied
- What we learned that the numbers don't show
- Closing sentence

---

## References (2-3 pages)

- 16-paper corpus + 4 foundational = 20 total
- IEEE author-year format
- Load-bearing (5, marked ★), Supporting (11), Foundational (4)

---

## Appendices (6-10 pages)

- **A. Configuration & Deployment Details**
- **B. Full Per-Typology Results Tables**
- **C. Multi-Agent Pipeline Schema Spec**
- **D. Feasibility Probe & Stage 6 Rule Findings**
- **E. Repository Structure**
- **F. API Endpoints Reference**
- **G. Sample SHAP Explanations**

---

## Complete diagram checklist (unchanged from v2 — 39 figures)

Standard project-report diagram types all covered:
Use Case, Sequence, Class, Component, DFD, Activity, ER, State,
Deployment (UML), Network Topology, CI/CD Pipeline, Gantt,
Master Architecture, ROC / PR / Calibration, Confusion Matrix,
Feature Importance, Model Pipeline Flow.

Total: 39 figures
- 4 from ROC-AUC script (Anurag ran ✓)
- 3 screenshots (Anurag adds)
- 9 data-driven (I generate)
- 23 image prompts (Anurag generates externally)

---

## Approval + start signal

Anurag — v3 skeleton addresses all your 2026-07-20 feedback:
- Section 1.2 rewritten with 10 June start + Phase 1 research 15-26 June
- Team roles table at top, referenced through every section
- Sanvi's Sparkov dataset acquisition credited in Section 3
- Section 9 fully restructured as stages (no "V1/V2/V3 audit" language)

Say **"start drafting"** and I'll create
`docs/CHIMERA-FD_Project_Report.docx` using the docx skill, starting
with Section 1 for tone/voice review.
