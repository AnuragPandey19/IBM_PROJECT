"""Generate all architecture diagrams for the CHIMERA-FD project report.

Produces ~18 PNG diagrams into reports/diagrams/ folder. Visual style is:
colorful, rounded corners, gradient fills, minimal text density, print quality.

Run:
    python scripts/generate_report_diagrams.py

Each generator is a standalone function so they can be regenerated individually.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DPI = 200

# ------------------------------------------------------------------
# Colors — cohesive palette (rose accent + slate greys + supporting)
# ------------------------------------------------------------------
C = {
    "accent":     "#F43F5E",   # rose
    "accent_dk":  "#BE1F45",
    "user":       "#8B5CF6",   # violet
    "merchant":   "#0EA5E9",   # sky
    "backend":    "#EC4899",   # pink
    "frontend":   "#F59E0B",   # amber
    "db":         "#10B981",   # emerald
    "model":      "#8B5CF6",   # violet
    "external":   "#64748B",   # slate
    "bg":         "#0F172A",   # slate-900 (dark for prints, but we do LIGHT)
    "bg_light":   "#F8FAFC",   # slate-50
    "text":       "#0F172A",
    "text_light": "#F8FAFC",
    "muted":      "#94A3B8",
    "success":    "#10B981",
    "warn":       "#F59E0B",
    "danger":     "#EF4444",
    "line":       "#CBD5E1",
}


def _setup_ax(ax, title=None, xlim=(0, 100), ylim=(0, 100), bg=C["bg_light"]):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor(bg)
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold", color=C["text"], pad=6)


def _box(ax, xy, w, h, text, color=C["backend"], text_color="white",
         font_size=10, corner=0.4, bold=True, subtitle=None,
         edge=None, edge_width=1.5):
    """Draw a rounded box with text."""
    x, y = xy
    fbb = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.02,rounding_size={corner}",
        facecolor=color,
        edgecolor=edge if edge else color,
        linewidth=edge_width,
    )
    ax.add_patch(fbb)
    txt_x = x + w / 2
    txt_y = y + h / 2
    if subtitle:
        ax.text(txt_x, txt_y + h * 0.13, text, ha="center", va="center",
                fontsize=font_size, color=text_color,
                fontweight="bold" if bold else "normal")
        ax.text(txt_x, txt_y - h * 0.18, subtitle, ha="center", va="center",
                fontsize=font_size - 2, color=text_color, alpha=0.85)
    else:
        ax.text(txt_x, txt_y, text, ha="center", va="center",
                fontsize=font_size, color=text_color,
                fontweight="bold" if bold else "normal")


def _arrow(ax, xy_from, xy_to, color=C["muted"], style="-|>",
           lw=1.6, label=None, label_offset=(0, 0), curve=0):
    conn = "arc3,rad=" + str(curve) if curve else "arc3"
    a = FancyArrowPatch(xy_from, xy_to, arrowstyle=style,
                        color=color, lw=lw, mutation_scale=15,
                        connectionstyle=conn)
    ax.add_patch(a)
    if label:
        mx = (xy_from[0] + xy_to[0]) / 2 + label_offset[0]
        my = (xy_from[1] + xy_to[1]) / 2 + label_offset[1]
        ax.text(mx, my, label, fontsize=8, color=color,
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor="none", alpha=0.85))


def _save(fig, name):
    path = OUT_DIR / f"{name}.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=C["bg_light"])
    plt.close(fig)
    print(f"  ✓ {name}.png")


# ==================================================================
# 1. System Context Diagram
# ==================================================================
def diag_01_system_context():
    fig, ax = plt.subplots(figsize=(11, 7))
    _setup_ax(ax, "Figure 6.1: CHIMERA-FD — System Context")

    # Central system
    _box(ax, (35, 40), 30, 20, "CHIMERA-FD",
         color=C["accent"], font_size=16,
         subtitle="Fraud Detection Platform", corner=1.5)

    # External actors
    _box(ax, (5, 75), 22, 12, "End Customer",
         color=C["user"], subtitle="Buys goods, pays via card", corner=1)
    _box(ax, (73, 75), 22, 12, "Analyst",
         color=C["user"], subtitle="Reviews flagged transactions", corner=1)
    _box(ax, (5, 8), 22, 12, "Merchant Portal",
         color=C["merchant"], subtitle="Zomato / Swiggy / BigBasket", corner=1)
    _box(ax, (73, 8), 22, 12, "External DB",
         color=C["db"], subtitle="Render.com Postgres", corner=1)

    # Arrows in
    _arrow(ax, (16, 75), (40, 60), label="1. Payment", label_offset=(-5, 3))
    _arrow(ax, (16, 20), (40, 42), label="2. /checkout API call", label_offset=(-3, 0))
    _arrow(ax, (60, 42), (84, 20), label="3. Persist txn+prediction",
           label_offset=(2, 0))
    _arrow(ax, (60, 60), (84, 78), label="4. Analyst dashboard",
           label_offset=(4, 3))

    # Bottom footnote
    ax.text(50, 2, "Solid arrows = data flow  ·  Users interact with system, system interacts with external DB",
            ha="center", va="center", fontsize=8, color=C["muted"], style="italic")

    _save(fig, "01_system_context")


# ==================================================================
# 2. Container Diagram
# ==================================================================
def diag_02_container_diagram():
    fig, ax = plt.subplots(figsize=(12, 7.5))
    _setup_ax(ax, "Figure 6.2: High-Level Container Diagram")

    # Container: HF Space (outer)
    hf = FancyBboxPatch((5, 20), 68, 68,
                        boxstyle="round,pad=0.02,rounding_size=1.5",
                        facecolor="none",
                        edgecolor=C["accent"],
                        linewidth=2,
                        linestyle="--")
    ax.add_patch(hf)
    ax.text(39, 85, "Hugging Face Space (Docker container)",
            ha="center", fontsize=11, fontweight="bold", color=C["accent"])

    # Inside HF Space
    _box(ax, (10, 55), 28, 20, "Next.js Frontend",
         color=C["frontend"], subtitle="Static export served by FastAPI",
         font_size=11, corner=1)
    _box(ax, (43, 55), 25, 20, "FastAPI Backend",
         color=C["backend"], subtitle="Python 3.11 · uvicorn",
         font_size=11, corner=1)
    _box(ax, (10, 27), 28, 20, "Model Artifacts",
         color=C["model"], subtitle="LightGBM + isotonic + Sparkov",
         font_size=11, corner=1)
    _box(ax, (43, 27), 25, 20, "Sample Data",
         color=C["external"], subtitle="Parquet files",
         font_size=11, corner=1)

    # Outside: Render Postgres
    _box(ax, (80, 42), 17, 18, "PostgreSQL",
         color=C["db"], subtitle="Render.com",
         font_size=11, corner=1)

    # Outside: Users
    _box(ax, (80, 72), 17, 12, "Users",
         color=C["user"], subtitle="Browser",
         font_size=10, corner=1)

    # Arrows
    _arrow(ax, (39, 65), (43, 65), color=C["text"], label="serves")
    _arrow(ax, (55, 55), (55, 47), color=C["text"], label="loads at\nstartup")
    _arrow(ax, (68, 65), (80, 55), color=C["accent"], label="SQL")
    _arrow(ax, (88, 72), (55, 65), color=C["text"], label="HTTPS", curve=-0.15)
    _arrow(ax, (24, 55), (24, 47), color=C["text"], label="loads")

    ax.text(51, 15, "Single-container deploy: All Python + JS + models in one image. External Postgres for durable state.",
            ha="center", fontsize=8.5, color=C["muted"], style="italic")

    _save(fig, "02_container_diagram")


# ==================================================================
# 3. Backend Layered Architecture
# ==================================================================
def diag_03_backend_layered():
    fig, ax = plt.subplots(figsize=(11, 8))
    _setup_ax(ax, "Figure 7.1: Backend Layered Architecture")

    layers = [
        (75, "Client (Browser / Merchant Portal)", C["user"], "HTTP + JSON"),
        (63, "Routes  ·  api/routes/", C["backend"],
         "auth, predict, predict_sparkov, checkout, transactions, metrics,\n"
         "notifications, analytics, profile, health"),
        (49, "Dependencies  ·  api/dependencies/", C["accent"],
         "require_user()  ·  require_company()  ·  require_admin()  ·  get_db()"),
        (35, "Services  ·  api/services/", C["model"],
         "ModelService (singleton)  ·  FeatureService  ·  SparkovLookups"),
        (21, "DB Models  ·  api/db/models.py", C["db"],
         "Company · User · Transaction · Prediction · Feedback (SQLAlchemy ORM)"),
        (7, "PostgreSQL", C["external"], "Render.com managed database"),
    ]

    for y, name, color, sub in layers:
        _box(ax, (10, y), 80, 10, name,
             color=color, font_size=11, corner=0.6, subtitle=sub)

    # Arrows down
    for y in [73, 61, 47, 33, 19]:
        _arrow(ax, (50, y), (50, y - 3), color=C["muted"], lw=1.2)

    ax.text(50, 1, "Each layer depends only on the layer below. Cross-cutting concerns (auth, logging) in middleware.",
            ha="center", fontsize=8.5, color=C["muted"], style="italic")

    _save(fig, "03_backend_layered")


# ==================================================================
# 4. FastAPI Project Structure Tree
# ==================================================================
def diag_04_backend_structure():
    fig, ax = plt.subplots(figsize=(10, 8))
    _setup_ax(ax, "Figure 7.2: FastAPI Project Structure")

    lines = [
        (5, 92, "api/", C["accent"], "root package"),
        (10, 87, "main.py", C["text"], "app factory, router registration, lifespan"),
        (10, 82, "config.py", C["text"], "pydantic Settings, env-driven paths"),
        (10, 77, "routes/", C["backend"], "one file per REST resource"),
        (15, 72, "auth.py         register, login, /me", C["text"], ""),
        (15, 67, "predict.py      IEEE-CIS scoring", C["text"], ""),
        (15, 62, "predict_sparkov.py   Sparkov mode + /samples + /random", C["text"], ""),
        (15, 57, "checkout.py     public /checkout gateway simulator", C["text"], ""),
        (15, 52, "transactions.py list, filter, pagination", C["text"], ""),
        (15, 47, "metrics.py, notifications.py, analytics.py, profile.py", C["text"], ""),
        (10, 42, "services/", C["model"], "singletons + business logic"),
        (15, 37, "model_service.py    dual model loader + score + SHAP", C["text"], ""),
        (15, 32, "sparkov_lookups.py  target-encoder mappings", C["text"], ""),
        (15, 27, "feature_service.py  IEEE-CIS feature pipeline", C["text"], ""),
        (10, 22, "db/", C["db"], ""),
        (15, 17, "models.py       ORM classes", C["text"], ""),
        (15, 12, "session.py      engine, get_db(), init_db()", C["text"], ""),
        (10, 7, "schemas/, dependencies/", C["muted"], "Pydantic I/O + FastAPI deps"),
    ]

    for x, y, name, color, note in lines:
        weight = "bold" if x == 5 or (x == 10 and color != C["text"]) else "normal"
        ax.text(x, y, name, fontsize=10, color=color, fontweight=weight,
                fontfamily="monospace")
        if note:
            ax.text(65, y, note, fontsize=8, color=C["muted"],
                    fontstyle="italic")

    ax.text(50, 1, "Convention: one file per resource under routes/, one singleton per capability under services/",
            ha="center", fontsize=8.5, color=C["muted"], style="italic")

    _save(fig, "04_backend_structure")


# ==================================================================
# 5. ModelService Class Diagram
# ==================================================================
def diag_05_model_service_class():
    fig, ax = plt.subplots(figsize=(12, 7))
    _setup_ax(ax, "Figure 7.3: Model Service Class Diagram")

    # ModelService
    _box(ax, (5, 45), 30, 45, "", color="white", edge=C["backend"],
         edge_width=2, corner=0.4)
    ax.text(20, 84, "ModelService", ha="center", fontsize=12,
            fontweight="bold", color=C["backend"])
    ax.plot([6, 34], [82, 82], color=C["backend"], lw=1)
    fields = [
        "- stage1: Stage1LightGBM",
        "- calibrator: IsotonicCalibrator",
        "- sparkov_model: Stage1LightGBM",
        "- feature_columns: list[str]",
        "- sparkov_feature_columns: list[str]",
        "- model_version: str",
        "- sparkov_model_version: str",
    ]
    for i, f in enumerate(fields):
        ax.text(6.5, 79 - i * 3, f, fontsize=8, color=C["text"], fontfamily="monospace")
    ax.plot([6, 34], [57, 57], color=C["backend"], lw=1)
    methods = [
        "+ load()", "+ warmup()",
        "+ score(X)", "+ shap(X, top_k)",
        "+ score_sparkov(X)", "+ shap_sparkov(X, top_k)",
    ]
    for i, m in enumerate(methods):
        ax.text(6.5, 54 - i * 1.5, m, fontsize=8, color=C["text"], fontfamily="monospace")

    # SparkovLookups
    _box(ax, (40, 60), 30, 30, "", color="white", edge=C["model"],
         edge_width=2, corner=0.4)
    ax.text(55, 85, "SparkovLookups", ha="center", fontsize=12,
            fontweight="bold", color=C["model"])
    ax.plot([41, 69], [83, 83], color=C["model"], lw=1)
    fields = [
        "- merchant_te: dict[str, float]",
        "- city_te: dict[str, float]",
        "- job_te: dict[str, float]",
        "- zip_te: dict[int, float]",
        "- global_target_mean: float",
    ]
    for i, f in enumerate(fields):
        ax.text(41.5, 80 - i * 2.7, f, fontsize=8, color=C["text"], fontfamily="monospace")

    # Stage1LightGBM
    _box(ax, (75, 60), 22, 30, "", color="white", edge=C["accent"],
         edge_width=2, corner=0.4)
    ax.text(86, 85, "Stage1LightGBM", ha="center", fontsize=11,
            fontweight="bold", color=C["accent"])
    ax.plot([76, 96], [83, 83], color=C["accent"], lw=1)
    fields = [
        "- model: lgb.Booster",
        "- feature_names: list",
    ]
    for i, f in enumerate(fields):
        ax.text(76.5, 80 - i * 2.7, f, fontsize=8, color=C["text"], fontfamily="monospace")
    ax.plot([76, 96], [72, 72], color=C["accent"], lw=1)
    ax.text(76.5, 69, "+ predict_proba(X)", fontsize=8, color=C["text"],
            fontfamily="monospace")
    ax.text(76.5, 66, "+ load(path)", fontsize=8, color=C["text"], fontfamily="monospace")

    # IsotonicCalibrator
    _box(ax, (40, 35), 30, 20, "", color="white", edge=C["db"],
         edge_width=2, corner=0.4)
    ax.text(55, 50, "IsotonicCalibrator", ha="center", fontsize=11,
            fontweight="bold", color=C["db"])
    ax.plot([41, 69], [48, 48], color=C["db"], lw=1)
    ax.text(41.5, 44, "- iso: IsotonicRegression", fontsize=8, color=C["text"],
            fontfamily="monospace")
    ax.plot([41, 69], [42, 42], color=C["db"], lw=1)
    ax.text(41.5, 39, "+ transform(raw)  → calibrated", fontsize=8, color=C["text"],
            fontfamily="monospace")

    # Relations
    _arrow(ax, (35, 65), (40, 70), color=C["muted"], style="-|>", label="uses")
    _arrow(ax, (35, 55), (40, 47), color=C["muted"], style="-|>", label="uses")
    _arrow(ax, (70, 72), (75, 74), color=C["muted"], style="-|>", label="owns")

    # Singleton note
    ax.text(20, 40, "★ Singleton", ha="center", fontsize=10,
            color=C["accent"], fontweight="bold")
    ax.text(20, 37, "(loaded once at\nFastAPI startup)",
            ha="center", fontsize=8, color=C["muted"], style="italic")

    _save(fig, "05_model_service_class")


# ==================================================================
# 6. Feature Engineering Pipelines
# ==================================================================
def diag_06_feature_pipeline():
    fig, ax = plt.subplots(figsize=(12, 6.5))
    _setup_ax(ax, "Figure 7.4: Feature Engineering Pipelines (IEEE-CIS vs Sparkov)")

    # IEEE-CIS pipeline
    ax.text(25, 92, "IEEE-CIS Pipeline (390+ features)",
            ha="center", fontsize=11, fontweight="bold", color=C["accent"])

    ieee_steps = [
        ("Raw txn JSON", C["muted"]),
        ("Merge tables", C["frontend"]),
        ("Impute NaN", C["frontend"]),
        ("Label encode", C["backend"]),
        ("Target encode", C["backend"]),
        ("Time features", C["backend"]),
        ("Velocity (card1)", C["backend"]),
        ("Stage 1 LightGBM", C["model"]),
        ("Isotonic calibrator", C["db"]),
        ("Decision", C["accent"]),
    ]
    for i, (t, c) in enumerate(ieee_steps):
        y = 82 - i * 7.5
        _box(ax, (10, y), 30, 5, t, color=c, font_size=9, corner=0.3)
        if i < len(ieee_steps) - 1:
            _arrow(ax, (25, y), (25, y - 2.5), color=C["muted"], lw=1.2)

    # Sparkov pipeline
    ax.text(75, 92, "Sparkov Pipeline (30 features)",
            ha="center", fontsize=11, fontweight="bold", color=C["merchant"])

    sparkov_steps = [
        ("Payment JSON", C["muted"]),
        ("Profile lookup (velocity, city)", C["frontend"]),
        ("Amount features (log, bucket)", C["backend"]),
        ("Temporal (hour, is_night)", C["backend"]),
        ("Geographic (haversine)", C["backend"]),
        ("Cached target encoders", C["model"]),
        ("Sparkov Stage 1 LightGBM", C["model"]),
        ("No calibrator — already calibrated", C["db"]),
        ("Decision", C["accent"]),
    ]
    for i, (t, c) in enumerate(sparkov_steps):
        y = 82 - i * 8.3
        _box(ax, (60, y), 30, 5, t, color=c, font_size=9, corner=0.3)
        if i < len(sparkov_steps) - 1:
            _arrow(ax, (75, y), (75, y - 3.3), color=C["muted"], lw=1.2)

    ax.text(50, 3, "Same 3-stage design applied to different feature spaces — methodology transfer proof",
            ha="center", fontsize=8.5, color=C["muted"], style="italic")

    _save(fig, "06_feature_pipeline")


# ==================================================================
# 7. Database ER Diagram
# ==================================================================
def diag_07_db_er_diagram():
    fig, ax = plt.subplots(figsize=(12, 8))
    _setup_ax(ax, "Figure 8.1: Database Schema (ER Diagram)")

    def entity(x, y, name, fields, color):
        h = 5 + len(fields) * 3
        _box(ax, (x, y), 25, h, "", color="white", edge=color,
             edge_width=2, corner=0.4)
        ax.text(x + 12.5, y + h - 2.5, name, ha="center", fontsize=11,
                fontweight="bold", color=color)
        ax.plot([x + 0.5, x + 24.5], [y + h - 5, y + h - 5], color=color, lw=1)
        for i, f in enumerate(fields):
            ax.text(x + 1, y + h - 8 - i * 3, f, fontsize=8, color=C["text"],
                    fontfamily="monospace")

    # Company
    entity(5, 70, "companies",
           ["PK id",
            "name (unique)",
            "industry, size",
            "use_case, logo_url",
            "is_active",
            "created_at, updated_at"], C["accent"])

    # User
    entity(38, 70, "users",
           ["PK id",
            "email (unique)",
            "hashed_password",
            "full_name, role",
            "is_active",
            "FK company_id → companies"], C["user"])

    # Transaction
    entity(5, 25, "transactions",
           ["PK id",
            "external_id (unique)",
            "amount, product_cd, ...",
            "raw_features (JSON)",
            "is_fraud (nullable label)",
            "FK company_id → companies"], C["backend"])

    # Prediction
    entity(38, 25, "predictions",
           ["PK id",
            "FK transaction_id → txns",
            "raw_score, calibrated_score",
            "decision",
            "shap_top (JSON)",
            "model_version, latency_ms",
            "FK company_id → companies"], C["model"])

    # Feedback
    entity(70, 25, "feedback",
           ["PK id",
            "FK prediction_id → preds (unique)",
            "FK analyst_id → users",
            "verdict",
            "notes"], C["db"])

    # Relations
    _arrow(ax, (30, 76), (38, 76), color=C["muted"], style="-|>",
           label="1 : N", label_offset=(0, 2))
    _arrow(ax, (30, 71), (17, 55), color=C["muted"], style="-|>",
           label="1 : N",  curve=-0.2)
    _arrow(ax, (30, 71), (50, 55), color=C["muted"], style="-|>",
           label="1 : N", curve=0.2)
    _arrow(ax, (30, 40), (38, 40), color=C["muted"], style="-|>",
           label="1 : N", label_offset=(0, 2))
    _arrow(ax, (63, 40), (70, 40), color=C["muted"], style="-|>",
           label="1 : 1", label_offset=(0, 2))
    _arrow(ax, (50, 72), (82, 45), color=C["muted"], style="-|>", curve=0.3,
           label="analyst_id")

    ax.text(50, 5, "★ Every transaction and prediction carries a company_id — the multi-tenancy boundary is at the schema level",
            ha="center", fontsize=9, color=C["accent"], fontweight="bold", style="italic")

    _save(fig, "07_db_er_diagram")


# ==================================================================
# 8. Multi-Tenancy Enforcement
# ==================================================================
def diag_08_multi_tenancy():
    fig, ax = plt.subplots(figsize=(12, 7))
    _setup_ax(ax, "Figure 8.2: Multi-Tenancy Enforcement — Company_id Boundary")

    # 3 companies (columns)
    companies = [
        (10, "Zomato", C["accent"]),
        (40, "Swiggy", C["frontend"]),
        (70, "BigBasket", C["db"]),
    ]

    for x, name, color in companies:
        # Company header
        _box(ax, (x, 82), 20, 8, name, color=color, font_size=11, corner=0.5)

        # Admin user
        _box(ax, (x, 70), 20, 8, f"{name} Admin",
             color="white", edge=color, edge_width=2, corner=0.5,
             text_color=color)

        # Data blob
        _box(ax, (x, 40), 20, 25, "", color="white", edge=color,
             edge_width=2, corner=0.5)
        ax.text(x + 10, 61, "Transactions", ha="center", fontsize=10,
                color=color, fontweight="bold")
        ax.text(x + 10, 58, "Predictions", ha="center", fontsize=10,
                color=color, fontweight="bold")
        ax.text(x + 10, 50, f"company_id = {companies.index((x, name, color)) + 1}",
                ha="center", fontsize=9, color=C["text"], fontfamily="monospace",
                fontweight="bold")
        ax.text(x + 10, 46, "(all rows tagged)", ha="center", fontsize=8,
                color=C["muted"], style="italic")

        # Login arrow
        _arrow(ax, (x + 10, 70), (x + 10, 65), color=color, lw=1.2)

    # Barriers between companies (walls)
    for wall_x in [32.5, 62.5]:
        ax.plot([wall_x, wall_x], [30, 78], color=C["danger"], lw=2, linestyle="--")

    # Legend
    ax.text(50, 25, "Isolation enforced at THREE layers:",
            ha="center", fontsize=10, color=C["text"], fontweight="bold")

    layers = [
        "1. DB schema — company_id FK on every tenant-scoped row",
        "2. Route dependency — require_company() gates every endpoint",
        "3. Query filter — every ORM query joins/filters on current_user.company_id",
    ]
    for i, txt in enumerate(layers):
        ax.text(50, 20 - i * 3.5, txt, ha="center", fontsize=9, color=C["text"])

    ax.text(50, 4, "★ Cross-tenant data access is not just prevented — it is impossible by construction",
            ha="center", fontsize=9, color=C["danger"], fontweight="bold")

    _save(fig, "08_multi_tenancy")


# ==================================================================
# 9. Next.js Route Map
# ==================================================================
def diag_09_nextjs_routes():
    fig, ax = plt.subplots(figsize=(12, 8))
    _setup_ax(ax, "Figure 9.1: Next.js App Router — Route Map")

    # Public routes
    ax.text(25, 94, "Public Routes (no auth)", ha="center",
            fontsize=11, fontweight="bold", color=C["merchant"])
    public = [
        ("/", "Landing page"),
        ("/features", "Feature marketing"),
        ("/about, /pricing, /contact", "Static marketing"),
        ("/login", "Sign in form"),
        ("/register", "Company + admin signup"),
        ("/checkout", "TechMart demo checkout"),
        ("/merchants/zomato", "Zomato branded checkout"),
        ("/merchants/swiggy", "Swiggy branded checkout"),
        ("/merchants/bigbasket", "BigBasket branded checkout"),
    ]
    for i, (path, desc) in enumerate(public):
        y = 87 - i * 5
        _box(ax, (5, y), 20, 3.8, path, color=C["merchant"], font_size=8, corner=0.3)
        ax.text(26, y + 1.9, desc, fontsize=9, color=C["text"], va="center")

    # Auth routes
    ax.text(75, 94, "Authenticated Routes (analyst / admin)", ha="center",
            fontsize=11, fontweight="bold", color=C["backend"])
    auth = [
        ("/dashboard", "KPIs + risky txn table"),
        ("/transactions", "Filterable txn list"),
        ("/transactions/[id]", "Detail + SHAP waterfall"),
        ("/predict", "Live Predict (Sparkov + IEEE-CIS)"),
        ("/analytics", "Time-series charts (monthly/yearly)"),
        ("/profile", "Update name, password, company"),
    ]
    for i, (path, desc) in enumerate(auth):
        y = 87 - i * 5
        _box(ax, (55, y), 20, 3.8, path, color=C["backend"], font_size=8, corner=0.3)
        ax.text(76, y + 1.9, desc, fontsize=9, color=C["text"], va="center")

    ax.text(50, 5, "Public shell (PublicShell.tsx) wraps marketing + checkout · App shell (AppShell.tsx) wraps authenticated pages",
            ha="center", fontsize=8.5, color=C["muted"], style="italic")

    _save(fig, "09_nextjs_routes")


# ==================================================================
# 10. Component Hierarchy
# ==================================================================
def diag_10_component_hierarchy():
    fig, ax = plt.subplots(figsize=(12, 8))
    _setup_ax(ax, "Figure 9.2: Frontend Component Hierarchy")

    # Root
    _box(ax, (40, 87), 20, 7, "RootLayout", color=C["accent"], corner=0.4)

    # Two shells
    _box(ax, (10, 72), 25, 7, "PublicShell", color=C["merchant"], corner=0.4,
         subtitle="marketing + checkout")
    _box(ax, (65, 72), 25, 7, "AppShell", color=C["backend"], corner=0.4,
         subtitle="analyst UI + sidebar")

    _arrow(ax, (48, 87), (22, 79), color=C["muted"])
    _arrow(ax, (52, 87), (78, 79), color=C["muted"])

    # PublicShell children
    public_children = [
        (2, 60, "LandingPage"),
        (14, 60, "MerchantCheckout"),
        (26, 60, "Splash"),
    ]
    for x, y, name in public_children:
        _box(ax, (x, y), 10, 5, name, color=C["merchant"], font_size=8, corner=0.3)
        _arrow(ax, (22, 72), (x + 5, y + 5), color=C["muted"], lw=1)

    # MerchantCheckout children
    _box(ax, (14, 50), 10, 5, "ResultScreen", color=C["merchant"], font_size=8, corner=0.3)
    _arrow(ax, (19, 60), (19, 55), color=C["muted"], lw=1)

    # AppShell children
    app_children = [
        (55, 60, "Sidebar"),
        (66, 60, "NotificationPanel"),
        (78, 60, "Dashboard"),
        (89, 60, "Transactions"),
    ]
    for x, y, name in app_children:
        _box(ax, (x, y), 10, 5, name, color=C["backend"], font_size=8, corner=0.3)
        _arrow(ax, (78, 72), (x + 5, y + 5), color=C["muted"], lw=1)

    # 2nd row app
    app2 = [
        (55, 48, "Predict"),
        (66, 48, "Analytics"),
        (78, 48, "Profile"),
        (89, 48, "TxnDetail"),
    ]
    for x, y, name in app2:
        _box(ax, (x, y), 10, 5, name, color=C["backend"], font_size=8, corner=0.3)
        _arrow(ax, (78, 72), (x + 5, y + 5), color=C["muted"], lw=1)

    # Shared components box
    _box(ax, (10, 20), 80, 15, "", color="white", edge=C["muted"],
         edge_width=1.5, corner=0.6)
    ax.text(50, 32, "Shared components (used across pages)",
            ha="center", fontsize=10, fontweight="bold", color=C["muted"])
    shared = [
        "Tooltip · FloatingTooltip · Splash",
        "ThemeInit (dark/light + sidebar collapsed persistence)",
        "SparkovPredictMode · ShapWaterfall · MerchantCheckout",
    ]
    for i, s in enumerate(shared):
        ax.text(50, 28 - i * 3, s, ha="center", fontsize=9, color=C["text"],
                fontfamily="monospace")

    ax.text(50, 12, "Layouts share auth guard state — AppShell redirects to /login if isAuthenticated()==false",
            ha="center", fontsize=8.5, color=C["muted"], style="italic")

    _save(fig, "10_component_hierarchy")


# ==================================================================
# 11. Merchant Portal Architecture
# ==================================================================
def diag_11_merchant_portal():
    fig, ax = plt.subplots(figsize=(12, 7))
    _setup_ax(ax, "Figure 10.1: Multi-Merchant Portal Architecture (Fan-in)")

    # 4 merchant portals
    merchants = [
        (5, "TechMart", C["accent"], "shopping_net"),
        (25, "Zomato", "#E23744", "misc_net"),
        (45, "Swiggy", "#FC8019", "misc_net"),
        (65, "BigBasket", "#84BE39", "grocery_pos"),
    ]

    for x, name, color, cat in merchants:
        _box(ax, (x, 75), 18, 12, name, color=color, font_size=11,
             corner=0.5, subtitle=f"category={cat}")

    # Central API
    _box(ax, (33, 42), 25, 15, "POST /api/checkout",
         color=C["backend"], font_size=12,
         subtitle="FastAPI + Sparkov model", corner=0.6)

    # Arrows converging
    for x, name, color, cat in merchants:
        _arrow(ax, (x + 9, 75), (45, 57), color=color, lw=1.5,
               label=f"company_slug=\n{name.lower()}",
               label_offset=(0, 3))

    # DB
    _box(ax, (33, 15), 25, 15, "PostgreSQL",
         color=C["db"], font_size=11,
         subtitle="Transactions tagged with correct company_id", corner=0.6)

    _arrow(ax, (45, 42), (45, 30), color=C["muted"], lw=1.6,
           label="INSERT with company_id")

    # Analyst dashboards on the right
    _box(ax, (85, 60), 12, 30, "", color="white", edge=C["muted"],
         edge_width=1.5, corner=0.4)
    ax.text(91, 87, "Admin Logins", ha="center", fontsize=10, fontweight="bold",
            color=C["muted"])
    for i, (_, name, color, _) in enumerate(merchants):
        y = 82 - i * 5
        ax.text(91, y, f"admin@{name.lower()}.demo",
                ha="center", fontsize=8, color=color, fontfamily="monospace")

    _arrow(ax, (58, 22), (85, 65), color=C["muted"], curve=-0.3,
           label="SELECT WHERE company_id = current_user.company_id")

    _save(fig, "11_merchant_portal")


# ==================================================================
# 12. Multi-Tenant Data Isolation
# ==================================================================
def diag_12_multi_tenant_isolation():
    fig, ax = plt.subplots(figsize=(12, 7))
    _setup_ax(ax, "Figure 10.2: Multi-Tenant Data Isolation in Action")

    # Two admins side by side
    _box(ax, (5, 78), 30, 10, "Zomato Admin",
         color="#E23744", subtitle="Logged in as admin@zomato.demo", corner=0.5)
    _box(ax, (65, 78), 30, 10, "Swiggy Admin",
         color="#FC8019", subtitle="Logged in as admin@swiggy.demo", corner=0.5)

    # Same DB
    _box(ax, (20, 40), 60, 20, "", color="white", edge=C["muted"],
         edge_width=2, corner=0.6)
    ax.text(50, 55, "Shared Database", ha="center", fontsize=11,
            fontweight="bold", color=C["muted"])

    # Data rows
    rows = [
        (25, 48, "Zomato biryani txn", "#E23744"),
        (25, 44, "Zomato wedding txn", "#E23744"),
        (52, 48, "Swiggy conference txn", "#FC8019"),
        (52, 44, "Swiggy office lunch txn", "#FC8019"),
        (38, 42, "(interleaved)", C["muted"]),
    ]
    for x, y, txt, color in rows:
        ax.text(x, y, txt, fontsize=8.5, color=color, fontweight="bold",
                fontfamily="monospace")

    # Queries with filters
    _arrow(ax, (20, 78), (30, 60), color="#E23744", lw=1.6,
           label="WHERE company_id=Zomato")
    _arrow(ax, (80, 78), (70, 60), color="#FC8019", lw=1.6,
           label="WHERE company_id=Swiggy")

    # Result panels
    _box(ax, (5, 15), 30, 20, "", color="white", edge="#E23744",
         edge_width=2, corner=0.5)
    ax.text(20, 32, "Zomato Dashboard", ha="center", fontsize=10,
            fontweight="bold", color="#E23744")
    ax.text(20, 27, "✓ Zomato biryani txn", ha="center", fontsize=8, color=C["text"])
    ax.text(20, 24, "✓ Zomato wedding txn", ha="center", fontsize=8, color=C["text"])
    ax.text(20, 20, "✗ (no Swiggy data visible)", ha="center", fontsize=8, color=C["muted"])

    _box(ax, (65, 15), 30, 20, "", color="white", edge="#FC8019",
         edge_width=2, corner=0.5)
    ax.text(80, 32, "Swiggy Dashboard", ha="center", fontsize=10,
            fontweight="bold", color="#FC8019")
    ax.text(80, 27, "✓ Swiggy conference txn", ha="center", fontsize=8, color=C["text"])
    ax.text(80, 24, "✓ Swiggy office lunch txn", ha="center", fontsize=8, color=C["text"])
    ax.text(80, 20, "✗ (no Zomato data visible)", ha="center", fontsize=8, color=C["muted"])

    _arrow(ax, (30, 40), (20, 35), color="#E23744", lw=1.6)
    _arrow(ax, (70, 40), (80, 35), color="#FC8019", lw=1.6)

    ax.text(50, 5, "Same DB, same code — different company_id in JWT determines what each admin sees",
            ha="center", fontsize=9, color=C["muted"], fontweight="bold", style="italic")

    _save(fig, "12_multi_tenant_isolation")


# ==================================================================
# 13. Payment Authorization Sequence Diagram
# ==================================================================
def diag_13_seq_payment():
    fig, ax = plt.subplots(figsize=(13, 8))
    _setup_ax(ax, "Figure 11.1: Payment Authorization Flow (Sequence)")

    # Actors at top
    actors = [
        (10, "Customer", C["user"]),
        (28, "Merchant\nPortal", C["merchant"]),
        (46, "FastAPI\n/api/checkout", C["backend"]),
        (64, "ModelService\n+ SparkovLookups", C["model"]),
        (82, "PostgreSQL", C["db"]),
    ]
    lifelines = []
    for x, name, color in actors:
        _box(ax, (x - 6, 88), 12, 8, name, color=color, font_size=9, corner=0.4)
        # Lifeline
        ax.plot([x, x], [12, 88], color=C["muted"], lw=0.6, linestyle=":")
        lifelines.append(x)

    # Messages
    messages = [
        (85, 10, 28, "Add items to cart", C["user"]),
        (79, 10, 28, "Click Pay ₹8,500", C["user"]),
        (71, 28, 46, "POST /api/checkout {card, amount, ...}", C["merchant"]),
        (63, 46, 64, "score_sparkov(features)", C["backend"]),
        (57, 64, 64, "  enrich profile + haversine + target_enc", C["model"], "self"),
        (51, 64, 46, "return (score=0.06, decision=block)", C["model"]),
        (45, 46, 82, "INSERT transactions, predictions", C["backend"]),
        (39, 82, 46, "OK", C["db"]),
        (33, 46, 28, "{status: 'declined', reason: ...}", C["backend"]),
        (27, 28, 10, "Show 'Payment Declined' screen", C["merchant"]),
    ]

    for msg in messages:
        y, fx, tx, label = msg[0], msg[1], msg[2], msg[3]
        color = msg[4]
        if len(msg) > 5 and msg[5] == "self":
            # self-message
            ax.annotate("", xy=(fx + 4, y - 1.5), xytext=(fx, y),
                        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3))
            ax.text(fx + 5, y - 0.5, label, fontsize=8, color=color, va="center")
        else:
            style = "-|>" if fx < tx else "-|>"
            _arrow(ax, (fx, y), (tx, y), color=color, lw=1.3)
            mx = (fx + tx) / 2
            ax.text(mx, y + 1.2, label, ha="center", fontsize=8, color=color)

    ax.text(46, 4, "Total end-to-end latency typically < 200 ms (model inference ~80 ms, DB write ~50 ms)",
            ha="center", fontsize=9, color=C["muted"], style="italic")

    _save(fig, "13_seq_payment")


# ==================================================================
# 14. Analyst Review Sequence
# ==================================================================
def diag_14_seq_analyst_review():
    fig, ax = plt.subplots(figsize=(13, 8))
    _setup_ax(ax, "Figure 11.2: Analyst Review Flow (Sequence)")

    actors = [
        (10, "Analyst", C["user"]),
        (30, "Next.js\nDashboard", C["frontend"]),
        (50, "FastAPI\nendpoints", C["backend"]),
        (72, "PostgreSQL", C["db"]),
        (91, "ModelService", C["model"]),
    ]
    for x, name, color in actors:
        _box(ax, (x - 6, 88), 12, 8, name, color=color, font_size=9, corner=0.4)
        ax.plot([x, x], [12, 88], color=C["muted"], lw=0.6, linestyle=":")

    messages = [
        (85, 10, 30, "Log in → JWT", C["user"]),
        (79, 30, 50, "GET /api/metrics/summary", C["frontend"]),
        (73, 50, 72, "SELECT ... WHERE company_id = ?", C["backend"]),
        (67, 72, 50, "counts + top_risky[]", C["db"]),
        (61, 50, 30, "DashboardKPIs JSON", C["backend"]),
        (55, 10, 30, "Click a flagged transaction row", C["user"]),
        (49, 30, 50, "GET /api/transactions/{id}", C["frontend"]),
        (43, 50, 72, "SELECT txn JOIN predictions", C["backend"]),
        (37, 72, 30, "txn + prediction + SHAP top-5", C["db"]),
        (31, 30, 10, "Render SHAP waterfall + risk score", C["frontend"]),
        (25, 10, 30, "(future) Submit verdict via /feedback", C["user"]),
    ]

    for msg in messages:
        y, fx, tx, label, color = msg
        _arrow(ax, (fx, y), (tx, y), color=color, lw=1.3)
        mx = (fx + tx) / 2
        ax.text(mx, y + 1.2, label, ha="center", fontsize=8, color=color)

    ax.text(50, 4, "Analyst never runs the model — they interpret its output, add labels via feedback for future retraining",
            ha="center", fontsize=9, color=C["muted"], style="italic")

    _save(fig, "14_seq_analyst_review")


# ==================================================================
# 15. Live Predict Blind Test Sequence
# ==================================================================
def diag_15_seq_live_predict():
    fig, ax = plt.subplots(figsize=(13, 8))
    _setup_ax(ax, "Figure 11.3: Live Predict Blind Test Sequence")

    actors = [
        (10, "User\n(Mentor)", C["user"]),
        (30, "Live Predict\nPage", C["frontend"]),
        (52, "FastAPI\n/api/predict/sparkov", C["backend"]),
        (75, "ModelService\n.score_sparkov", C["model"]),
        (92, "localStorage", C["db"]),
    ]
    for x, name, color in actors:
        _box(ax, (x - 6, 88), 12, 8, name, color=color, font_size=9, corner=0.4)
        ax.plot([x, x], [12, 88], color=C["muted"], lw=0.6, linestyle=":")

    messages = [
        (85, 10, 30, "Click 'Load Random Transaction'", C["user"]),
        (79, 30, 52, "GET /random", C["frontend"]),
        (73, 52, 30, "sample row (with ground truth)", C["backend"]),
        (67, 30, 30, "Fill form, HIDE is_fraud label", C["frontend"], "self"),
        (61, 10, 30, "Study inputs, form hypothesis", C["user"]),
        (55, 10, 30, "Click 'Score Transaction'", C["user"]),
        (49, 30, 52, "POST /api/predict/sparkov", C["frontend"]),
        (43, 52, 75, "score_sparkov + shap_sparkov", C["backend"]),
        (37, 75, 52, "raw_score, decision, shap_top", C["model"]),
        (31, 52, 30, "PredictionResponse", C["backend"]),
        (25, 10, 30, "Click 'Reveal ground truth'", C["user"]),
        (19, 30, 92, "Update accuracy stats", C["frontend"]),
    ]

    for msg in messages:
        y, fx, tx, label = msg[0], msg[1], msg[2], msg[3]
        color = msg[4]
        if len(msg) > 5 and msg[5] == "self":
            ax.annotate("", xy=(fx + 4, y - 1.5), xytext=(fx, y),
                        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3))
            ax.text(fx + 5, y - 0.5, label, fontsize=8, color=color, va="center")
        else:
            _arrow(ax, (fx, y), (tx, y), color=color, lw=1.3)
            mx = (fx + tx) / 2
            ax.text(mx, y + 1.2, label, ha="center", fontsize=8, color=color)

    ax.text(50, 4, "Ground truth is stored in state but not surfaced until Reveal — prevents 'told you the answer' credibility issue",
            ha="center", fontsize=9, color=C["muted"], style="italic")

    _save(fig, "15_seq_live_predict")


# ==================================================================
# 16. Auth (Register + Login) Sequence
# ==================================================================
def diag_16_seq_auth():
    fig, ax = plt.subplots(figsize=(13, 8))
    _setup_ax(ax, "Figure 11.4: Authentication Flow (Register + Login)")

    actors = [
        (10, "Browser", C["user"]),
        (32, "Next.js\nregister/login", C["frontend"]),
        (54, "FastAPI\n/auth/*", C["backend"]),
        (76, "bcrypt +\nJWT signer", C["model"]),
        (92, "PostgreSQL", C["db"]),
    ]
    for x, name, color in actors:
        _box(ax, (x - 6, 88), 12, 8, name, color=color, font_size=9, corner=0.4)
        ax.plot([x, x], [12, 88], color=C["muted"], lw=0.6, linestyle=":")

    # Register subflow
    ax.text(50, 82, "── REGISTER ──", ha="center", fontsize=10,
            fontweight="bold", color=C["accent"])
    reg = [
        (78, 10, 32, "Submit company + email + password"),
        (72, 32, 54, "POST /auth/register"),
        (66, 54, 76, "bcrypt.hash(password, rounds=12)"),
        (60, 54, 92, "INSERT Company, User(role='admin')"),
        (54, 92, 32, "201 Created"),
    ]
    for y, fx, tx, label in reg:
        _arrow(ax, (fx, y), (tx, y), color=C["accent"], lw=1.3)
        mx = (fx + tx) / 2
        ax.text(mx, y + 1.2, label, ha="center", fontsize=8, color=C["accent"])

    # Login subflow
    ax.text(50, 47, "── LOGIN ──", ha="center", fontsize=10,
            fontweight="bold", color=C["backend"])
    login = [
        (43, 10, 32, "Enter email + password"),
        (37, 32, 54, "POST /auth/login"),
        (31, 54, 92, "SELECT users WHERE email=?"),
        (25, 92, 54, "row"),
        (19, 54, 76, "bcrypt.verify + jwt.encode(sub, company_id)"),
        (13, 54, 32, "{access_token, user}"),
    ]
    for y, fx, tx, label in login:
        _arrow(ax, (fx, y), (tx, y), color=C["backend"], lw=1.3)
        mx = (fx + tx) / 2
        ax.text(mx, y + 1.2, label, ha="center", fontsize=8, color=C["backend"])

    ax.text(50, 4, "Public /auth/register only creates 'analyst' role. Admin role requires CLI seed_companies.py or /auth/register/first-user",
            ha="center", fontsize=8.5, color=C["muted"], style="italic")

    _save(fig, "16_seq_auth")


# ==================================================================
# 17. Deployment Topology
# ==================================================================
def diag_17_deployment():
    fig, ax = plt.subplots(figsize=(12, 7.5))
    _setup_ax(ax, "Figure 12.1: Deployment Topology")

    # HF Space cloud
    hf_box = FancyBboxPatch((5, 30), 55, 55,
                            boxstyle="round,pad=0.02,rounding_size=2",
                            facecolor="#FFF8E7",
                            edgecolor=C["frontend"],
                            linewidth=2, linestyle="--")
    ax.add_patch(hf_box)
    ax.text(32, 82, "Hugging Face Space", ha="center",
            fontsize=12, fontweight="bold", color=C["frontend"])

    # Docker container inside HF
    docker = FancyBboxPatch((10, 35), 45, 42,
                            boxstyle="round,pad=0.02,rounding_size=1",
                            facecolor="white",
                            edgecolor=C["backend"], linewidth=1.8)
    ax.add_patch(docker)
    ax.text(32, 74, "Docker container (python:3.11-slim)", ha="center",
            fontsize=10, fontweight="bold", color=C["backend"])

    _box(ax, (14, 62), 15, 8, "uvicorn", color=C["backend"], font_size=9, corner=0.3)
    _box(ax, (33, 62), 18, 8, "FastAPI app", color=C["backend"], font_size=9, corner=0.3)
    _box(ax, (14, 51), 15, 8, "Next.js\nstatic", color=C["frontend"], font_size=9, corner=0.3)
    _box(ax, (33, 51), 18, 8, "Serves /* from ./frontend_dist",
         color=C["frontend"], font_size=8, corner=0.3)
    _box(ax, (14, 40), 15, 8, "LightGBM\n+ Sparkov", color=C["model"], font_size=9, corner=0.3)
    _box(ax, (33, 40), 18, 8, "models/*.pkl (Git LFS)",
         color=C["model"], font_size=8, corner=0.3)

    # Render Postgres
    render_box = FancyBboxPatch((70, 40), 25, 30,
                                boxstyle="round,pad=0.02,rounding_size=1.5",
                                facecolor="#ECFDF5",
                                edgecolor=C["db"], linewidth=2, linestyle="--")
    ax.add_patch(render_box)
    ax.text(82.5, 66, "Render.com", ha="center", fontsize=11,
            fontweight="bold", color=C["db"])

    _box(ax, (73, 46), 19, 15, "PostgreSQL 16",
         color=C["db"], font_size=10, subtitle="External URL (SSL)", corner=0.4)

    # User
    _box(ax, (30, 12), 40, 10, "User's Browser",
         color=C["user"], font_size=11, corner=0.5,
         subtitle="hits undebuggedbit-chimera-fd.hf.space")

    # Arrows
    _arrow(ax, (50, 22), (32, 35), color=C["accent"], lw=1.6,
           label="HTTPS", label_offset=(-3, 0))
    _arrow(ax, (55, 55), (70, 55), color=C["accent"], lw=1.6,
           label="TCP 5432\nSSL")

    # git flow at bottom
    ax.text(50, 5, "git push hf main  →  HF rebuilds Docker  →  models pulled via LFS  →  container restart  →  new version live in 5–8 min",
            ha="center", fontsize=9, color=C["muted"], style="italic")

    _save(fig, "17_deployment_topology")


# ==================================================================
# 18. Fraud Decision Cascade
# ==================================================================
def diag_18_decision_cascade():
    fig, ax = plt.subplots(figsize=(12, 6.5))
    _setup_ax(ax, "Figure 13.1: Fraud Decision Cascade (Thresholds)")

    # Two rows — one for each dataset
    # IEEE-CIS
    ax.text(50, 90, "IEEE-CIS Mode  (higher fraud rate, wider thresholds)",
            ha="center", fontsize=11, fontweight="bold", color=C["accent"])

    # Bar
    ax.add_patch(Rectangle((5, 72), 90, 5, facecolor=C["success"]))
    ax.add_patch(Rectangle((5 + 90 * 0.05, 72), 90 * 0.90, 5, facecolor=C["warn"]))
    ax.add_patch(Rectangle((5 + 90 * 0.95, 72), 90 * 0.05, 5, facecolor=C["danger"]))
    ax.text(6, 74.5, "APPROVE", va="center", fontsize=8, color="white", fontweight="bold")
    ax.text(50, 74.5, "REVIEW (human)", va="center", ha="center",
            fontsize=9, color="white", fontweight="bold")
    ax.text(93, 74.5, "BLOCK", va="center", ha="right", fontsize=8, color="white",
            fontweight="bold")
    # thresholds
    for pos, label in [(0.05, "0.05"), (0.95, "0.95")]:
        x = 5 + 90 * pos
        ax.plot([x, x], [70, 79], color=C["text"], lw=1.2)
        ax.text(x, 68, label, ha="center", fontsize=9, color=C["text"], fontweight="bold")
    ax.text(5, 68, "0.00", ha="center", fontsize=9, color=C["muted"])
    ax.text(95, 68, "1.00", ha="center", fontsize=9, color=C["muted"])
    ax.text(5, 82, "calibrated probability (isotonic Stage 3)",
            fontsize=8.5, color=C["muted"], style="italic")

    # Sparkov
    ax.text(50, 55, "Sparkov Mode  (lower fraud rate 0.5%, narrower thresholds — tuned from val PR curve)",
            ha="center", fontsize=11, fontweight="bold", color=C["merchant"])

    ax.add_patch(Rectangle((5, 37), 90, 5, facecolor=C["success"]))
    ax.add_patch(Rectangle((5 + 90 * 0.005 * 20, 37), 90 * (0.05 - 0.005) * 20, 5,
                            facecolor=C["warn"]))
    ax.add_patch(Rectangle((5 + 90 * 0.05 * 20, 37), 90 * (1 - 0.05 * 20), 5,
                            facecolor=C["danger"]))
    ax.text(6, 39.5, "APPROVE", va="center", fontsize=8, color="white", fontweight="bold")
    ax.text(20, 39.5, "REVIEW", va="center", fontsize=8, color="white", fontweight="bold")
    ax.text(80, 39.5, "BLOCK", va="center", fontsize=8, color="white", fontweight="bold")
    for pos, label in [(0.005, "0.005"), (0.05, "0.05")]:
        # scaled x for Sparkov (0.05 max meaningful)
        x = 5 + 90 * pos * 20   # 20x scale to show narrow range
        if x > 95: x = 95
        ax.plot([x, x], [35, 44], color=C["text"], lw=1.2)
        ax.text(x, 33, label, ha="center", fontsize=9, color=C["text"], fontweight="bold")
    ax.text(5, 33, "0.000", ha="center", fontsize=8, color=C["muted"])
    ax.text(95, 33, "0.050+", ha="center", fontsize=8, color=C["muted"])
    ax.text(5, 47, "raw model probability (no calibrator — already well calibrated Brier=0.002)",
            fontsize=8.5, color=C["muted"], style="italic")

    # Notes
    ax.text(50, 20, "Same three-way decision, tuned per dataset:",
            ha="center", fontsize=10, fontweight="bold", color=C["text"])
    ax.text(50, 15, "• APPROVE: model confident non-fraud → transaction proceeds",
            ha="center", fontsize=9, color=C["text"])
    ax.text(50, 11, "• REVIEW: middle band → routed to human analyst queue",
            ha="center", fontsize=9, color=C["text"])
    ax.text(50, 7, "• BLOCK: model confident fraud → transaction auto-declined at gateway",
            ha="center", fontsize=9, color=C["text"])

    _save(fig, "18_decision_cascade")


# ==================================================================
# Main
# ==================================================================
def main():
    print(f"Generating diagrams to {OUT_DIR} ...")
    print()
    for fn in [
        diag_01_system_context,
        diag_02_container_diagram,
        diag_03_backend_layered,
        diag_04_backend_structure,
        diag_05_model_service_class,
        diag_06_feature_pipeline,
        diag_07_db_er_diagram,
        diag_08_multi_tenancy,
        diag_09_nextjs_routes,
        diag_10_component_hierarchy,
        diag_11_merchant_portal,
        diag_12_multi_tenant_isolation,
        diag_13_seq_payment,
        diag_14_seq_analyst_review,
        diag_15_seq_live_predict,
        diag_16_seq_auth,
        diag_17_deployment,
        diag_18_decision_cascade,
    ]:
        try:
            fn()
        except Exception as e:
            print(f"  ✗ {fn.__name__} FAILED: {e}")
    print()
    print(f"Done. Files in {OUT_DIR}")


if __name__ == "__main__":
    main()
