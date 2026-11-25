# How the restocking modes work

The app estimates how many units each outlet needs, assigns each unit a score based on the chosen objective, and distributes the shared budget with either Greedy or Bounded Knapsack. Profit and Popularity use the same need calculation but different scores.

## 1. Forecast monthly sales

For each outlet and product ID, the app takes monthly customer purchases (`mth_purchase`) from the imported CSV files. If the same product has multiple batches in one month, it counts that month's purchases once. The forecast is calculated separately for each outlet; sales from different outlets are not combined into one forecast.

With at least two months of data, the app fits a straight line using ordinary least-squares linear regression. It uses a calendar-month index `x = 12 × year + month`, so missing months are spaced correctly rather than treated as zero sales. With one month, the forecast is that month's sales. The forecast cannot be negative.

For example, monthly sales of 80, 90, and 100 in three consecutive months follow a trend of 10 additional units per month. The next-month forecast is 110 units.

## 2. One replacement rule

The latest imported month for each outlet/product supplies sales, current stock, prices and monthly expiry losses. Prior months supply sales history for the Popularity forecast. Old stock is not added to current stock.

```text
expired replacement = floor(this month's expired units × 75%)
restocking need = this month's units sold + expired replacement
available stock = current stock − expired/due-today stock still on hand
new total target = available stock + restocking need
```

This replaces the gradual target history, initial target, recent-sales demand cap, near-expiry credit and forecast shelf-life need cap. There is no separate quantity formula for Profit or Popularity. The 75% is an explicit business setting (`EXPIRED_REPLACEMENT_PERCENT`), not a learned optimum. The app replaces all sales but only part of expired losses, allowing total stock to decline without an abrupt stop in replenishment.

For an initial 50 units, 7 sold and 40 expired leave 3 usable. Purchase `7 + floor(40 × 0.75) = 37`, producing a new target of `3 + 37 = 40`. The actual allocation may be smaller when the budget is limited or the selected objective gives a zero score. Projected stock after allocation is not an executed purchase or receipt.

### Recording monthly losses

The optional `mth_expired` CSV column records units that expired during that reporting month, including losses already disposed of. Repeat the same monthly product total across its batch rows, just like `mth_purchase`; it is counted once, not once per batch. Zero means no expiry losses that month. Do not repeat a previous month's loss as a new loss.

If `mth_expired` is blank or absent, the app estimates losses from positive stock in the latest snapshot whose batch expiry date falls within the reporting month. Expired batches with earlier expiry dates are not new losses and are not counted again. This estimate cannot see units already disposed of, so supplying `mth_expired` is preferred. The table identifies whether losses are reported or estimated. The optional legacy `initial_stock_target` field is retained for file compatibility but does not affect this rule.

Current stock is the stock remaining after sales; it may still include expired goods awaiting removal. Do not include sold units in current stock, or add disposed units back into it. All dates use the file's month-end snapshot, not today's date. Stock expiring that day cannot meet future sales. Stock with 1–14 days remaining is flagged but remains available, without a second sales-credit adjustment.

### Five-month example at a $1,000 budget

Import all five CSVs from `sample_data/expiry_series/`, select `Outlet_ExpirySeries`, set the budget to $1,000 and use **As of** to compare months.

| Month | Starting units | Sold | Expired this month | Available left | Buy | New total target |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| July | 50 | 7 | 40 | 3 | 37 | 40 |
| August | 40 | 10 | 24 | 6 | 28 | 34 |
| September | 34 | 12 | 16 | 6 | 24 | 30 |
| October | 30 | 14 | 10 | 6 | 21 | 27 |
| November | 27 | 18 | 0 | 9 | 18 | 27 |

The example assumes expired units are removed and the recommended quantities are received between monthly snapshots; the app does not execute these movements. This is a synthetic monthly balance illustration, not a delivery transaction ledger. Old GradualDemo/ExpiryDemo/OverstockDemo datasets remain importable, but their previous target-based expected results no longer apply.

The replacement rule does not increase stock automatically when demand grows, enforce a minimum shelf stock, or predict which individual units will actually sell. It can continue buying slow-selling products because it intentionally replaces 75% of losses. Near-expiry stock can still expire before it is sold. Those are limitations of the deliberately simple policy, not extra hidden target rules.

## 3. Score each unit

The Objective selector uses the same `OBJECTIVES` list and per-unit score formulas as `main` (verified against `c966792`). The default is **Availability + margin**. Switching objectives changes only unit scores and ranking; all objectives share the same replacement need, budget algorithms and expiry calculation. The expiry/replacement policy on this branch remains separate from main's forecast-based need calculation.

| Objective | Unit score |
| --- | --- |
| Availability + margin (default) | 100 + non-negative gross margin in cents |
| Popularity | Forecast monthly sales × 100, rounded to an integer |
| Profit | Non-negative gross margin in cents |

### Popularity

```text
popularity score per unit = round(forecast monthly sales × 100)
```

