# GPT1: replace sales and 75% of monthly expired losses

This synthetic five-month series demonstrates the simplified rule for **EXP-SERIES-001 — Strawberry Yogurt 150g**. Every month has positive sales, while expiry losses gradually fall.

```text
purchase needed = monthly sales + floor(monthly expired units × 75%)
new total target = remaining unexpired stock + purchase needed
```

## Try it

Run `GPT/app.py`, import all five CSV files in this directory, choose `Outlet_ExpirySeries`, and set the budget to **$1,000.00**. Use **As of** to move from July through November. Both Profit and Popularity, with either Greedy or Knapsack, fund the full needs at this budget. It applies separately to each decision, not cumulatively to the series.

| Month | Starting units | Sold | Expired this month | Usable left | Replace expired | Purchase | New total | Spend |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| July | 50 | 7 | 40 | 3 | 30 | 37 | 40 | $44.40 |
| August | 40 | 10 | 24 | 6 | 18 | 28 | 34 | $33.60 |
| September | 34 | 12 | 16 | 6 | 12 | 24 | 30 | $28.80 |
| October | 30 | 14 | 10 | 6 | 7 | 21 | 27 | $25.20 |
| November | 27 | 18 | 0 | 9 | 0 | 18 | 27 | $21.60 |

July's order is `7 sold + floor(40 expired × 75%) = 37`. Adding the 3 usable units gives a total of 40. With no expiry in November, replacing the 18 sales maintains the total at 27. This differs from the removed 20%-per-month target-history rule and from GPT2's forecast-plus-buffer rule.

## CSV meanings

- `mth_purchase` is actual units sold during the reporting month, repeated consistently across product batches and counted once.
- `mth_expired` is units that expired during that month, including already-disposed losses. It also repeats across batches and is counted once. Do not repeat an older loss as a new loss.
- `current_total_stock` is remaining stock, including expired units still on hand. July has 43 units in its CSV: 40 expired and 3 usable. The 7 sold are not included.
- The old `initial_stock_target` field is blank and unused. No target ledger or previous target is required.
- Unit cost is $1.20, selling price $2.10, lead time zero and shelf life 20 days, all fictional demonstration assumptions. All expiry dates are relative to month-end snapshots.
- Each month's starting balance assumes prior recommendations are fully received and expired units are removed between snapshots. These files illustrate aggregate planning balances, not a detailed receipt ledger. The program does not perform purchases, receipt or disposal automatically.
- This is a deliberate replacement policy, not a proven optimum. Replacing 75% of expired losses can still cause waste when demand is weak. Forecasting remains available for Popularity scores rather than changing these quantities.

All five files were checked with GPT1's importer, both objectives and both allocation algorithms at $1,000. The budget is intentionally generous so it does not cause the reduction in stock totals.
