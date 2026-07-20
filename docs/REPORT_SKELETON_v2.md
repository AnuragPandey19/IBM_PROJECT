# CHIMERA-FD — Project Report Skeleton (v2 — expanded)

**Status:** Anurag approved v1; this v2 adds standard project-report diagrams
(use case, sequence, class, ER, activity, state, component, deployment
topology, data flow) plus an expanded deployment section.

**Target format:** Microsoft Word (`.docx`) — this MD file is skeleton only.
The actual report will be generated using the docx skill and saved to
`docs/CHIMERA-FD_Project_Report.docx`.

**Length target:** 40-50 pages including expanded diagrams and appendices.

---

## Front matter (2-3 pages)

- Cover page (title, author, IBM logo placeholder, submission date, supervisor)
- Acknowledgments (team + mentor + AI-assisted tooling honest disclosure)
- Table of contents (auto)
- List of figures + tables
- **Executive Summary (1 page):** two paragraphs, headline numbers.

---

## Section 1 — Introduction & Problem Statement (3-4 pages)

### 1.1 Motivation
- $33.5B card fraud, 75% card-not-present
- Three failure modes of rule engines
- Constraint stack (imbalance, latency, explainability)

### 1.2 Project Scope + Timeline
- Sprint window: 23 June - 30 July 2026
- Team of 4, my role
- Deliverables: system + written report + live demo

### 1.3 What I Set Out to Build
- Two-stage cascaded pipeline
- Multi-tenant B2B portal
- Live-deployed on Hugging Face Spaces

### 1.4 Report Structure

**Diagrams:**
- Figure 1.1: **[IMAGE PROMPT]** — Sprint timeline / Gantt chart
  showing weeks 1-5, work items per week
- Figure 1.2: **[IMAGE PROMPT]** — Team organization / role split

**Hinglish tracker:** origin story, dukaandar analogy, PR-AUC vs accuracy.

---

## Section 2 — Research Foundation (4-5 pages)

### 2.1 Corpus Overview (16 papers)
### 2.2 The Five Load-Bearing Papers
### 2.3 Explainability-Imbalance Paradox — extended discussion
### 2.4 Where We Diverge

**Diagrams:**
- Figure 2.1: **[IMAGE PROMPT]** — SMOTE vs cost-sensitive-loss illustration
- Figure 2.2: **[IMAGE PROMPT]** — 5 papers → 5 design pillars → CHIMERA-FD

**Hinglish tracker:** Zafar-Wu paradox mirror analogy, 5 hero papers simple.

---

## Section 3 — Dataset Choice & Analysis (3-4 pages)

### 3.1 Four Candidate Datasets (comparison table)
### 3.2 IEEE-CIS as Research Baseline
### 3.3 Sparkov for Live Demo
### 3.4 ULB and PaySim Rejected
### 3.5 Documented Limitation (Sparkov has zero card-testing patterns)

**Diagrams:**
- Table 3.1: 4-dataset comparison
- Figure 3.1: **[GENERATED]** — dataset size vs fraud rate scatter

**Hinglish tracker:** IEEE vs Sparkov choice, ULB reject reason.

---

## Section 4 — Model Design & Training (6-7 pages — DEEP DIVE)

### 4.1 Two-Stage Cascaded Design
### 4.2 Stage 1 LightGBM Choice
### 4.3 Sparkov Feature Engineering (30 features from 8 fields)
### 4.4 Stage 3 Isotonic Recalibration
### 4.5 Threshold Selection (history + rationale)
### 4.6 Training Results (val PR-AUC 0.827, test 0.805, Brier 0.0008)
### 4.7 Decision Augmenter (post-model safety nets)

