# LLM Prompt — Generate CHIMERA-FD Test Cases

Copy **everything below the `--- PROMPT STARTS ---` line** into ChatGPT,
Claude, or Gemini. Edit the top line to say how many cases you want and
which typologies to prioritise.

---

--- PROMPT STARTS ---

You are helping me generate test cases for a fraud detection ML model
called CHIMERA-FD. Each test case is a single JSON object with a
customer transaction and a ground-truth label ("fraud" or "legit") that
you decide based on the scenario you describe.

Generate **20 test cases** covering a balanced mix of clear fraud, clear
legit, borderline, and edge cases. Return them as JSONL — one JSON
object per line, no wrapping array, no markdown fences.

## Test case schema

Every test case has this exact shape:

```json
{
  "id": "TC-XXX",
  "scenario": "Short human-readable name",
  "description": "One-sentence explanation of the scenario",
  "expected_label": "fraud" | "legit",
  "expected_severity": "clear" | "borderline" | "edge",
  "typology": "one of the typology names below",
  "payload": {
    "card_number": "<any 16-digit test number>",
    "cardholder_name": "<any name>",
    "amount": <USD dollars, float>,
    "merchant_name": "<merchant name>",
    "merchant_category": "<one of the 14 Sparkov categories>",
    "cust_email": "<any email>",
    "demo_profile": "established" | "new" | "high_spender" | "senior",
    "demo_hour_override": <int 0-23>
  },
  "notes": "Why this label — one sentence."
}
```

## Sparkov merchant categories (pick exactly one per case)

- `entertainment` — movies, concerts
- `food_dining` — restaurants
- `gas_transport` — fuel, cabs
- `grocery_net` — online groceries
- `grocery_pos` — in-store groceries
- `health_fitness` — gym, health
- `home` — home improvement
- `kids_pets` — kids, pet supplies
- `misc_net` — miscellaneous online (Zomato/Swiggy delivery)
- `misc_pos` — miscellaneous in-store
- `personal_care` — salons, spas
- `shopping_net` — online shopping (electronics)
- `shopping_pos` — in-store shopping
- `travel` — flights, hotels

## Customer profiles (pick exactly one per case)

- `established` — 35 y.o. regular customer, avg $55 spend, 200 prior
  transactions. The reliable everyday user.
- `new` — 26 y.o. new customer, zero purchase history. Fresh card.
- `high_spender` — 48 y.o. premium buyer, avg $500 spend, 300 prior.
  Consistent large purchases.
- `senior` — 67 y.o. careful spender, avg $42, mostly groceries and gas,
  150 prior transactions.

## Typology values

Pick one per case:

Fraud typologies:
- `late_night_bulk_fraud` — big amount + night hour + new customer
- `card_testing` — tiny amount + odd hour + new customer, verifying
  stolen card
- `cross_category_fraud` — customer buys wildly outside their pattern
- `velocity_spike` — established customer suddenly spending 20-50x their
  average
- `weekend_spike` — fraud running at odd weekend hours

Legit typologies:
- `routine_grocery` — small amount + business hours + established +
  grocery
- `corporate_lunch` — medium amount + business hours + established or
  high_spender + food_dining
- `wedding_order` — big amount + business hours + high_spender +
  misc_net (legit large corporate/wedding catering)
- `late_night_hostel` — small amount + night hour + senior or
  established + grocery
- `senior_routine` — small amount + business hours + senior + grocery
  or gas
- `fuel_purchase` — small-medium + any hour + established +
  gas_transport
- `high_value_regular` — large amount + business hours + high_spender +
  any category the profile normally buys

## Decision rules the model roughly follows

- **Amount matters most.** Small amounts (< $12) NEVER auto-block —
  they can only be `approved` or `review`.
- **Night hour** (0 ≤ hour < 6) is a fraud signal.
- **New customer** with big amount is a fraud signal.
- **Established / high_spender / senior** history offsets amount
  suspicion.
- **`misc_net`, `shopping_net`, `travel`** carry higher learned fraud
  rates than `grocery_pos`, `food_dining`.
- **`grocery_pos`, `food_dining`, `gas_transport`** are lower-risk
  categories.

## Rules for the labels you assign

- `"fraud"` means: any reasonable human would say this transaction
  looks like fraud based only on the payload data.
- `"legit"` means: any reasonable human would say this is a normal
  everyday purchase.
- If you're not sure, mark `expected_severity: "borderline"` and
  give your best guess for the label.
- Edge cases (hostel student late-night groceries, senior citizen
  ordering online for the first time) should use `expected_severity:
  "edge"`.

## Coverage requirements for the 20 cases

At minimum include:

- 3 × `late_night_bulk_fraud` (fraud)
- 2 × `card_testing` (fraud)
- 2 × `velocity_spike` (fraud)
- 1 × `cross_category_fraud` (fraud)
- 4 × `routine_grocery` (legit)
- 2 × `corporate_lunch` (legit)
- 2 × `wedding_order` (legit)
- 2 × `late_night_hostel` (legit, `edge` severity)
- 1 × `senior_routine` (legit)
- 1 × edge case of your choice

Vary the amounts, categories, and profiles so no two cases are
identical. IDs should be `TC-001`, `TC-002`, ... in order.

## Example output format (do NOT wrap in an array, do NOT add markdown fences)

```
{"id":"TC-001","scenario":"Late-night electronics bulk buy","description":"New card, $2800 electronics at 3AM","expected_label":"fraud","expected_severity":"clear","typology":"late_night_bulk_fraud","payload":{"card_number":"4532111122225678","cardholder_name":"Sarah Johnson","amount":2800.00,"merchant_name":"TechMart Electronics","merchant_category":"shopping_net","cust_email":"sarah.j@example.com","demo_profile":"new","demo_hour_override":3},"notes":"Brand-new customer plus large online amount plus night hour is the textbook fraud pattern."}
{"id":"TC-002",...}
...
```

Start now. Output exactly 20 JSONL lines, nothing else.

--- PROMPT ENDS ---

---

## After the LLM responds

1. Copy the JSONL output.
2. Paste into `tests/authored/<yourname>.jsonl`.
3. Skim each line — does the `expected_label` obviously match the
   scenario? If not, edit or delete the case.
4. Run `python scripts/run_test_cases.py --dir tests/authored`.

## Tweaking the prompt

- **Want more fraud, less legit?** Edit the "Coverage requirements"
  section to change the counts.
- **Want to focus on one typology?** Delete the other typology
  requirements and boost the one you want to 20.
- **Want harder edge cases?** Increase the "Edge case" count and lower
  the "clear" cases.

## Reminder about honesty

The LLM is generating **synthetic scenarios**. It cannot know how the
model was trained. Its labels are our human-plausibility ground truth,
not model truth. When the model disagrees with the label, we investigate
both sides.
