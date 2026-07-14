# CHIMERA-FD · Test Case Authoring Guide

> **Audience**: Team members writing test cases for the Sparkov fraud
> detection model. No ML background required.

## What we're doing

Instead of training on more data, we're going to **test** our existing
Sparkov model by generating a large set of transaction scenarios, each
with an **expected label** ("fraud" or "legit") that a human — or an
LLM — would clearly agree on.

Then we score every test case through our model and compare the model's
decision (`approve` / `review` / `block`) against the expected label.
The gap between the two is our **error surface** — it tells us where the
model is weak, where the thresholds are wrong, and what we need to add
rule-based safety nets for.

**Success looks like** producing ~200 well-labelled test cases across
the fraud typologies below.

---

## The transaction schema

Every test case is a single JSON object with a `payload` block that
matches the `POST /api/checkout` endpoint. You do **not** need to
supply every feature — the backend fills velocity, geo, and customer
history from a "customer profile" you select.

### Required payload fields

| Field | Type | Example | Notes |
|---|---|---|---|
| `card_number` | string | `"4532111122225678"` | Any 16-digit test card. Real cards are NEVER used. |
| `cardholder_name` | string | `"Sarah Johnson"` | Any name. |
| `amount` | float (USD) | `1899.00` | **USD dollars.** Not INR. The Indian merchant portals convert INR → USD before hitting the API. |
| `merchant_name` | string | `"TechMart Electronics"` | The merchant sending the checkout. |
| `merchant_category` | string | `"shopping_net"` | One of Sparkov's 14 categories (see list below). |
| `demo_profile` | string | `"new"` | One of: `established` \| `new` \| `high_spender` \| `senior` (see below). |
| `demo_hour_override` | int 0-23 | `3` | Hour of day the transaction happens. Optional; if omitted, uses server clock. |

### Optional fields

| Field | Type | Notes |
|---|---|---|
| `cust_email` | string | Any format. Not scored — used only for logs. |
| `card_expiry` | string | `"12/29"`. Not scored. |
| `card_cvv` | string | `"123"`. Not scored. |
| `company_slug` | string | `zomato` / `swiggy` / `bigbasket` / `techmart`. Just decides which merchant dashboard the transaction lands in. |

---

## The 14 Sparkov merchant categories

Pick one per test case. Each carries a different learned fraud rate.

| Category | Meaning | Typical use |
|---|---|---|
| `entertainment` | Movies, concerts, streaming | BookMyShow-style |
| `food_dining` | Restaurants, dining out | — |
| `gas_transport` | Fuel, cabs, transport | Ola/Uber-style |
| `grocery_net` | Online groceries | BigBasket-style |
| `grocery_pos` | In-store groceries | — |
| `health_fitness` | Gym, health apps | — |
| `home` | Home improvement | — |
| `kids_pets` | Kids' items, pet supplies | — |
| `misc_net` | Miscellaneous online | Zomato/Swiggy delivery |
| `misc_pos` | Miscellaneous in-store | — |
| `personal_care` | Salons, spas | — |
| `shopping_net` | Online shopping | TechMart-style electronics |
| `shopping_pos` | In-store shopping | — |
| `travel` | Flights, hotels | — |

**Rule of thumb**: `shopping_net`, `misc_net`, `travel` are more
online-fraud prone. `grocery_pos`, `food_dining` are lower-risk in the
learned distribution.

---

## The 4 customer profiles

Each `demo_profile` value expands, server-side, to a full customer
history. The profile drives velocity, geography, age, and gender
features that the model actually looks at.

| Profile | Age | Spend habit | Prior txns | Typical usage |
|---|---|---|---|---|
| `established` | 35 | Avg $55, boring pattern | 200 | Everyday reliable customer |
| `new` | 26 | Avg $0, zero history | 0 | Fresh card, no purchase pattern |
| `high_spender` | 48 | Avg $500, premium buyer | 300 | Consistent large purchases |
| `senior` | 67 | Avg $42, groceries/gas | 150 | Careful spender, small routine buys |

**Pick the profile that matches the story you're testing**. If your test
case is a "hostel student ordering ₹320 groceries at 3 AM", the closest
match is `senior` (small routine buys) — not `new` (which the model would
correctly treat as more suspicious).

---

## The 4 possible outcomes

The model returns one of four decisions:

