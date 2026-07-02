"""Evaluation metrics for fraud detection.

We report three axes:
  1. Detection quality: PR-AUC (primary), ROC-AUC (for reference), F1, precision@recall
  2. Calibration:       Brier score, ECE (Expected Calibration Error)
  3. Explanation:       computed in a separate module in Week 3 (faithfulness, stability)

Accuracy is NEVER reported as a headline. Fraud is 3.5% of data — a "predict 0"
model scores 96.5% accuracy and catches ZERO fraud.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


@dataclass
class MetricsReport:
    """Container for all metrics we compute on a single (y_true, y_score) pair."""
    n_samples: int
    n_positives: int
    fraud_rate_pct: float

    # Detection
    pr_auc: float
    roc_auc: float

    # Threshold-dependent (chosen threshold, defaults to argmax-F1 on val)
    chosen_threshold: float
    precision_at_threshold: float
    recall_at_threshold: float
    f1_at_threshold: float

    # Threshold-independent operating points
    precision_at_50_recall: float
    precision_at_80_recall: float
    recall_at_1pct_fpr: float
    recall_at_5pct_fpr: float

    # Calibration
    brier_score: float
    ece: float

    # Confusion matrix at chosen threshold
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    def as_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        lines = [
            f"  Samples:      {self.n_samples:,}",
            f"  Positives:    {self.n_positives:,} ({self.fraud_rate_pct:.3f}%)",
            "",
            "  DETECTION",
            f"    PR-AUC  (primary):        {self.pr_auc:.4f}",
            f"    ROC-AUC (secondary):      {self.roc_auc:.4f}",
            "",
            f"  AT THRESHOLD {self.chosen_threshold:.3f}",
            f"    Precision:                {self.precision_at_threshold:.4f}",
            f"    Recall:                   {self.recall_at_threshold:.4f}",
            f"    F1:                       {self.f1_at_threshold:.4f}",
            f"    Confusion:  TP={self.tp}  FP={self.fp}  TN={self.tn}  FN={self.fn}",
            "",
            "  OPERATING POINTS",
            f"    Precision @ 50% Recall:   {self.precision_at_50_recall:.4f}",
            f"    Precision @ 80% Recall:   {self.precision_at_80_recall:.4f}",
            f"    Recall    @ 1%  FPR:      {self.recall_at_1pct_fpr:.4f}",
            f"    Recall    @ 5%  FPR:      {self.recall_at_5pct_fpr:.4f}",
            "",
            "  CALIBRATION",
            f"    Brier Score:              {self.brier_score:.4f}",
            f"    ECE:                      {self.ece:.4f}",
        ]
        return "\n".join(lines)


def find_best_threshold(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Threshold that maximizes F1 on the given data. Use on VAL, not test."""
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_score)
    # sklearn returns len(thresh) = len(prec) - 1; align
    f1s = 2 * precisions[:-1] * recalls[:-1] / (precisions[:-1] + recalls[:-1] + 1e-12)
    if len(f1s) == 0:
        return 0.5
    return float(thresholds[int(np.nanargmax(f1s))])


def precision_at_recall(y_true: np.ndarray, y_score: np.ndarray, target_recall: float) -> float:
    """Precision when threshold is set to achieve at least `target_recall`."""
    precisions, recalls, _ = precision_recall_curve(y_true, y_score)
    # find the highest recall >= target_recall
    mask = recalls >= target_recall
    if not mask.any():
        return 0.0
    return float(precisions[mask][-1])


def recall_at_fpr(y_true: np.ndarray, y_score: np.ndarray, target_fpr: float) -> float:
    """Recall when threshold is set so that FPR <= target_fpr.

    FPR = FP / N (fraction of legit txns flagged). Lower is customer-friendlier.
    """
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score)
    order = np.argsort(-y_score)
    y_true_sorted = y_true[order]
    y_score_sorted = y_score[order]

    n_neg = int((y_true == 0).sum())
    n_pos = int((y_true == 1).sum())
    if n_neg == 0 or n_pos == 0:
        return 0.0

    # Walk down sorted scores. Stop when FPR would exceed target.
    cum_fp = np.cumsum(y_true_sorted == 0)
    cum_tp = np.cumsum(y_true_sorted == 1)
    fpr = cum_fp / n_neg
    tpr = cum_tp / n_pos
    # find largest k where fpr[k] <= target_fpr
    mask = fpr <= target_fpr
    if not mask.any():
        return 0.0
    return float(tpr[mask][-1])


def expected_calibration_error(y_true: np.ndarray, y_score: np.ndarray, n_bins: int = 10) -> float:
    """ECE = weighted average of |accuracy - confidence| across probability bins.

    In a well-calibrated model, if we predict P(fraud)=0.7 for 1000 transactions,
    ~700 of them should be fraud. ECE measures how far we are from that.
    """
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (y_score >= lo) & (y_score <= hi)
        else:
            mask = (y_score >= lo) & (y_score < hi)
        if not mask.any():
            continue
        bin_confidence = float(y_score[mask].mean())
        bin_accuracy = float(y_true[mask].mean())
        bin_weight = mask.sum() / n
        ece += bin_weight * abs(bin_accuracy - bin_confidence)
    return float(ece)


def evaluate(y_true, y_score, threshold: float | None = None) -> MetricsReport:
    """Compute all metrics. If threshold is None, uses argmax-F1 threshold."""
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score)

    if threshold is None:
        threshold = find_best_threshold(y_true, y_score)

    y_pred = (y_score >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm[0, 0], cm[0, 1], cm[1, 0], cm[1, 1]

    return MetricsReport(
        n_samples=len(y_true),
        n_positives=int(y_true.sum()),
        fraud_rate_pct=float(y_true.mean() * 100),

        pr_auc=float(average_precision_score(y_true, y_score)),
        roc_auc=float(roc_auc_score(y_true, y_score)),

        chosen_threshold=float(threshold),
        precision_at_threshold=float(precision_score(y_true, y_pred, zero_division=0)),
        recall_at_threshold=float(recall_score(y_true, y_pred, zero_division=0)),
        f1_at_threshold=float(f1_score(y_true, y_pred, zero_division=0)),

        precision_at_50_recall=precision_at_recall(y_true, y_score, 0.5),
        precision_at_80_recall=precision_at_recall(y_true, y_score, 0.8),
        recall_at_1pct_fpr=recall_at_fpr(y_true, y_score, 0.01),
        recall_at_5pct_fpr=recall_at_fpr(y_true, y_score, 0.05),

        brier_score=float(brier_score_loss(y_true, y_score)),
        ece=expected_calibration_error(y_true, y_score, n_bins=10),

        tp=int(tp), fp=int(fp), tn=int(tn), fn=int(fn),
    )
