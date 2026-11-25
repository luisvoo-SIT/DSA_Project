# Market Expand

A PySide6 desktop prototype for viewing monthly outlet inventory, inspecting batch expiry, predicting demand, and allocating a shared restocking budget. The editable process diagram remains available from the toolbar.

## Run

```powershell
py -m pip install -r requirements.txt
py app.py
```

Choose **Import monthly CSV** and select one or more files. Try the three files in `sample_data`. Importing a file for an existing outlet and month asks to replace that month's records. Imported records and edits are held in memory; use **Save edited CSV** to persist each edited month. Export the calculated recommendations separately. The inventory table is editable; editing monthly purchases updates all batches for that product in that file. Use the inventory filter controls to search a selected column (or all columns), and sort by any column in ascending or descending order. These controls apply to the inventory and expiry views; the global product search and outlet selector also affect the recommendation display. Numeric columns are sorted numerically. The recommendation chart shows need and allocation for the first 20 ranked, displayed products; the table and export contain all applicable results. The expiry chart groups batch quantities by remaining shelf life, including expired units. It includes historical snapshots: a batch appearing in multiple report months is counted in each snapshot, not as distinct physical inventory. The expiry table shows the report month for each row. The budget, allocation method, search and outlet filter update results immediately. The search affects the displayed recommendations, not how the selected outlets share the budget.

Pandas handles table filtering, sorting and graph aggregation. Matplotlib provides the embedded charts: pandas alone does not supply the interactive Qt chart canvas. Both dependencies are listed in `requirements.txt`.

Recommendations recalculate in the background after a short pause in editing the budget. The summary shows when a calculation is running; exporting is available again when the latest result is ready. Large knapsack calculations can still take time, but the window remains interactive.

## CSV format

The filename is `Outlet_Name_YYYY_MM.csv`, for example `Outlet_A_2026_06.csv`. The final year and month identify the reporting month and the preceding text identifies the outlet. A reporting snapshot is taken on the last day of the month. Required headers:

```text
item_id,item_name,category,unit_cost,unit_sell,current_total_stock,mth_purchase,lead_time,shelf_life,batch_no,supplier_rating
```

Each row is a product batch. `batch_no` is four-character MMYY text and is preserved with leading zeroes. Stock is batch-specific. Monthly customer purchases repeat across batches for the same product and must agree; they are counted once per product and month. Lead time and shelf life are in days; supplier rating is 0–5. Prices have at most two decimal places. The importer rejects duplicate product/batch pairs, negative quantities, invalid dates, and batches whose assumed delivery is after the report date.

## Model and assumptions

- The batch number denotes the order month. Delivery is the last day of that month plus lead time; shelf life starts on delivery. Remaining shelf life is calculated at the report date. The whole batch is considered expiring if it has 14 days or less remaining, including already expired batches. The expiry tab uses a priority queue, earliest first.
- Forecasting uses one monthly purchase value per product and outlet. With at least two historical months, linear regression predicts the following month using calendar month indices; with one month it uses that month's purchases. Missing months are not treated as zero. Predictions are clamped at zero.
- The latest snapshot for each product and outlet is used. This means an older snapshot may be used for an outlet/product if no newer one was imported. Import matching recent months for a fair comparison.
- Restocking need uses one replacement rule: **units sold this month + floor(75% of units expired this month)**. The new total target is current unexpired stock plus that need. Both objectives use the same need. This replaces the earlier gradual-target and expiry-adjustment rules.
- Optional `mth_expired` records actual monthly expiry losses, including stock already disposed of. Repeat it consistently across batch rows for that product; count it once per month. Without it, the app estimates losses only from stock whose expiry date falls within the reporting month, so retained older expired stock is not counted again. Already-disposed losses are invisible to that estimate. The table shows the data source.
- Unexpired stock, including near-expiry stock, is available; expired/due-today units are excluded. Near-expiry stock is flagged for review. The new total is a projection after removing expired stock and funding recommendations; inventory is not automatically changed.
- The shared Objective selector matches main: **Availability + margin** (default) scores 100 plus non-negative margin cents; **Popularity** scores forecast monthly sales multiplied by 100; **Profit** scores non-negative margin cents. Only priority points change between objectives; replacement quantities and allocation algorithms are shared. Supplier rating is informational. Zero-score products are not allocated. Forecasting affects the popularity score, not the quantity calculation.
- Import `sample_data/expiry_series/` and set a $1,000 budget for a five-month example: targets **50 → 40 → 34 → 30 → 27 → 27**. Use **As of** to compare months. The old `initial_stock_target` column is accepted for compatibility but no longer affects the calculation. See [RESTOCKING_MODES.md](RESTOCKING_MODES.md) for the worked example and assumptions.
- Greedy allocation buys in rank order. Bounded knapsack maximizes the selected additive score using integer cents and unit quantities, subject to each product's need and the budget. Knapsack is limited to budgets up to 1,000.00 for responsiveness; use Greedy for larger budgets. Neither method models minimum order quantities, supplier capacity, future expiry interactions, or actual sales and profit. See [RESTOCKING_MODES.md](RESTOCKING_MODES.md) for details and examples.
- Exact product ID lookup uses a balanced binary search tree; partial name/ID search uses linear search. The editable flowchart is a separate visual model: editing a diagram does not alter the algorithms. Its live calculation panel is a separate illustration.

The application does not authenticate users, send purchase orders, or track shipments. Recommendations are decision support and do not update inventory automatically.

## Balanced budget for more variety

Choose **Profit** or **Popularity** under Objective, then **Balanced budget** under Allocation. This progressively funds the least-funded product/outlet by spend, using score/cost rank to break ties. Money is redistributed when needs are met or an item is unaffordable. The method respects the total budget and each product's need; zero-score products are excluded.

Equal spending does not mean equal unit counts, and whole-unit prices prevent an exact split. Each outlet/product is a separate request. Balanced favours spreading money rather than maximizing total score, so the two objectives can produce similar balanced allocations. It is a separate method alongside Greedy and Knapsack; those algorithms retain their existing behaviour. The summary shows how many eligible products were funded, and exports include `allocation_method`.

For a demo, import the Youth files, choose **As of = 2026-09**, select Outlet Youth, and enter a $600 budget. In either Profit or Popularity, Greedy funds 4 products while Balanced budget funds all 40. See the scoring guide for exact spending figures and limitations.

## Balance first, then use Greedy or Knapsack

Select Greedy or Knapsack, enable **Balance first**, and choose the **Budget share for balanced base** (50% initially). Stage one balances that share across eligible outlet/products. Stage two uses the selected algorithm to allocate all unspent money to remaining need, including money that stage one could not spend on whole units. The balanced purchases are locked in; quantities cannot exceed the original need.

More budget for the balanced base generally favours variety; less leaves more money for score-based prioritization. At 0%, the allocation is the original Greedy/Knapsack method. At 100%, it behaves like Balanced budget. The separate Balanced budget method still balances the entire budget and disables the extra controls. Knapsack retains its $1,000 overall budget limit. Hybrid knapsack optimizes the remaining problem, not the entire original budget after rearranging the balanced purchases.

The table and export separate **Balanced units** from **Priority units** and record `balance_percent` and `allocation_method`. The summary shows actual spending in each stage. With Youth September, Popularity and $600, a 50% base funds all 40 products: stage one spends $299.40; Greedy adds $300.32, or Knapsack adds $300.48.

## Test

```powershell
py -m unittest -v
```