**Diagrams:**
- Figure 4.1: **[IMAGE PROMPT]** — Two-stage cascaded pipeline flow
- Figure 4.2: **[GENERATED]** — Feature importance bar chart (top-10 by gain)
- Figure 4.3: **[FROM ROC-AUC SCRIPT]** — ROC curve
- Figure 4.4: **[FROM ROC-AUC SCRIPT]** — PR curve
- Figure 4.5: **[FROM ROC-AUC SCRIPT]** — Calibration reliability
- Figure 4.6: **[FROM ROC-AUC SCRIPT]** — Score distribution histogram
- Figure 4.7: **[IMAGE PROMPT]** — Feature engineering flow (8 → 30 features)
- Figure 4.8: **[IMAGE PROMPT]** — Decision augmenter's three rules
- Figure 4.9: **[IMAGE PROMPT]** — **State diagram** — transaction lifecycle:
  `pending → scored → (approve | review | block) → persisted` states
  with transitions and augmenter override arrow

**Hinglish tracker:** LightGBM vs XGBoost, Isotonic simple, feature engineering,
velocity feature limitation.

---

## Section 5 — System Architecture (6-7 pages — EXPANDED)

*Diagram-heavy. UML diagrams for all standard software engineering views.*

### 5.1 High-Level Architecture Overview
Brief prose + one master architecture figure.

### 5.2 Use Case Analysis
UML use case diagram — who does what:
- Actors: Customer (checkout), Fraud Analyst (dashboard review),
  Admin (multi-tenant management), Merchant (integration via API),
  External System (payment gateway)
- Use cases: submit_transaction, view_risk_score, mark_reviewed,
  drill_into_shap, create_company, provision_analyst, view_analytics

### 5.3 Request Lifecycle (Sequence Diagram)
UML sequence — end-to-end flow when a customer submits a checkout:
- Customer → Frontend (submit)
- Frontend → FastAPI /api/checkout (POST with 8 fields)
- FastAPI → ModelService.score_sparkov()
- ModelService → SparkovLookups.encode()
- ModelService → LightGBM.predict_proba()
- ModelService → decision_augmenter.apply_safety_nets()
- FastAPI → Postgres.INSERT Transaction + Prediction
- FastAPI → Frontend (approve/review/block decision + SHAP top-5)
- Frontend → Customer (display outcome)

### 5.4 Class Diagram (Key Backend Classes)
UML class diagram — key classes and relationships:
- ModelService (singleton)
- Stage1LightGBM
- IsotonicCalibrator
- SparkovLookups (singleton)
- decision_augmenter (module)
- Transaction, Prediction, Company, User (ORM models)
- CheckoutRequest, CheckoutResponse (Pydantic schemas)

### 5.5 Component Diagram
UML component diagram — high-level system components and their
interfaces:
- Frontend component
- FastAPI Gateway component
- Model Service component
- Persistence Layer component
- External: Postgres, HF Space runtime

### 5.6 Data Flow Diagram (DFD Level 1)
How data moves through the system:
- External entities: Customer, Analyst, Merchant Portal, Fraud Team
- Processes: 1.0 Ingest Payload, 2.0 Enrich Features, 3.0 Score Model,
  4.0 Apply Rules, 5.0 Persist + Return
- Data stores: Transaction DB, Prediction DB, Model Artifacts

### 5.7 Activity Diagram (Transaction Processing Workflow)
UML activity diagram — process flow with decision branches:
- Start → Receive payload → Validate schema → Enrich profile →
  Build features → Score model → Threshold decision →
  Augmenter checks → Persist → Return response → End

### 5.8 Entity-Relationship (ER) Diagram
Database schema visualization:
- Company (1) → (many) Users
- Company (1) → (many) Transactions
- Transaction (1) → (1) Prediction
- User has role (analyst | admin)
- Attributes for each entity

### 5.9 Frontend Overview (brief)
- Next.js 15 stack, key views (checkout, transactions, analytics)
- ~2 paragraphs, no code

### 5.10 Backend Overview (brief)
- FastAPI + Uvicorn, SQLAlchemy 2.0, JWT auth, rate limiting
- ~2 paragraphs, no code

### 5.11 Multi-Tenancy Enforcement (brief)
- company_id FK model, require_company dependency, 404 not 403
- Verified by test_multi_tenancy.py

