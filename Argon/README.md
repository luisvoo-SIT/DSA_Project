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
  - Target stock covering supplier lead time plus 30 days. Expiring stock ($\le 14$ days remaining) is strictly excluded from usable inventory.
  - Restocking need capped at forecast sales over the product's shelf life.
  - Illustrative additive priority value per unit: 100 points for availability plus 1 point per cent of non-negative gross margin.
  - Explicit **Merge Sort** ranking items by value per cost.
  - Shared budget allocation across selected outlets:
    - **Greedy Allocation**: Buys in rank order up to the shared budget limit.
    - **Bounded Knapsack Allocation**: Dynamic programming optimization maximizing total additive priority score using integer cents and discrete unit quantities (supported for budgets up to \$1,000.00).
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
