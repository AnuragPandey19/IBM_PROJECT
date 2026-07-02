# Getting Started — For Your Teammates

If you're one of the four builders (Anurag, Pankaj, Gurnoor, Sanvi), read this on day 1. It gets you from a clean laptop to a running notebook in about 20 minutes.

---

## 1. Install what you need

**On Windows:**

- Python 3.10 or 3.11 from [python.org](https://python.org). During install, tick "Add Python to PATH."
- Git from [git-scm.com](https://git-scm.com).
- VS Code from [code.visualstudio.com](https://code.visualstudio.com) (or any editor).

Verify in PowerShell:

```powershell
python --version   # should print 3.10.x or 3.11.x
git --version
```

## 2. Clone or open the project

```powershell
cd C:\Users\undeb\Documents\PROJECTS\IBM
# If teammate already shared the CHIMERA-FD folder, cd into it directly:
cd CHIMERA-FD
```

## 3. Set up a virtual environment

Do this once. It keeps CHIMERA-FD dependencies isolated from your other Python projects.

```powershell
python -m venv .venv
.venv\Scripts\activate

# You should see (.venv) prefix on your prompt.

pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

The `-e .` command installs CHIMERA-FD in "editable" mode so `import chimera_fd` works from anywhere without reinstalling every time you change source.

## 4. Confirm the data path

Open `config/config.yaml`. Look at the `data.ieee_cis` section. By default it expects:

```
C:\Users\undeb\Documents\PROJECTS\IBM\ieee-fraud-detection\train_transaction.csv
C:\Users\undeb\Documents\PROJECTS\IBM\ieee-fraud-detection\train_identity.csv
```

If your CSVs are somewhere else, edit the paths in the YAML.

Sanity check:

```powershell
python -m chimera_fd.config
```

You should see the resolved absolute paths.

## 5. Run data prep

**Smoke test first** — 50k rows, finishes in ~30 seconds:

```powershell
python scripts\prepare_data.py --nrows 50000
```

If that works, do the full run:

```powershell
python scripts\prepare_data.py
```

Full run takes 2–5 minutes and produces:

```
data/processed/ieee_cis/train.parquet
data/processed/ieee_cis/val.parquet
data/processed/ieee_cis/test.parquet
```

## 6. Open the exploration notebook

```powershell
jupyter notebook notebooks\01_data_exploration.ipynb
```

Run every cell top to bottom. It walks you through class balance, missingness, transaction-amount distribution, temporal patterns, and category-vs-fraud signals. At the end there is a "questions for feature engineering" section — answer those before touching Week 2 code.

## 7. Run the tests

```powershell
pytest tests\ -v
```

Should pass in under 2 seconds. If it doesn't, tell the group in Slack before doing anything else.

---

## What to do next (by week)

**This week (23–29 June):** finish the EDA notebook. Each person writes 3 observations they'd like to convert into features next week.

**Next week (30 June – 6 July):** build feature engineering + Stage 1 LightGBM baseline. Anurag will drop a `02_feature_engineering.ipynb` scaffold on Monday.

---

## Slack channel discipline

- Post error tracebacks as screenshots + text (so we can grep them).
- Push code once a day at end-of-day, even if incomplete. Use a WIP branch.
- Do not commit CSVs or model files. Ever. The `.gitignore` blocks the obvious paths; if you notice a new one, add it.

---

## Useful commands cheat sheet

```powershell
# Activate the venv (do this every new terminal session)
.venv\Scripts\activate

# Update dependencies after someone changes requirements.txt
pip install -r requirements.txt

# Format + lint
ruff check src/ tests/
ruff format src/ tests/

# Run just the data tests
pytest tests\test_loader.py -v

# Peek at parquet sizes
Get-ChildItem data\processed -Recurse | Select Name, Length
```