**Diagrams:**
- Figure 5.1: **[IMAGE PROMPT]** — Master architecture (frontend → backend
  → model service → DB, with SHAP + augmenter side-branches)
- Figure 5.2: **[IMAGE PROMPT]** — **Use Case Diagram** (UML) — 5 actors,
  10-12 use cases
- Figure 5.3: **[IMAGE PROMPT]** — **Sequence Diagram** (UML) — full
  request lifecycle for /api/checkout
- Figure 5.4: **[IMAGE PROMPT]** — **Class Diagram** (UML) — ModelService
  + Stage1LightGBM + IsotonicCalibrator + SparkovLookups + ORM models
- Figure 5.5: **[IMAGE PROMPT]** — **Component Diagram** (UML) — system
  components + interfaces
- Figure 5.6: **[IMAGE PROMPT]** — **Data Flow Diagram** (DFD Level 1)
- Figure 5.7: **[IMAGE PROMPT]** — **Activity Diagram** (UML) — transaction
  processing workflow
- Figure 5.8: **[IMAGE PROMPT]** — **Entity-Relationship (ER) Diagram** —
  Company / User / Transaction / Prediction schema
- Figure 5.9: **[SCREENSHOT — Anurag adds]** — Checkout page
- Figure 5.10: **[SCREENSHOT — Anurag adds]** — Transactions dashboard
- Figure 5.11: **[SCREENSHOT — Anurag adds]** — Analytics page

**Hinglish tracker:** FastAPI+Next.js brief, multi-tenancy funda,
UML diagrams intuition (kya kis diagram ka role hai).

---

## Section 6 — Deployment & Operations (3-4 pages — NEW DEDICATED SECTION)

### 6.1 Deployment Target — Why Hugging Face Spaces
- Free Docker-image hosting
- Same repo as code (mono-deploy)
- Live-reachable URL for mentor demo
- Comparison table: HF Spaces vs Render vs AWS vs Vercel (why HF won)

### 6.2 Docker Image Strategy
- Single multi-stage Dockerfile
  - Stage 1: Node builds Next.js static export
  - Stage 2: Python runtime pulls the static export + FastAPI + models
- One image, one port (7860), one process
- Image size after LFS: ~250 MB
- Cold-boot: ~5-8 min first build, ~30s cached rebuild

### 6.3 Configuration & Secrets
- Environment variables (as HF Space Repository Secrets):
  - `DATABASE_URL` → Postgres on Render
  - `JWT_SECRET_KEY` → 64-char hex
  - `ENV=prod` → disables /docs
  - `LOG_LEVEL=INFO`

### 6.4 External Dependencies
- **Postgres on Render** (free tier, internal URL) — the only persistent
  data store
- LFS storage for model artifacts (~28MB per pkl)

### 6.5 CI/CD Pipeline
- GitHub Actions triggers on push:
  - pytest run (unit + integration + multi-tenancy suite)
  - Ruff lint
- `git push hf main` triggers HF Space auto-rebuild
- Dual-remote setup: `github` (source of truth), `hf` (deployment)

### 6.6 Startup Sequence
- Container starts → Uvicorn boots FastAPI
- init_db() runs — schema create + auto-migration for missing columns
- ModelService.load() + warmup() — LightGBM JIT-caches with dummy predict
- SparkovLookups.load() — target-encoding dicts into memory
- Health check at `/api/health`

### 6.7 Live URL + Access
- Public URL: `https://undebuggedbit-chimera-fd.hf.space`
- Login: register a company + analyst via UI
- Admin bootstrap via `scripts/create_admin.py`

### 6.8 Rollback Strategy
- Git revert + push → HF auto-rebuilds previous version
- LFS artifact history preserved (model rollback via `git checkout`)

### 6.9 Post-Deployment Verification Checklist
- Health endpoint returns 200
- Model warmup completes without error
- Multi-tenancy test suite passes against live URL
- Checkout /api/checkout returns approve/review/block correctly