The factor of 100 preserves two decimal places of forecast precision in the integer score used by knapsack. Higher forecast sales give a higher score. Each recommended unit of the same outlet/product receives the same score; this can concentrate spending on highly popular products. The score is a relative priority, not a promise that all allocated units will sell.

### Profit

```text
gross profit per unit = max(0, selling price − purchase cost)
profit score per unit = round(gross profit per unit × 100)
```

The profit score represents the gross margin in cents. The replacement need limits how many units can be allocated, but sales volume does not directly change the profit score per unit. Both allocation methods skip products whose score is zero. The estimate assumes units sell at the stated price and excludes operating costs, discounts, and waste. Availability + margin retains its 100-point base even when gross margin is zero.

## 4. Allocate the budget

The app ranks recommendations by **score per unit ÷ unit cost**, highest first, using stable merge sort. The GPT importer requires a positive unit cost.

- **Greedy** buys in ranked order, up to each product's need and the remaining budget. It is fast, but it may not achieve the highest possible total score.
- **Bounded Knapsack** searches for the combination of whole units that maximizes total score without exceeding the budget or any product's need. It uses integer cents and is limited to budgets of $1,000 or less. For a larger budget, select Greedy or Even Distribution; the interface displays an explanatory message.
- **Balanced Budget (Even Distribution)** divides the budget into equal dollar shares across all eligible products (water-filling up to each item's need), then distributes any leftover budget one unit at a time in rank order (round-robin) so a broad variety of items is restocked.
- **Integrated Balanced Base (%) in Greedy and Bounded Knapsack**: Use the **Balanced Base (%)** control ($0\%$–$100\%$, default $25\%$) to reserve a portion of the budget for even distribution across all eligible products first; Greedy or Bounded Knapsack then allocates the remaining budget (plus any unspent base change) across each product's remaining unmet need.

## Example

Assume each product's calculated need is large enough to spend the entire $60 budget:

| Product | Cost | Selling price | Forecast monthly sales |
| --- | ---: | ---: | ---: |
| White Monster | $2.00 | $3.00 | 100 |
| Premium juice | $3.00 | $6.00 | 40 |

| Objective | Product | Score per unit | Score / cost |
| --- | --- | ---: | ---: |
| Popularity | White Monster | 100 × 100 = 10,000 | 10,000 / $2 = 5,000 |
| Popularity | Premium juice | 40 × 100 = 4,000 | 4,000 / $3 ≈ 1,333.33 |
| Profit | White Monster | ($3 − $2) × 100 = 100 | 100 / $2 = 50 |
| Profit | Premium juice | ($6 − $3) × 100 = 300 | 300 / $3 = 100 |

Greedy would buy 30 White Monsters in Popularity mode, or 20 premium juices in Profit mode. Knapsack maximizes the selected total score and may choose a different mix when costs or needs make another combination better.

## Try it with the sample data

In the app, select **Import monthly CSV** and import the September, October, and November 2026 files for `Outlet_Youth` and `Outlet_Community` from `sample_data/`. The files contain synthetic sales for the same 40 product IDs across both outlets. Youth is an illustrative high-candy-and-snack-sales scenario; Community is an illustrative higher-grocery-and-household-sales scenario. These patterns are invented for demonstration and do not represent measured age-group preferences.

Open **Restocking Recommendations**, select one outlet and a $500 budget, and switch the **Restock objective** between Profit and Popularity. The table shows forecast monthly sales, priority score, need, and allocated units. Select **All Outlets** to share the budget across both outlets while forecasts remain outlet-specific. You can also compare Greedy and Bounded Knapsack. Exported recommendations include the objective and score.

### Demonstrating Greedy versus Knapsack with varied prices

The nine Outlet C, Youth, and Community files now use synthetic unit costs ranging from $0.69 to $14.26 and independently varied profit margins. Each product keeps the same prices across months and, for shared product IDs, across outlets. Sales, stock, dates, and other input fields are unchanged. These are demonstration prices rather than surveyed retail prices.

For a clear difference, import the three `Outlet_C` monthly files, select `Outlet_C`, choose **Profit**, and enter a **$5.00** budget:

| Method | Allocated products | Spend | Estimated gross profit |
| --- | --- | ---: | ---: |
| Greedy | 1 Fresh Full Cream Milk 1L | $4.43 | $5.07 |
| Knapsack | 1 Roasted Almonds 100g and 1 White Monster Energy Ultra 500ml | $4.91 | $5.58 |

Knapsack achieves about 10.1% more gross profit in this example. Greedy chooses the highest profit-per-cost product first, leaving $0.57 that cannot buy another unit. Knapsack chooses a better combination. The example assumes the recommended units sell at the stated price.

For a Popularity comparison, import the three `Outlet_Youth` files, select that outlet, and use a **$20.00** budget. Greedy's total popularity score is **336,000**, versus **342,600** for Knapsack; two product allocations differ. Scores are per-unit priorities multiplied by allocated quantities, not sales counts. Results depend on the imported data, outlet, objective, and budget; a larger price range does not guarantee a large difference at every budget.
