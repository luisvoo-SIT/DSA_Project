# How the restocking modes work

The app estimates how many units each outlet needs, assigns each unit a score based on the chosen objective, and distributes the shared budget with either Greedy or Bounded Knapsack. Profit and Popularity use the same need calculation but different scores.

## 1. Forecast monthly sales

For each outlet and product ID, the app takes monthly customer purchases (`mth_purchase`) from the imported CSV files. If the same product has multiple batches in one month, it counts that month's purchases once. The forecast is calculated separately for each outlet; sales from different outlets are not combined into one forecast.

With at least two months of data, the app fits a straight line using ordinary least-squares linear regression. It uses a calendar-month index `x = 12 × year + month`, so missing months are spaced correctly rather than treated as zero sales. With one month, the forecast is that month's sales. The forecast cannot be negative.

For example, monthly sales of 80, 90, and 100 in three consecutive months follow a trend of 10 additional units per month. The next-month forecast is 110 units.

## 2. Calculate how many units are needed

For each product's latest snapshot at an outlet:

```text
daily demand = forecast monthly sales / number of days in latest snapshot month
target stock = ceil(daily demand × (lead time in days + 30))
raw need = max(0, target stock − usable stock)
shelf-life cap = ceil(daily demand × shelf life in days)
restocking need = min(raw need, shelf-life cap)
```

Usable stock excludes batches with 14 days or less of remaining shelf life, including expired stock. The target stock and shelf-life cap are rounded up to whole units. The result is a non-negative whole number. Forecasting affects the quantity available for allocation in **both** modes, even when Profit is selected.

## 3. Score each unit

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

The profit score represents the gross margin in cents. The forecast-based need limits how many units can be allocated, but sales volume does not directly change the profit score per unit. Both allocation methods skip products whose score is zero. The estimate assumes units sell at the stated price and excludes operating costs, discounts, and waste.

## 4. Allocate the budget

The app ranks recommendations by **score per unit ÷ unit cost**, highest first, using stable merge sort. The GPT importer requires a positive unit cost.

- **Greedy** buys in ranked order, up to each product's need and the remaining budget. It is fast, but it may not achieve the highest possible total score.
- **Bounded Knapsack** searches for the combination of whole units that maximizes total score without exceeding the budget or any product's need. It uses integer cents and is limited to budgets of $1,000 or less. For a larger budget, select Greedy; the interface displays an explanatory message.

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
