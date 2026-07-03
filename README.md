---
title: CHIMERA-FD Fraud Detection
emoji: 🛡️
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# CHIMERA-FD

**Cascaded Hybrid Inference with Multi-modal Explanations and Recalibration for Adaptive Fraud Detection.**

IBM Internship Capstone Project | 23 June – 30 July 2026
Team: Anurag Pandey, Pankaj Singh, Gurnoor Multani, Sanvi Bharadwaj

---

## 🌐 Live demo

**https://undebuggedbit-chimera-fd.hf.space** — click, sign in, score a transaction.

## 🚀 Deploy on Hugging Face Spaces

This repo doubles as a HF Docker Space. Push to a Space repo and it auto-builds
the multi-stage Dockerfile (Node builds Next.js → Python runtime serves both
FastAPI and the static frontend on the same port).

### Required environment variables (set as Space secrets)

| Variable            | Example                                              |
|---------------------|------------------------------------------------------|
| `DATABASE_URL`      | `postgresql://user:pass@dpg-abc.render.com/chimera`  |
| `JWT_SECRET_KEY`    | 64-char random hex — `python -c "import secrets;print(secrets.token_hex(32))"` |
| `ENV`               | `prod` (disables /docs)                              |
| `LOG_LEVEL`         | `INFO`                                               |

### Deployment steps

1. **Provision Postgres on Render** — Render dashboard → New PostgreSQL (free
   plan) → copy the **Internal Database URL** starting with `postgresql://…`.
2. **Create the Space** on huggingface.co (SDK = Docker), then push:
   ```bash
   git remote add hf https://huggingface.co/spaces/<user>/chimera-fd
   git push hf main
   ```
3. **Add secrets** in Space settings using the table above.
4. **Bootstrap admin** once the Space is live:
   `POST /auth/register` via Swagger or `python scripts/create_admin.py`.

First build takes ~5–8 min (LightGBM + Node + Python deps); subsequent
builds are cached.

### Local Docker

```bash
docker build -t chimera-fd .
docker run --rm -p 7860:7860 \
    -e DATABASE_URL="postgresql://user:pass@host/db" \
    -e JWT_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
    -e ENV=prod \
    chimera-fd
```

Open `http://localhost:7860`.

---

---

## What is this?

A two-stage fraud detection pipeline that combines a fast LightGBM triage scorer with a graph-neural-network specialist for uncertain cases. The novel contribution is not the models themselves — every component is off-the-shelf. The novelty is:

1. **Explanation-aware training.** We handle class imbalance via cost-sensitive loss instead of SMOTE, so post-hoc SHAP explanations remain faithful to the real data distribution. This directly addresses the explainability-imbalance paradox identified by Zafar & Wu (AI Review, 2026).
2. **Three-axis evaluation.** Detection (PR-AUC), calibration (ECE, Brier), and explanation faithfulness are reported together.
3. **Cascaded fast-slow inference.** 92% of transactions cleared by Stage 1 in <5ms. Only the uncertain band hits the expensive graph specialist.

See `docs/` for the full research write-up and reference architecture diagrams.

---

## Repository layout

```
CHIMERA-FD/
├── config/
│   └── config.yaml           # All configurable paths and hyperparameters
├── data/
│   ├── raw/                  # NOT committed. Points at ../ieee-fraud-detection/
│   ├── processed/            # Generated parquet files
│   └── external/
├── notebooks/
│   └── 01_data_exploration.ipynb
├── scripts/
│   └── prepare_data.py       # One-command data prep
├── src/chimera_fd/
│   ├── config.py             # Config loader
│   ├── data/                 # Loading, splitting
│   ├── features/             # Feature engineering (Week 2)
│   ├── models/               # Stage 1 LightGBM, Stage 2 GraphSAGE (Week 2)
│   ├── evaluation/           # PR-AUC + calibration + faithfulness (Week 3)
│   └── api/                  # FastAPI service (Week 3)
├── tests/
├── docs/
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Quick start (Windows)

**Prerequisites:** Python 3.10+, Git, and the IEEE-CIS raw CSVs sitting in `..\ieee-fraud-detection\` relative to this project.

```powershell
# 1. Create a virtual environment
cd C:\Users\undeb\Documents\PROJECTS\IBM\CHIMERA-FD
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 3. Verify the config finds your data
python -m chimera_fd.config

# 4. Run data prep (full data — takes ~2-5 min, uses ~4 GB RAM)
python scripts\prepare_data.py

# Or, for a quick smoke test first:
python scripts\prepare_data.py --nrows 50000

# 5. Start Jupyter and run the exploration notebook
jupyter notebook notebooks\01_data_exploration.ipynb
```

### Common troubleshooting

| Problem | Fix |
|---|---|
| `FileNotFoundError` when loading IEEE-CIS | Check paths in `config/config.yaml`. Default assumes `../ieee-fraud-detection/`. |
| Out of memory during data prep | Use `--nrows 100000` to work on a slice; or set `train_downsample_frac: 0.2` in config. |
| `ImportError: chimera_fd` | Run `pip install -e .` from project root so the src/ layout is on the path. |
| Slow parquet write | Confirm `pyarrow` is installed (`pip show pyarrow`). |
| LightGBM warns about OpenMP on Windows | Harmless. Ignore or install the Visual C++ 2015 runtime. |

---

## The 4-week plan

| Week | Dates | Deliverable |
|---|---|---|
| W1 | 23–29 Jun | Data merge, EDA, LightGBM Stage 1 baseline |
| W2 | 30 Jun – 6 Jul | GraphSAGE Stage 2 + Fusion Head + Isotonic calibration |
| W3 | 7–13 Jul | SHAP + GNNExplainer + Counterfactuals + FastAPI |
| W4 | 14–20 Jul | Streamlit dashboard + Docker + Sparkov cross-dataset test |
| Buffer | 21–30 Jul | Report, slides, demo video, viva prep |

---

## Ground rules for contributors

1. **Never use SMOTE.** We use `scale_pos_weight` / focal loss instead. This is a research contribution, not a preference.
2. **Never random-split a time-series.** Use `chimera_fd.data.splitter.time_based_split`. The splitter raises if you try.
3. **Never report accuracy as a headline metric.** PR-AUC first, then precision-at-recall, then F1. Accuracy on 3.5% fraud is meaningless.
4. **Never touch the test set during tuning.** Use `val.parquet` for hyperparameter search. Test is opened exactly once at the end.
5. **Commit code, not data.** `.gitignore` protects `data/`. Do not force-add CSVs or parquets.
6. **Every feature has a comment saying whether it would be available at prediction time.** If you can't say yes with certainty, do not include it. This prevents target leakage.

---

## Running tests

```powershell
pytest tests/ -v
```

---

## References

Full 16-paper corpus in `docs/CHIMERA-FD_Literature_and_Architecture.docx`.
Key citation for the methodological contribution:

> Zafar, U., & Wu, F. (2026). Methodological challenges in explainable AI for fraud detection: a systematic literature review. *AI Review*, 59:115.

---

## License

Internal capstone project. Not licensed for redistribution while the internship is ongoing.
