# Market Expand

A PySide6 desktop prototype for viewing monthly outlet inventory, inspecting batch expiry, predicting demand, and allocating a shared restocking budget. The editable process diagram remains available from the toolbar.

## Features

- **Monthly Inventory View**:
  - Multi-file monthly CSV import (`Outlet_Name_YYYY_MM.csv`).
  - Interactive, editable spreadsheet table. Editing monthly customer purchases automatically synchronizes across all batches for that product in that file.
  - In-memory data store with single-click persistence (**Save edited CSV**).
  - Fast search across all columns or specific columns, with ascending/descending numeric sorting.
  
- **Batch Expiry Inspection**:
  - Min-Heap **Priority Queue** ordering batches earliest remaining shelf life first.
  - Automatic flagging of critical batches with $\le 14$ days remaining (including expired units).
  - Embedded **Matplotlib** chart grouping batch stock quantities by remaining shelf life categories across all imported historical snapshots.
  - Clear display of report month, order date, delivery date, expiry date, and remaining shelf life.

- **Demand Forecasting & Restocking Allocation**:
  - Calendar month index **Linear Regression** for products with $\ge 2$ historical months; single-month purchase pass-through for 1 month; clamped at $\ge 0$.
  - Restocking need uses one replacement rule: **units sold this month + floor(75% of units expired this month)**. The new total target is current unexpired stock plus that need.
  - Optional `mth_expired` records actual monthly expiry losses (including disposed stock); without it, losses are estimated from batches whose expiry date falls within the reporting month.
  - Unexpired stock (including near-expiry 1–14d stock, which is flagged for review) remains available; expired/due-today units ($\le 0$d) are excluded.
  - Three selectable objectives: **Availability + margin** (default, $100 + \text{margin cents}$), **Popularity** ($\text{forecast} \times 100$), and **Profit** ($\text{margin cents}$).
  - Choose a restocking objective: **Profit** scores each unit by non-negative gross margin in cents; **Popularity** scores each unit by its outlet's forecast monthly sales multiplied by 100 (rounded to an integer). A score of zero receives no allocation.
  - Both objectives use the forecast-based need cap, usable stock, lead time and shelf life. Scores are per outlet and are calculated from imported history; they are not stored in input CSVs. Popularity is a priority score, not predicted sales of the allocated units, and may concentrate spending on a few products. Profit assumes units sell at the stated price and excludes operating costs and waste.
  - Explicit **Merge Sort** ranking items by value per cost.
  - Shared budget allocation across selected outlets:
    - **Greedy Allocation**: Buys in rank order up to the shared budget limit.
    - **Bounded Knapsack Allocation**: Dynamic programming optimization maximizing total additive priority score using integer cents and discrete unit quantities (supported for budgets up to \$1,000.00).
    - **Balanced Budget (Even Distribution) & Integrated Balanced Base (%)**: Splits a configurable percentage of the budget (`Balanced Base (%)`, $0\%$–$100\%$, default $25\%$ in the UI) evenly across all eligible products first so every affordable item receives baseline variety stock, and then allocates the remaining budget using **Greedy** or **Bounded Knapsack** across unmet needs (or $100\%$ even distribution when **Balanced Budget (Even Distribution)** is selected).
  - Embedded **Matplotlib** grouped bar chart displaying Need vs Allocated units for the first 20 ranked displayed products.
  - **Balanced Binary Search Tree (AVL Tree)** for exact product ID lookup and linear search for partial name/ID queries.
  - One-click export of all calculated recommendations to CSV (**Export recommendations CSV**).

- **Editable Process Flowchart & Live Calculation Panel**:
  - Accessible directly from the main toolbar (**Process Diagram**).
  - Visual interactive diagram canvas (`QGraphicsView` / `QGraphicsScene`) with draggable nodes, connecting arrows, and node editing/creation tools.
  - Interactive live calculation panel illustrating step-by-step mathematical breakdown for customizable sample inputs.

---

## Installation & Running

### Requirements
- Python 3.10+
- Dependencies listed in `requirements.txt`:
  - `PySide6`
  - `pandas`
  - `matplotlib`

### Windows (PowerShell / Command Prompt)

```powershell
py -m pip install -r requirements.txt
py app.py
```

### macOS / Linux (Terminal)

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

---

## Quick Tour with Sample Data

1. Launch `app.py`.
2. Click **Import monthly CSV** in the toolbar.
3. Select the three sample files located in `sample_data/`:
   - `Outlet_A_2026_05.csv`
   - `Outlet_A_2026_06.csv`
   - `Outlet_B_2026_06.csv`
4. Inspect the **Monthly Inventory** tab. Try editing `mth_purchase` or stock in the table. Notice all views and allocations update immediately.
5. Click **Save edited CSV** to persist any modified month back to a CSV file.
6. Switch to **Batch Expiry Inspection** to view batches ordered by the Priority Queue (earliest expiry first) and the aggregated shelf life distribution chart.
7. Switch to **Restocking Recommendations** to adjust the restocking budget, switch between Greedy and Knapsack allocation methods, filter outlets, or search for products.
8. Click **Export recommendations CSV** to export the entire recommendation table.
9. Click **Process Diagram** on the toolbar to explore the editable pipeline diagram and interactive live calculation illustration.

To compare objectives, import `Outlet_C_2026_09.csv`, `Outlet_C_2026_10.csv`, and `Outlet_C_2026_11.csv` together, choose Outlet C and a $500 budget, then switch **Restock objective**. These files contain synthetic sales and stock figures for the same 100 products across three months, including White Monster Energy. The table displays the forecast, selected objective score, and allocation; the recommendation export records the objective. Higher popularity scores indicate higher forecast monthly demand, and scores are not comparable across objectives.

---

## CSV File Specification

Filenames must adhere to `Outlet_Name_YYYY_MM.csv` (e.g. `Outlet_A_2026_06.csv`). The final year and month denote the reporting month; a reporting snapshot is taken on the last day of that month.

### Required CSV Headers:

```text
item_id,item_name,category,unit_cost,unit_sell,current_total_stock,mth_purchase,lead_time,shelf_life,batch_no,supplier_rating
```

### Validation & Business Rules:
- `batch_no`: 4-character `MMYY` text preserved with leading zeroes (e.g., `0526`).
- Batch delivery is assumed to occur on the last day of the order month plus `lead_time` days.
- Batches whose assumed delivery date is strictly after the reporting snapshot date are rejected.
- Stock is batch-specific.
- Monthly purchases (`mth_purchase`) repeat across batches for the same product in that file and must agree.
- Prices have at most two decimal places.
- Duplicate product/batch pairs (`item_id` and `batch_no`) within the file are rejected.
- Negative quantities are rejected.

---

## Running Automated Tests

Run the complete test suite:

### Windows:
```powershell
py -m unittest -v
```

### macOS / Linux:
```bash
python3 -m unittest -v
```

All 31 unit tests cover importer validation, BST lookup, priority queue ordering, demand regression, restocking math, merge sorting, greedy/knapsack allocation, export generation, and UI components.
