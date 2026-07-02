"""Generate SHAP explanations for the trained Stage 1 model.

Outputs:
  reports/shap/global_summary.csv          — top features by mean |SHAP|
  reports/shap/global_summary_bar.png      — global feature bar plot
  reports/shap/global_summary_beeswarm.png — SHAP beeswarm (subsample)
  reports/shap/local_examples.md           — natural-language explanations
  reports/shap/shap_values_val_sample.npy  — SHAP values for later use
  reports/shap/val_sample.parquet          — the val rows used

Usage:
    python scripts/generate_shap.py
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from chimera_fd.config import load_config
from chimera_fd.data.loader import load_parquet
from chimera_fd.evaluation.explanations import Stage1SHAPExplainer
from chimera_fd.models.stage1_lightgbm import Stage1LightGBM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("generate_shap")

VAL_SAMPLE_SIZE = 2000


def main():
    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "ieee_cis"
    models_dir = ROOT / "models"
    out_dir = ROOT / "reports" / "shap"
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    log.info("Loading trained model...")
    model = Stage1LightGBM.load(models_dir / "stage1_lightgbm.pkl")
    log.info("Model has %d features, %d best iterations",
             len(model.feature_names), model.model.best_iteration)

    log.info("Loading engineered TRAIN (for un-resampled background)...")
    train = load_parquet(processed / "train_features.parquet")
    log.info("Loading engineered VAL (for explanations)...")
    val = load_parquet(processed / "val_features.parquet")

    log.info("=" * 60)
    log.info("Fitting SHAP explainer with UN-RESAMPLED background")
    log.info("(THIS IS THE METHODOLOGICAL CONTRIBUTION vs SMOTE baselines)")
    log.info("=" * 60)
    explainer = Stage1SHAPExplainer(
        model=model,
        background_data=train,
        max_background_size=500,
    )

    log.info("Sampling %d val rows for SHAP computation...", VAL_SAMPLE_SIZE)
    val_sample = val.sample(
        n=min(VAL_SAMPLE_SIZE, len(val)), random_state=42
    ).reset_index(drop=True)
    X_val = val_sample[model.feature_names]
    y_val = val_sample["isFraud"].values

    log.info("Computing SHAP values...")
    shap_vals = explainer.shap_values(X_val)
    log.info("SHAP values shape: %s", shap_vals.shape)

    np.save(out_dir / "shap_values_val_sample.npy", shap_vals)
    val_sample.to_parquet(out_dir / "val_sample.parquet", index=False)

    # -------- Global summary from precomputed SHAP values --------
    log.info("Generating global summary...")
    mean_abs = np.abs(shap_vals).mean(axis=0)
    global_summary = pd.DataFrame({
        "feature": model.feature_names,
        "mean_abs_shap": mean_abs,
    }).sort_values("mean_abs_shap", ascending=False).head(30).reset_index(drop=True)
    global_summary.to_csv(out_dir / "global_summary.csv", index=False)
    log.info("Top 10 global features by mean |SHAP|:\n%s",
             global_summary.head(10).to_string(index=False))

    # -------- Bar plot (fast, matplotlib native) --------
    log.info("Rendering global bar plot...")
    top20 = global_summary.head(20)
    fig, ax = plt.subplots(figsize=(10, 8))
    y_pos = np.arange(len(top20))[::-1]
    colors = ["#c00000" if ("target_enc" in f or "card1" in f) else "#1f4e79"
              for f in top20["feature"]]
    ax.barh(y_pos, top20["mean_abs_shap"].values, color=colors, edgecolor="white")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(top20["feature"].values, fontsize=9)
    ax.set_xlabel("Mean |SHAP value|", fontsize=11)
    ax.set_title("Global Feature Importance (mean |SHAP|) — Stage 1 LightGBM",
                 fontsize=12, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / "global_summary_bar.png", dpi=150, bbox_inches="tight")
    plt.close()

    # -------- Beeswarm (subsample for speed) --------
    log.info("Rendering beeswarm plot on top 20 features / 500 rows...")
    try:
        top20_feats = top20["feature"].head(20).tolist()
        sub_idx = [model.feature_names.index(f) for f in top20_feats]
        sub_vals = shap_vals[:500, sub_idx]
        sub_X = X_val.iloc[:500][top20_feats]
        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            sub_vals, sub_X,
            feature_names=top20_feats,
            max_display=20,
            show=False,
        )
        plt.tight_layout()
        plt.savefig(out_dir / "global_summary_beeswarm.png",
                    dpi=150, bbox_inches="tight")
        plt.close()
    except Exception as e:
        log.warning("Beeswarm plot skipped: %s", e)

    # -------- Local explanations (from precomputed values, no re-call) --------
    log.info("Generating local explanations...")
    scores = model.predict_proba(X_val)
    high_risk_idx = np.argsort(-scores)[:5]
    low_risk_idx = np.argsort(scores)[:5]

    def local_explain(idx: int, top_k: int = 5) -> str:
        vals_row = shap_vals[idx]
        base_prob = 1.0 / (1.0 + np.exp(-explainer.expected_value))
        pred_logit = float(explainer.expected_value) + float(vals_row.sum())
        pred_prob = 1.0 / (1.0 + np.exp(-pred_logit))
        order = np.argsort(-np.abs(vals_row))[:top_k]
        out = [
            f"Predicted fraud probability: {pred_prob:.3f} (baseline: {base_prob:.3f})",
            "Top contributing factors:",
        ]
        for i in order:
            direction = "up-fraud" if vals_row[i] > 0 else "down-fraud"
            feat = model.feature_names[i]
            val = X_val.iloc[idx][feat]
            out.append(f"  {direction}  {feat}={val}  (contribution {vals_row[i]:+.4f})")
        return "\n".join(out)

    lines = [
        "# Local SHAP Explanations - Sample Transactions",
        "",
        "Each block shows a transaction's fraud probability and the top contributing features.",
        "Positive contribution pushes toward FRAUD; negative pushes toward LEGIT.",
        "",
        "**Background is drawn from the un-resampled training distribution.** This is the",
        "CHIMERA-FD methodological contribution vs SMOTE-trained baselines.",
        "",
        "---",
        "",
        "## Top-5 HIGH-RISK transactions",
        "",
    ]
    for rank, idx in enumerate(high_risk_idx, start=1):
        actual = "FRAUD" if y_val[idx] == 1 else "LEGIT"
        pred = float(scores[idx])
        expl = local_explain(int(idx), top_k=5)
        lines.append(f"### #{rank} - P(fraud)={pred:.3f} - Actual: {actual}")
        lines.append("```")
        lines.append(expl)
        lines.append("```")
        lines.append("")

    lines.append("## Top-5 LOW-RISK transactions")
    lines.append("")
    for rank, idx in enumerate(low_risk_idx, start=1):
        actual = "FRAUD" if y_val[idx] == 1 else "LEGIT"
        pred = float(scores[idx])
        expl = local_explain(int(idx), top_k=5)
        lines.append(f"### #{rank} - P(fraud)={pred:.3f} - Actual: {actual}")
        lines.append("```")
        lines.append(expl)
        lines.append("```")
        lines.append("")

    with open(out_dir / "local_examples.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log.info("=" * 60)
    log.info("SHAP GENERATION COMPLETE in %.1f seconds", time.time() - t0)
    log.info("=" * 60)
    log.info("Files written to %s", out_dir)
    for p in sorted(out_dir.glob("*")):
        size = p.stat().st_size
        size_str = f"{size / 1024:.1f} KB" if size < 1e6 else f"{size / 1e6:.1f} MB"
        log.info("  %s (%s)", p.name, size_str)


if __name__ == "__main__":
    main()
