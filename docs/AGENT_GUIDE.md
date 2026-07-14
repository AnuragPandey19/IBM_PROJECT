# CHIMERA-FD · Test Case Agent — Team Guide

> **Audience**: Team members (Anurag, Pankaj, Gurnoor, Sanvi) who will
> run their own autonomous test case generator to author 50-100 test
> cases each.

## What this replaces

The previous plan was: "copy prompt into ChatGPT, paste output into
JSONL". That's slow and requires manual quality control on every batch.

The new plan is: **each teammate runs an agentic script** that does the
full loop autonomously:

1. Reads a config file with your name and target counts per typology.
2. Calls an LLM in a loop, asking for cases targeting the typologies
   that are still under-covered.
3. Validates the schema of every generated case.
4. Deduplicates against what's already in your output file.
5. **Optionally** live-validates each case against the backend to
   confirm the payload is well-formed.
6. Writes the accepted cases to `tests/authored/<yourname>.jsonl`.
7. Repeats until every typology target is met.

You run one command, walk away for 10 minutes, come back to 50-100
validated test cases.

## Prerequisites

### 1. Install extra dependencies

```bash
pip install -r requirements-agent.txt
```

This installs the LLM client libraries (OpenAI, Anthropic, Google
Gemini) plus pyyaml for the config file. Each provider is optional —
you only need the SDK for the LLM you plan to use.

### 2. Get an API key (choose one)

| Provider | Where to get a key | Free tier |
|---|---|---|
| **OpenAI** | https://platform.openai.com/api-keys | No; ~$0.30 for 100 cases with GPT-4o-mini |
| **Anthropic (Claude)** | https://console.anthropic.com/settings/keys | Very small free tier |
| **Google Gemini** | https://aistudio.google.com/apikey | **Yes** — generous free tier, good default |
| **Groq** | https://console.groq.com/keys | **Yes** — free, very fast |
| **Ollama** (local) | https://ollama.com — run models on your laptop | Free forever, no key needed |

**Recommended for our team**: **Google Gemini** — free, high quality,
generous quota.

### 3. Set your key as an env var

**Windows (PowerShell)**:
```powershell
$env:GEMINI_API_KEY = "your-key-here"      # for Gemini
# or
$env:OPENAI_API_KEY = "your-key-here"      # for OpenAI
# or
$env:ANTHROPIC_API_KEY = "your-key-here"   # for Anthropic
```

**Linux/macOS**:
```bash
export GEMINI_API_KEY="your-key-here"
```

**Or**: put the keys in a `.env` file at the project root (gitignored).

## Configuration

Copy `scripts/agent_config.example.yaml` to `scripts/agent_config.<yourname>.yaml`
and edit it:

```yaml
# Your name — used to name the output file (tests/authored/anurag.jsonl)
author: anurag

# Which LLM to use
provider: gemini            # openai | anthropic | gemini | groq | ollama
model: gemini-2.5-flash     # e.g. gpt-4o-mini, claude-3-5-sonnet, gemini-2.5-flash

# How many test cases per typology to target
target_counts:
  # Fraud typologies
  late_night_bulk_fraud: 8
  card_testing: 5
  cross_category_fraud: 4
  velocity_spike: 5
  weekend_spike: 3
  # Legit typologies
  routine_grocery: 8
  corporate_lunch: 5
  wedding_order: 5
  late_night_hostel: 4      # edge cases — expect model may over-block
  senior_routine: 4
  fuel_purchase: 3
  high_value_regular: 3
  # Total = 57 cases

# Batch size — how many cases the LLM generates per iteration
batch_size: 10

# Max iterations before giving up (safety valve — usually finishes in ~10)
max_iterations: 20

# If true, POST each case to /api/checkout before accepting it — verifies
# the payload is well-formed. Slower but higher-quality.
validate_live: true
backend_url: http://localhost:8000
```

## Running the agent

```bash
python scripts/test_case_agent.py --config scripts/agent_config.anurag.yaml
```

You'll see live progress:

```
── CHIMERA-FD test case agent ──
Author        : anurag
Provider      : gemini (gemini-2.5-flash)
Target        : 57 cases across 12 typologies
Existing file : tests/authored/anurag.jsonl (0 cases)

[iter 1] LLM → 10 cases → 8 valid schema → 8 unique → 8 saved
  Coverage: late_night_bulk_fraud 2/8 · card_testing 1/5 · ...
[iter 2] LLM → 10 cases → 10 valid schema → 9 unique → 9 saved
  Coverage: late_night_bulk_fraud 4/8 · card_testing 3/5 · ...
...
[iter 7] LLM → 10 cases → 10 valid schema → 5 unique → 5 saved
  Coverage: ALL TARGETS MET

Done. 58 cases saved to tests/authored/anurag.jsonl (took 4m 12s)
```

## Provider-specific notes

### Google Gemini (recommended)

```yaml
provider: gemini
model: gemini-2.5-flash
```

Free tier: 15 requests/minute, 1500 requests/day. Perfect for generating
a couple hundred cases.

### OpenAI

```yaml
provider: openai
model: gpt-4o-mini            # cheap and good enough
# or
model: gpt-4o                  # higher quality, ~10x more expensive
```

### Anthropic

```yaml
provider: anthropic
model: claude-3-5-sonnet-latest
# or
model: claude-3-5-haiku-latest   # cheaper and fast
```

### Groq (fastest, free)

```yaml
provider: groq
model: llama-3.3-70b-versatile
```

Free tier is generous. Uses OpenAI-compatible client under the hood.

### Ollama (local, free, offline)

```yaml
provider: ollama
model: llama3.1:8b
# assumes ollama is running locally on port 11434
```

Requires downloading a model first: `ollama pull llama3.1:8b`.
Smaller models produce lower-quality cases; use 8B+ for reasonable
output.

## What the agent does under the hood

Every iteration:

1. Looks at the current coverage vs targets and decides which
   typologies still need more cases.
2. Builds a **prompt** that explains the schema and asks the LLM for a
   batch focused on the under-covered typologies.
3. Parses the LLM output as JSONL. Rejects any line that isn't valid
   JSON or is missing required fields.
4. Dedupes against everything already saved (matches by
   `scenario + amount + typology + demo_profile` signature).
5. If `validate_live: true`, POSTs each candidate to the backend's
   `/api/checkout` endpoint. If the endpoint returns a 2xx, the case is
   real. Otherwise discarded.
6. Appends the survivors to `tests/authored/<yourname>.jsonl` and
   updates the coverage counters.

## Cost estimate

- 100 cases with **Gemini 2.5 Flash**: **free** (well under the daily
  quota).
- 100 cases with **GPT-4o-mini**: ~**$0.30**.
- 100 cases with **Claude 3.5 Haiku**: ~**$0.50**.
- 100 cases with **Ollama** (local): **free**, just eats laptop CPU.

## After the run

The output file `tests/authored/<yourname>.jsonl` is the final
deliverable. Commit it to the repo (`git add tests/authored/`).

Then evaluate everyone's cases against the model:

```bash
# Combines everyone's files in tests/authored/*.jsonl
python scripts/run_test_cases.py --dir tests/authored
```

The evaluation report lands in `tests/results/`.

## Troubleshooting

**Agent says "0 valid schema" every iteration**
- The LLM is outputting Markdown code fences around the JSONL.
  The prompt asks it not to, but some models ignore. Try a different
  model, or lower the temperature in the config.

**Live validation is rejecting most cases**
- Check that the backend is actually running (`curl http://localhost:8000/ping`).
- Look at the error field on the rejected cases in the log — often
  it's a merchant name the backend doesn't like, or a category
  outside the 14 valid ones.

**Agent never finishes**
- Check `max_iterations` isn't too low.
- Some typologies (like `weekend_spike`) are hard for the LLM to
  generate. Drop the target count for those.

**API key errors**
- Confirm the env var is actually set (`echo $GEMINI_API_KEY` on
  Linux/macOS, `echo $env:GEMINI_API_KEY` in PowerShell).
- Some providers need billing enabled even for free tier.

## When you're done

1. Commit your `tests/authored/<yourname>.jsonl`.
2. Run `python scripts/run_test_cases.py --dir tests/authored` to see
   how the model does across everyone's cases.
3. Look at the "cases the model got wrong" section of the report —
   those are the failure modes we need to fix (or document as a
   known limitation).