| Decision | Meaning | Expected in test cases |
|---|---|---|
| `approved` | Model is confident the transaction is legit | Legit test cases |
| `declined` | Model is confident it's fraud, auto-blocked | Clear fraud test cases |
| `review` | Model is uncertain, sends to human queue | Ambiguous cases |
| — | (there's a small-amount safety net: any transaction under $12 that would have been blocked gets downgraded to `review` instead) | — |

---

## Expected labels for test cases

For each test case you write:

- `expected_label`: **must be** `"fraud"` or `"legit"` (this is the
  ground truth we're comparing against).
- `expected_severity`: one of `"clear"`, `"borderline"`, `"edge"` —
  helps us weight the test results.

**Clear cases** should be ones any human would agree on:
- "Brand new customer, $8000 electronics purchase at 3 AM" → clearly
  fraud.
- "Established senior, $42 grocery at 2 PM" → clearly legit.

**Borderline cases** are where the model can reasonably choose either:
- "Established regular, $1500 laptop at 10 AM" → probably legit but a
  fraud model routing it to review is also acceptable.

**Edge cases** are ones you *think* will surprise the model:
- "Senior grandma, $300 groceries at 3 AM" (hostel-student pattern) —
  we expect the model may over-block this and the safety net should
  catch it.

---

## Fraud typologies to cover

Aim for a **balanced spread**. Roughly 40% clear-fraud, 40% clear-legit,
20% borderline/edge.

### Fraud typologies

1. **Late-night bulk fraud** — Big amount + late-night hour + new
   customer. Bulk stolen-card scenario. Should reliably BLOCK.
   - Example: `new` profile, `misc_net`, $2500+, hour=3

2. **Card testing** — Small amount + odd hour + new customer. Fraudster
   verifying stolen card before big purchase. Should REVIEW (safety net
   downgrades from BLOCK since amount is tiny).
   - Example: `new` profile, `grocery_pos`, $5, hour=2

3. **Cross-category fraud** — Customer buys wildly outside their
   pattern. E.g. `senior` (usually grocery) suddenly buys $2000 luxury
   electronics.

4. **Geographic anomaly** — Not directly encodable in current schema
   (distance is fixed to 5 km), but you can mimic by pairing an
   improbable merchant with a customer profile.

5. **Velocity spike** — Established customer with $55 avg suddenly
   spending $3000. High ratio-to-mean pushes toward fraud.

6. **Weekend spike** — Some fraud rings run at weekends.
   `day_of_week` is not directly settable in checkout, but the payload
   route derives it from server time. Use `demo_hour_override` combined
   with realistic amounts.

### Legit typologies

7. **Routine grocery** — Small amount + business hours + established
   customer + grocery. Should APPROVE.

8. **Corporate lunch** — Medium amount + business hours + established
   or high_spender + food_dining or misc_net.

9. **Wedding order** — Big amount + business hours + high_spender or
   established + misc_net or shopping_net. Should APPROVE despite the
   size because customer history explains it.

10. **Late-night hostel/night-worker** — Small amount + night hour +
    senior or established + grocery_pos. Should APPROVE via safety
    net (small-amount rule).

11. **Senior citizen routine** — Small amount + business hours +
    `senior` profile + grocery_pos or gas_transport.

12. **Fuel purchase** — Small-to-medium + any hour + established +
    gas_transport.

---

## What the test runner does

`scripts/run_test_cases.py` reads a JSONL file of test cases and for
each row:

1. Sends the `payload` block to the local backend's `/api/checkout`
   endpoint (which does the same enrichment a real checkout does).
2. Records the model's decision, score, and SHAP top 5.
3. Compares the model's decision with the test case's `expected_label`:
   - `expected_label="fraud"` matches decision `declined` (or `review`
     with a high score).
   - `expected_label="legit"` matches decision `approved` (or `review`
     with a low score).
4. Emits per-typology precision/recall + a full confusion matrix.

Example output:
```
─── Test Case Results ───
Total cases:                200
Correct predictions:        173 (86.5%)
Missed fraud:                12 (blocked → approved)
False fraud alarms:          15 (legit → blocked)
Reviewed (correctly):        28
Reviewed (wrongly):           3

Per typology:
  late_night_bulk_fraud:   25/25  (100%)  ✓
  card_testing:            18/20  (90%)
  routine_grocery:         39/40  (97%)
  ...
```

---

## Where to put your test cases

Every teammate should write their test cases into their own JSONL file:

```
tests/authored/
  anurag.jsonl
  pankaj.jsonl
  gurnoor.jsonl
  sanvi.jsonl
```

The test runner picks up **every** `.jsonl` file in `tests/authored/`
and combines them. Team names in the filename let us track which cases
came from whom.

**When you're done writing, run:**

```bash
python scripts/run_test_cases.py --dir tests/authored
```

The report will be saved to `tests/results/eval_YYYY-MM-DD.md`.

---

## LLM-assisted authoring

To write cases quickly, you can use ChatGPT / Claude / Gemini. See
`docs/LLM_PROMPT.md` for a **ready-to-copy** prompt that explains the
schema to the LLM and asks for a specific number of cases in JSONL
format.

Sample workflow:

1. Open `docs/LLM_PROMPT.md`, copy the whole thing.
2. Paste into ChatGPT (or your LLM of choice).
3. At the top of the prompt, edit "Generate 20 test cases covering …"
   to whatever number and typology mix you want.
4. Copy the LLM's JSONL output.
5. Paste into your `tests/authored/<yourname>.jsonl` file.
6. Review each case for obvious errors before committing.

**Don't just blindly trust the LLM.** Skim each generated case and
sanity-check the `expected_label`.

---

## FAQ

**Q: Does the amount have to be in USD?**
A: Yes. `amount` is what the model scores. If you want to think in INR,
convert with `USD = INR / 80` when writing the case.

**Q: Can I invent a new merchant name?**
A: You can, but the model will have zero learned signal for it (it
falls back to the training-set global mean). To make merchant name
actually contribute, use one of the merchants in the demo (`TechMart
Electronics`, `Zomato`, `Swiggy`, `BigBasket`) or a merchant from the
Sparkov training set. See `SPARKOV_MERCHANTS.md` for a list (or
`GET /api/predict/sparkov/lookups` at runtime).

**Q: The model says APPROVED on a case I labelled fraud. Is my
label wrong or the model wrong?**
A: Sometimes yours, sometimes the model's. The evaluation report will
group by typology so we can spot systematic model errors vs random
label noise. Both signals matter.

**Q: What if a case is genuinely ambiguous?**
A: Use `expected_severity: "borderline"`. The runner weighs those less.
