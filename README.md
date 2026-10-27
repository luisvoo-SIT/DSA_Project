# Market Expand

A PySide6 desktop prototype for viewing monthly outlet inventory, inspecting batch expiry, predicting demand, and allocating a shared restocking budget. The editable process diagram remains available from the toolbar.

## Run

```powershell
py -m pip install -r requirements.txt
py app.py
```

Choose **Import monthly CSV** and select one or more files. Try the three files in `sample_data`. Importing a file for an existing outlet and month asks to replace that month's records. Imported records and edits are held in memory; use **Save edited CSV** to persist each edited month. Export the calculated recommendations separately. The inventory table is editable; editing monthly purchases updates all batches for that product in that file. The budget, allocation method, search and outlet filter update results immediately. The search affects the displayed recommendations, not how the selected outlets share the budget.

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
- Daily demand is predicted monthly demand divided by the number of days in the latest report month. Target stock covers supplier lead time plus 30 days. Expiring stock is excluded from usable stock. Order need is capped at forecast sales over the product's shelf life. For product-level price, lead time and shelf life, the first batch row in the latest snapshot is used; keep these fields consistent across batches if that is intended.
- The illustrative priority value per unit is 100 points for availability plus one point per cent of non-negative gross margin. Merge sort ranks value per cost. This is a heuristic, not a proven profit or stockout optimum. Supplier rating is stored but does not currently affect the score. The budget is shared across the selected outlets.
- Greedy allocation buys in rank order. Bounded knapsack maximizes this same additive score using integer cents and unit quantities, subject to each product's need and the budget. Knapsack is limited to budgets up to 1,000.00 for responsiveness; use Greedy for larger budgets. Neither method models minimum order quantities, supplier capacity, future expiry interactions, or actual sales and profit.
- Exact product ID lookup uses a balanced binary search tree; partial name/ID search uses linear search. The editable flowchart is a separate visual model: editing a diagram does not alter the algorithms. Its live calculation panel is a separate illustration.

The application does not authenticate users, send purchase orders, or track shipments. Recommendations are decision support and do not update inventory automatically.

## Test

```powershell
py -m unittest -v
```