**Diagrams:**
- Figure 6.1: **[IMAGE PROMPT]** — **Deployment Diagram** (UML) —
  container topology: HF Space Docker (Node + Python + models) →
  Postgres on Render, with client browser
- Figure 6.2: **[IMAGE PROMPT]** — **Network Topology** — client →
  HF Space → Postgres, showing HTTPS + TLS + firewall boundaries
- Figure 6.3: **[IMAGE PROMPT]** — **CI/CD Pipeline** — GitHub → Actions →
  (lint + test) → dual push to github/hf → HF auto-rebuild
- Figure 6.4: **[IMAGE PROMPT]** — Multi-stage Dockerfile build stages
  (Node builder → Python runtime)

**Hinglish tracker:** HF Space simple explanation, Docker single-image funda,
Postgres on Render, dual-remote push flow, CI/CD kya karta hai.

---

## Section 7 — Multi-Agent Test Case Methodology (5-6 pages — DEEP DIVE)

*Was Section 6 in v1; renumbered.*

### 7.1 Testing Problem — Why Aggregate PR-AUC Hides Failures
### 7.2 Multi-Agent Pipeline Architecture (12 agents)
### 7.3 Anti-Bias Design (LLM provider diversity)
### 7.4 Isolation Guarantees (mentor briefing)
### 7.5 Manual Quality Gate
### 7.6 The Twelve Typologies
### 7.7 Test Rounds (V1 → V2 → V3)
### 7.8 Schema Compliance — Practical Lesson

**Diagrams:**
- Figure 7.1: **[IMAGE PROMPT]** — Multi-agent pipeline (3 lanes × 4 agents,
  validator loop, aggregator, model runner)
- Figure 7.2: **[IMAGE PROMPT]** — 12 diverse agents visualization
- Figure 7.3: **[IMAGE PROMPT]** — Validator's 5-check flowchart
  (schema → semantic → distribution → duplicate → anti-contamination)

**Hinglish tracker:** 12-agent architecture, held-out guarantee,
V1/V2/V3 story, schema drift lesson.

---

## Section 8 — Results & Analysis (5-6 pages)

*Was Section 7 in v1; renumbered.*

### 8.1 Aggregate Performance (V1, V2, V3)
### 8.2 Scale Invariance — Headline Finding
### 8.3 Per-Typology Breakdown (V3)
### 8.4 Confusion Matrices
### 8.5 Calibration Quality
### 8.6 SHAP Explanations (real transaction walkthrough)

**Diagrams:**
- Figure 8.1: **[GENERATED]** — Scale invariance chart (accuracy vs test set
  size on log-x axis, 3 data points)
- Figure 8.2: **[GENERATED]** — Per-typology stacked bar (V3, 12 typologies ×
  3 outcomes)
- Figure 8.3: **[GENERATED]** — Confusion matrix heatmap (V3, 3M rows)
- Figure 8.4: **[reuse Figure 4.5]** — Calibration reliability
- Figure 8.5: **[IMAGE PROMPT]** — SHAP waterfall example (one high-risk
  transaction)

**Hinglish tracker:** V1/V2/V3 scale invariance, per-typology verdict,
calibration matters, SHAP dashboard.

---

## Section 9 — Iterative Improvements & Challenges (5-6 pages — DEEP DIVE)

*Was Section 8 in v1; renumbered. This is the honesty section.*

### 9.1 The V3 Audit (weak typologies)
### 9.2 First Attempt — Augmentation Regression (2026-07-18)
### 9.3 The Feasibility Probe (2026-07-19)
### 9.4 The Catch-22 (intellectual centerpiece)
### 9.5 Null-Result Rule Experiment (2026-07-20)
### 9.6 Other Challenges (HF storage, multi-tenancy, schema drift)
### 9.7 What This Section Represents

**Diagrams:**
- Figure 9.1: **[GENERATED]** — Before/after regression trajectory chart
- Figure 9.2: **[IMAGE PROMPT]** — Feature signature collision visualization
  (card_testing vs late_night_hostel overlap)
