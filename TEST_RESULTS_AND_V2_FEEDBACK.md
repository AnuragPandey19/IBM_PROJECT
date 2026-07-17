# Test cases — V1 results and V2 feedback

## Part 1 — V1 test results (in plain language)

We ran your 234 v1 test cases against the Sparkov fraud detection model directly
(no network, no API, just the model). Here is what happened:

- **65.8% overall accuracy** — the model got 154 out of 234 correct.
- **94% of legit transactions were correctly approved.** The model rarely
  bothers real customers.
- **Only 33% of fraud attempts were caught.** The model misses two out of
  three fraud transactions.

### Where the model shines (100% correct on these)

- `corporate_lunch` — 19/19
- `fuel_purchase` — 16/16
- `routine_grocery` — 21/21
- `senior_routine` — 17/17
- `high_value_regular` — 14/17 correct + 3 sent to review (0 wrong)
- `wedding_order` — 17/18 correct + 1 review (0 wrong)
- `late_night_bulk_fraud` — 22/24 caught (this is the model's fraud strength)

### Where the model completely fails (0% caught)

- `card_testing` — 0 out of 23 tiny-amount frauds caught. The model gives a
  $1.49 fraud a score of `0.00000003` — it is confident the transaction is
  fine. The amount is too small to trigger any alarm.
- `weekend_spike` — 0 out of 20 caught. Fraud between 20:00 and 23:00 slips
  through because the model only treats hour < 6 as suspicious.
- `velocity_spike` — 0 out of 20 caught as fraud (6 landed in review, still
  bad). Established customers suddenly spending 5-10x their usual amount are
  not flagged. The velocity feature exists but is not weighted enough.

### Partially working

- `cross_category_fraud` — 13 out of 20 caught. Missed 7, mostly senior
  customers buying in unfamiliar categories at business hours.
- `late_night_hostel` — 15 out of 19 correctly labeled legit. 2 false positives
  where the model wrongly blocked established customers buying groceries at
  0-2 AM.

### Bottom line

The model is a specialist. It handles obvious fraud (giant amount + odd hour
+ new customer) and it recognizes normal spending patterns. It is blind to
subtle fraud — small amounts, evening hours, and unusual behaviour from
existing customers. These are exactly the patterns a real fraudster would try.

The next step is either retraining the model with more diverse fraud examples,
or adding rule-based safety nets in the API for the three failing patterns.

---

## Part 2 — Problems with V2

The v2 file you uploaded is very different from v1. All 234 original test case
IDs were completely rewritten with new payloads, and 6 new cases were added
(TC-235 to TC-240). Total 240 rows.

Unfortunately v2 has three problems that would make the test results
meaningless. If we ran v2 as-is, the numbers would look real but they would
not reflect the model's true performance.

### Problem 1 — inconsistent labels

V1 used only two label values: `fraud` and `legit`. V2 has three:
`fraud` (115 rows), `legit` (120 rows), and `fraudulent` (5 rows).

The runner script does not know what `fraudulent` means. Those 5 rows would
be misclassified in the accuracy calculation.

### Problem 2 — merchant categories the model does not know

V1 used the exact codes the Sparkov model was trained on:
`shopping_net`, `misc_net`, `grocery_pos`, `food_dining`, `gas_transport`
and so on.

V2 uses freeform strings:
`Groceries`, `Charity`, `Dining/Restaurant`, `Electronics`, `Insurance`

The model has never seen these strings. It converts every unknown category
to the value 0 internally, which means the category feature carries no
signal. Every prediction becomes noise. The model is essentially blind to
what type of merchant the transaction is at.

### Problem 3 — demo profile keys that do not exist

The checkout endpoint has exactly four customer profiles defined:
`new`, `established`, `high_spender`, `senior`. Each profile carries
important context — a home city, a prior spending history, a customer age,
etc. This is what makes `demo_profile: "new"` behave differently from
`demo_profile: "established"` in the test.

V2 uses profiles like `suburban_family`, `corporate_traveler`, `dormant_user`,
`high_net_worth`, `unassigned`. None of these exist in the code. When the
runner cannot find the profile, it silently falls back to the `new` profile
for every row. That means every test in v2 is scored as if the transaction
came from a brand-new customer with zero purchase history — regardless of
what the scenario intends.

The whole point of `demo_profile` in the test cases is to simulate different
customer contexts. V2 nullifies that.

---

## Part 3 — What to fix for V2 iteration 2

The scenarios, descriptions, notes, cardholder names, emails, and card
numbers can all stay creative. Those fields do not touch the model. But
three fields have to match the code exactly:

### Field 1 — `expected_label`

Use only:
- `fraud`
- `legit`

No `fraudulent`, no `suspicious`, no `unknown`. Two values, that is it.

### Field 2 — `merchant_category`

Use only one of these Sparkov codes (case-sensitive):
- `entertainment`
- `food_dining`
- `gas_transport`
- `grocery_net`
- `grocery_pos`
- `health_fitness`
- `home`
- `kids_pets`
- `misc_net`
- `misc_pos`
- `personal_care`
- `shopping_net`
- `shopping_pos`
- `travel`

If your scenario is about grocery shopping, use `grocery_pos` (in-store) or
`grocery_net` (online). If it is a restaurant, use `food_dining`. If it is
online electronics, use `shopping_net`. If it is fuel, use `gas_transport`.
Match your scenario to one of these 14 codes.

### Field 3 — `demo_profile`

Use only:
- `new` — brand-new customer, no purchase history, card issued recently
- `established` — long-standing customer, consistent low-value spending
  (~$55 average)
- `high_spender` — premium customer, ~$500 average, high but consistent
- `senior` — older customer, mostly groceries and fuel, ~$42 average

Pick the profile whose historical pattern best matches your test scenario.
The model uses each profile's velocity history (how much they usually
spend, how often, when they last purchased) — so getting this right is
what makes the test meaningful.

### One more thing

If you want to test scenarios that involve dormant users, corporate cards,
or high-net-worth insurance payments — those are great ideas, but they need
new profiles added to the code first. Talk to Anurag about which profiles
would be worth adding before writing test cases that depend on them. It is
much easier to add a new profile in `api/routes/checkout.py` than to run
tests against a mismatched vocabulary.

---

## Suggested next steps

1. Regenerate v2 using the three fields above with only allowed values.
2. Send the corrected file to Anurag.
3. Anurag runs the runner script and we get a real accuracy number for v2.
4. If v2 has enough new failure patterns beyond what v1 caught, that becomes
   another data point for the mentor conversation. If it repeats v1's
   findings, we already know what to fix.