- Figure 9.3: **[IMAGE PROMPT]** — Catch-22 diagram (3 closed doors:
  training-derived / test-derived / domain-derived)
- Figure 9.4: **[GENERATED]** — Rule 4 fire distribution + precision chart

**Hinglish tracker:** kal ka failure full story, feasibility probe kya karta,
catch-22 finding (bade sikhne wali baat), rule 4 null result kyu disabled,
HF storage lesson.

---

## Section 10 — Roadmap & Future Work (2 pages)

### 10.1 Immediate Post-Internship (real seconds_since_prev feature)
### 10.2 Stage 2 GraphSAGE Specialist
### 10.3 Multi-Agent Dataset Framework (post-internship research)
### 10.4 Frontend Improvements (SHAP waterfall)
### 10.5 Ops Improvements (Alembic, metrics, SLOs)

**Diagrams:**
- Figure 10.1: **[IMAGE PROMPT]** — Roadmap timeline (post-July 30 milestones)

---

## Section 11 — Conclusion (1 page)

- Three-sentence summary
- Engineering discipline applied
- What I learned that numbers don't show
- Closing sentence.

---

## References (2-3 pages)

- 16-paper corpus + 4 foundational papers = 20 total
- IEEE author-year format
- Split into: Load-bearing (5 highlighted with ★), Supporting corpus (11),
  Foundational (4)

---

## Appendices (6-10 pages)

- **A. Configuration & Deployment Details** — HF secrets, Docker steps,
  Postgres schema DDL
- **B. Full Per-Typology Results Tables** — V1, V2, V3 with counts
- **C. Multi-Agent Pipeline Schema** — from
  `docs/TestCase_Schema_Spec_for_Gurnoor.txt`
- **D. Feasibility Probe & Rule 4 Findings** — from
  `v2-chimera-fd/evaluation/`
- **E. Reference Repository Structure** — file tree with key modules
- **F. API Endpoints Reference** — OpenAPI-style summary of key routes
- **G. Sample SHAP Explanations** — 3-4 real transactions with SHAP tops

---

## Complete diagram checklist

| # | Section | Type of Diagram | Source |
|---|---------|-----------------|--------|
| 1.1 | Intro | Sprint Gantt chart | IMAGE PROMPT |
| 1.2 | Intro | Team org chart | IMAGE PROMPT |
| 2.1 | Research | SMOTE vs cost-sensitive illustration | IMAGE PROMPT |
| 2.2 | Research | 5 papers → 5 pillars fan-out | IMAGE PROMPT |
| 3.1 | Dataset | Dataset size vs fraud rate scatter | GENERATED |
| 4.1 | Model | Two-stage cascaded pipeline flow | IMAGE PROMPT |
| 4.2 | Model | Feature importance bar chart | GENERATED |
| 4.3 | Model | ROC curve | SCRIPT (ran ✓) |
| 4.4 | Model | PR curve | SCRIPT (ran ✓) |
| 4.5 | Model | Calibration reliability | SCRIPT (ran ✓) |
| 4.6 | Model | Score distribution histogram | SCRIPT (ran ✓) |
| 4.7 | Model | Feature engineering flow (8→30) | IMAGE PROMPT |
| 4.8 | Model | Decision augmenter's 3 rules | IMAGE PROMPT |
| 4.9 | Model | **State diagram** — transaction lifecycle | IMAGE PROMPT |
| 5.1 | Architecture | Master architecture | IMAGE PROMPT |
| 5.2 | Architecture | **Use Case Diagram (UML)** | IMAGE PROMPT |
| 5.3 | Architecture | **Sequence Diagram (UML)** | IMAGE PROMPT |
| 5.4 | Architecture | **Class Diagram (UML)** | IMAGE PROMPT |
| 5.5 | Architecture | **Component Diagram (UML)** | IMAGE PROMPT |
| 5.6 | Architecture | **Data Flow Diagram (DFD)** | IMAGE PROMPT |
| 5.7 | Architecture | **Activity Diagram (UML)** | IMAGE PROMPT |
| 5.8 | Architecture | **ER Diagram** — database schema | IMAGE PROMPT |
| 5.9 | Architecture | Checkout page screenshot | Anurag adds |
| 5.10 | Architecture | Transactions dashboard screenshot | Anurag adds |
| 5.11 | Architecture | Analytics page screenshot | Anurag adds |
| 6.1 | Deployment | **Deployment Diagram (UML)** | IMAGE PROMPT |
| 6.2 | Deployment | Network Topology | IMAGE PROMPT |
| 6.3 | Deployment | CI/CD Pipeline | IMAGE PROMPT |
| 6.4 | Deployment | Multi-stage Dockerfile stages | IMAGE PROMPT |
| 7.1 | Testing | Multi-agent pipeline architecture | IMAGE PROMPT |
| 7.2 | Testing | 12 diverse agents visualization | IMAGE PROMPT |
| 7.3 | Testing | Validator's 5-check flowchart | IMAGE PROMPT |
| 8.1 | Results | Scale invariance chart | GENERATED |
| 8.2 | Results | Per-typology stacked bar (V3) | GENERATED |
| 8.3 | Results | Confusion matrix heatmap (V3) | GENERATED |
| 8.5 | Results | SHAP waterfall example | IMAGE PROMPT |
| 9.1 | Challenges | Regression trajectory chart | GENERATED |
| 9.2 | Challenges | Feature signature collision viz | IMAGE PROMPT |
| 9.3 | Challenges | Catch-22 diagram (3 closed doors) | IMAGE PROMPT |
| 9.4 | Challenges | Rule 4 fire distribution + precision | GENERATED |
| 10.1 | Roadmap | Post-internship roadmap timeline | IMAGE PROMPT |

**Total: 39 figures.**
- **4 from ROC-AUC script** (Anurag ran — outputs ready ✓)
- **3 screenshots from Anurag**
- **9 data-driven diagrams I generate** from stored evaluation JSONs
- **23 image prompts** for external image gen (DALL-E / Midjourney / Firefly)

---

## Standard project-report diagram types now covered

Following UML + software engineering conventions:

| Diagram type | Coverage | Section |
|--------------|----------|---------|
| Use Case Diagram | ✓ Fig 5.2 | Architecture |
| Sequence Diagram | ✓ Fig 5.3 | Architecture |
| Class Diagram | ✓ Fig 5.4 | Architecture |
| Component Diagram | ✓ Fig 5.5 | Architecture |
| Data Flow Diagram (DFD) | ✓ Fig 5.6 | Architecture |
| Activity Diagram | ✓ Fig 5.7 | Architecture |
| Entity-Relationship (ER) | ✓ Fig 5.8 | Architecture |
| State Diagram | ✓ Fig 4.9 | Model |
| Deployment Diagram (UML) | ✓ Fig 6.1 | Deployment |
| Network Topology | ✓ Fig 6.2 | Deployment |
| CI/CD Pipeline | ✓ Fig 6.3 | Deployment |
| Gantt Chart | ✓ Fig 1.1 | Intro |
| Master Architecture | ✓ Fig 5.1 | Architecture |
| ROC / PR / Calibration | ✓ Fig 4.3-4.6 | Model |
| Confusion Matrix Heatmap | ✓ Fig 8.3 | Results |
| Feature Importance | ✓ Fig 4.2 | Model |
| Model Pipeline Flow | ✓ Fig 4.1 | Model |

**Every standard project-report diagram type is included.**

---

## Approval + next step

**Anurag — please confirm before I start drafting the DOCX:**

1. Sections + diagram list all OK?
2. Deployment section (6) — enough depth for what mentor will want?
3. 39 total figures — comfortable with that many?

**Once you say "start drafting":**

- I'll use the docx skill to create `docs/CHIMERA-FD_Project_Report.docx`
- Draft Section 1 first (with placeholders for figures using
  `[FIGURE 1.1: <prompt>]` markers you can replace)
- Show you the docx for tone/voice review
- Iterate section by section

Kya add karna hai kuch aur? Ya start drafting?
