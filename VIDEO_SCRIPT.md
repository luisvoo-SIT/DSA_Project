# Market Expand: Video Presentation & Live Demo Script (13:30 Timed for 15:00 Max)

> [!TIP]
> **Pacing & 15-Minute Maximum Budget**:
> - At a natural speaking pace of **130 words per minute**, the spoken script below is **~1,210 words (~9 minutes 15 seconds of speaking)** plus **~4 minutes 15 seconds of live GUI & terminal demo actions**, totaling **13 minutes 30 seconds** (leaving a safe **1:30 buffer** before the hard 15:00 cutoff).
> - Follow the **`[DEMO / SCREEN CUE]`** lines in brackets to coordinate your clicks with the narration.

| Segment | Topic | Spoken Time | Demo Action Time | Segment Total | Cumulative Time |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **1** | Problem Scenario & Dual Architecture (`Argon/` & `GPT/`) | 1:30 | 0:15 | **1:45** | 0:00 – 1:45 |
| **2** | CSV Validation, `mth_expired` & Live Table Batch Sync | 1:30 | 1:00 | **2:30** | 1:45 – 4:15 |
| **3** | Min-Heap Priority Queue & Batch Expiry Inspection | 1:25 | 0:45 | **2:10** | 4:15 – 6:25 |
| **4** | OLS Linear Regression, 75% Expiry Replacement & Merge Sort | 1:45 | 0:35 | **2:20** | 6:25 – 8:45 |
| **5** | Balanced Base + Greedy/Knapsack, `As of` Series & AVL Search | 1:35 | 1:00 | **2:35** | 8:45 – 11:20 |
| **6** | Process Flowchart, Unit Tests (`44` + `20`) & GenAI Comparison | 1:30 | 0:40 | **2:10** | 11:20 – 13:30 |

---

## Pre-Recording Setup (Do Before Hitting Record)

1. Open a terminal in [`/Users/tancheehui/SitCodingWork/DSA_Project/Argon`](file:///Users/tancheehui/SitCodingWork/DSA_Project/Argon) and launch the app so the window is already open:
   ```bash
   python3 app.py
   ```
2. Have your code editor open to [`/Users/tancheehui/SitCodingWork/DSA_Project`](file:///Users/tancheehui/SitCodingWork/DSA_Project) with `Argon/core/` and `GPT/` expanded in the sidebar.

---

## Segment 1: Introduction, Problem Statement & Architecture (0:00 – 1:45)
*(Speaker 1 — ~195 words, 1:30 speaking + 0:15 screen navigation)*

**[DEMO / SCREEN CUE (0:00): Show the Market Expand GUI side-by-side with the IDE file explorer showing `Argon/` and `GPT/`.]**

"Hi everyone, and welcome to our RSE2203 Data Structures and Algorithms presentation. We are presenting **Market Expand**, a Python desktop application built with PySide6, Pandas, and Matplotlib for multi-outlet perishable inventory management and shared restocking budget allocation.

Grocery chains selling perishable goods—like fresh milk, bakery items, and beverages—receive inventory in discrete monthly batches, each with its own order date, supplier lead time, and shelf life. Managing these in plain spreadsheets creates three major problems:
- First, expired and near-expiry batches get mixed in with fresh stock, hiding waste and inflating usable inventory counts.
- Second, if an overstocked store replaces 100 percent of expired units every month, slow-moving products keep expiring; but cutting orders to zero causes sudden stockouts.
- Third, purely score-maximizing budget algorithms spend everything on a few top items, leaving the rest of the store assortment empty. Planners need a way to combine **catalog-wide variety** with **priority optimization** across availability, popularity, and profit objectives."

**[DEMO / SCREEN CUE (1:15): Point briefly to `Argon/core/`, `Argon/ui/`, and `GPT/` in the IDE sidebar.]**

"To solve this, `Argon/core/` implements all data structures and algorithms from scratch in pure Python, while `Argon/ui/` provides a PySide6 Model-View-Controller interface. We also maintain both our Gemini codebase in `Argon/` and our ChatGPT codebase in `GPT/` for side-by-side GenAI evaluation."

---

## Segment 2: CSV Validation, `mth_expired` & Live Batch Sync (1:45 – 4:15)
*(Speaker 2 — ~195 words, 1:30 speaking + 1:00 live import & edit demo)*

**[DEMO / SCREEN CUE (1:45): Show `Argon/core/csv_importer.py` in the IDE (`parse_filename` and `import_monthly_csv`).]**

"Let's look at data ingestion in `csv_importer.py`. Each file is named `Outlet_Name_YYYY_MM.csv`, anchoring the snapshot date to the last calendar day of that reporting month. Every row is a product batch containing eleven required fields plus an optional `mth_expired` column that records actual monthly expiry losses, including stock already disposed of.

Our importer enforces five validation rules:
1. `batch_no` must be four-digit `MMYY` text preserving leading zeroes.
2. Duplicate `(item_id, batch_no)` pairs in a file are rejected.
3. Quantities cannot be negative, ratings must be 0 to 5, and prices allow at most two decimal places.
4. Both `mth_purchase` and `mth_expired` represent monthly product totals, so all batches of the same product in a file must agree.
5. Assumed delivery is the last day of `MMYY` plus `lead_time` days; any batch delivered after the report date is rejected."

**[DEMO / SCREEN CUE (2:45): Switch to the GUI. Click 'Import monthly CSV', import the 5 files in `Argon/sample_data/expiry_series/` (`Outlet_ExpirySeries_2026_07.csv` through `11.csv`), and show the 'Monthly Inventory' tab.]**

"In the GUI, I'll import the five monthly files from `sample_data/expiry_series/`. Using Pandas, we can filter by outlet or column and sort numeric columns numerically.

Now watch the live batch synchronization: in July 2026, this product has two batch rows, both showing `40` in `Mth Expired`."

**[DEMO / SCREEN CUE (3:35): Double-click `Mth Expired` on one July row, change `40` to `20`, press Enter to show both July rows update to `20`, then change it back to `40`.]**

"When I edit `Mth Expired` or `Mth Purchase` on a single batch row, `BatchTableModel.setData()` automatically synchronizes all sibling batches for that product and month in memory and updates our recommendations immediately."

---

## Segment 3: Min-Heap Priority Queue & Batch Expiry View (4:15 – 6:25)
*(Speaker 3 — ~185 words, 1:25 speaking + 0:45 GUI tab demo)*

**[DEMO / SCREEN CUE (4:15): Open `Argon/core/priority_queue.py` in the IDE.]**

"Next, `priority_queue.py` handles batch expiry inspection. A batch's expiry date is its delivery date plus `shelf_life` days, and its remaining shelf life is `expiry_date - report_date`. Batches with `0` or fewer days left are expired and excluded from available stock, while batches with `1` to `14` days remaining stay available but are flagged as near-expiry for review.

To present batches in First-Expired, First-Out order without re-sorting a full list from scratch, `BatchPriorityQueue` uses a binary min-heap (`heapq`). On line 23, each batch is pushed with a four-element tuple key:
`(batch.remaining_shelf_life, batch.delivery_date, batch.item_id, self._counter)`
Including the monotonic integer `self._counter` guarantees that if two snapshots tie on the first three fields, Python never attempts to compare `BatchRecord` dataclass instances directly. Peeking at the most urgent batch is $O(1)$, each push or pop is $O(\log n)$, and draining $n$ batches takes $O(n \log n)$ time."

**[DEMO / SCREEN CUE (5:25): Switch to the GUI and click the 'Batch Expiry Inspection' tab.]**

"In the **Batch Expiry Inspection** tab, the table lists batches popped from our min-heap earliest first, highlighting expired and near-expiry rows in red along with their report month. Above the table, our embedded Matplotlib chart uses Pandas `pd.cut()` to aggregate batch quantities across shelf-life tiers from `Expired (<= 0d)` and `Expiring Soon (1-14d)` up to `Fresh (> 90d)`."

---

## Segment 4: OLS Linear Regression, 75% Expiry Replacement & Merge Sort (6:25 – 8:45)
*(Speaker 4 — ~225 words, 1:45 speaking + 0:35 code highlight)*

**[DEMO / SCREEN CUE (6:25): Open `Argon/core/forecasting.py` and `Argon/core/restocking.py` in the IDE.]**

"Now let's look at demand forecasting and our 75 percent partial expiry replacement rule in `forecasting.py` and `restocking.py`.

First, for the **Popularity** objective, `predict_demand()` fits an Ordinary Least Squares linear regression line across historical monthly sales per outlet. On line 7 of `forecasting.py`, we map each `(year, month)` to a continuous calendar month index `12 * year + month`. If an outlet skips a month, the index gap is 2 rather than 1, so the slope accounts for the missing month without treating it as zero sales. Predictions for `latest_x + 1` are clamped at zero.

Second, in `restocking.py`, we solve the overstocking problem using one transparent partial replacement rule:
- `expired_replacement = floor(expired_this_month * 75%)`
- `need = latest_sales + expired_replacement`
- `new_total_target = usable_stock + need`
If `mth_expired` is provided in the CSV, we use it directly; otherwise, `calculate_monthly_expired_units()` estimates losses only from batches whose expiry date falls within that reporting month, so older retained expired stock is never double-counted. Because we replace 100 percent of units sold but only 75 percent of expired losses, an overstocked item naturally steps down its total stock target month over month until expiry waste reaches zero.

Third, planners can choose between three unit-scoring objectives:
- **Availability + margin** (default): `100 + nonnegative margin cents`
- **Popularity**: `round(forecast_monthly_sales * 100)`
- **Profit**: `nonnegative margin cents`"

**[DEMO / SCREEN CUE (8:10): Open `Argon/core/sorting.py` in the IDE.]**

"Finally, `sorting.py` ranks all candidate products descending by `value_per_cost` using recursive **Merge Sort**, guaranteeing $O(n \log n)$ worst-case time and stable, deterministic tie-breaking across outlets."

---

## Segment 5: Live Demo — `As of` Series, Two-Stage Balanced Base & AVL Search (8:45 – 11:20)
*(Speaker 5 — ~215 words, 1:35 speaking + 1:00 live GUI demo)*

**[DEMO / SCREEN CUE (8:45): Switch to the GUI 'Restocking Recommendations' tab with `Outlet_ExpirySeries` loaded. Set Budget to `$1000.00`, open 'As of:', and click through `2026-07` to `2026-11`.]**

"Let's watch that 75 percent replacement rule work live in the **Restocking Recommendations** tab using the **As of** month selector on `Outlet_ExpirySeries`:
- In **July 2026**, starting with 50 units, 7 sell and 40 expire, leaving 3 available. Buying `7 + floor(40 * 0.75) = 37` units steps the **New Target** down from 50 to **40**.
- Stepping **As of** through **August**, **September**, **October**, and **November** lowers the target smoothly from **40 to 34, 30, and 27**, where monthly expired units drop to **0**."

**[DEMO / SCREEN CUE (9:30): Import `Outlet_Youth_2026_09.csv` from `Argon/sample_data/`. Select `Outlet_Youth Only`, set Budget to `$600.00`, set 'Balanced Base (%)' to `0%`, then increase 'Balanced Base (%)' to `50%`, and toggle Method among `Greedy`, `Bounded Knapsack`, and `Balanced Budget (Even Distribution)`.]**

"Next, in `allocation.py`, we integrated a two-stage **Balanced Base (%)** share into **Greedy** and **Bounded Knapsack** alongside a standalone **Balanced Budget** mode:
- At **0% Balanced Base**, pure Greedy spends the entire $\$600.00$ budget on just **4 of the 40 products** in `Outlet_Youth`.
- When I set **Balanced Base (%)** to **50%**, Stage 1 distributes the first $\$300.00$ evenly across the catalog—funding **all 40 of 40 products**—and returns any unspent cents to Stage 2, where **Greedy** or **Bounded Knapsack DP** (binary splitting `1, 2, 4, ...` up to $\$1,000.00$) optimizes the remaining $\$300.00$ across unmet needs!"

**[DEMO / SCREEN CUE (10:40): Type `DEMO001` into the Search box, pause, then type `Monster`, then clear the Search box.]**

"For product search, typing an exact SKU like `DEMO001` queries our self-balancing **AVL Tree** (`core/bst.py`) in $O(\log n)$ time via LL, RR, LR, and RL rotations, while partial keywords like `Monster` fall back to $O(n)$ **Linear Search** without altering how outlets share the budget."

---

## Segment 6: Process Flowchart, Unit Tests (`44` + `20`) & GenAI Comparison (11:20 – 13:30)
*(Speaker 6 — ~195 words, 1:30 speaking + 0:40 flowchart & terminal demo)*

**[DEMO / SCREEN CUE (11:20): Click 'Process Diagram' in the top toolbar. Drag a node on the left canvas, and adjust 'Expired This Mth' or 'Balanced Base (%)' in the right-hand 'Live Illustrative Calculation Panel'.]**

"Clicking **Process Diagram** on the toolbar opens our editable `QGraphicsScene` workflow window (`flowchart_view.py`). Users can rearrange or edit flowchart nodes on the left, while the **Live Illustrative Calculation Panel** on the right lets users adjust sales, `Expired This Mth`, and `Balanced Base (%)` to inspect the 75 percent replacement math and two-stage budget split live."

**[DEMO / SCREEN CUE (11:55): Switch to the Terminal in `DSA_Project/Argon` and run `python3 -m unittest -v`.]**

"In the terminal, running `python3 -m unittest -v` executes our **44 automated unit and offscreen GUI tests** in `Argon/tests/` (alongside **20 tests** in `GPT/test_restocking_modes.py`—64 tests total), completing in 1.8 seconds with 100 percent passing results.

Finally, comparing our **ChatGPT (`GPT/`)** and **Gemini (`Argon/`)** codebases across the four RSE2203 GenAI criteria taught us three key engineering lessons:
- **Accuracy & Algorithmic Design**: ChatGPT used a `(spent_cents, index)` min-heap for spend balancing and a background `QThreadPool` worker for its pure-Python dictionary Knapsack solver, whereas `Argon/` used equal-dollar water-filling plus round-robin, a true rotation-based `AVLTree`, a collision-safe heap counter `self._counter`, and a vectorized 1D/2D `numpy` Knapsack array that solves a 100-item, $\$1,000.00$ Knapsack in just **65 milliseconds**.
- **Completeness & Clarity**: Both codebases pass 100 percent of their test suites (`44` in `Argon/` and `20` in `GPT/`), while `Argon/`'s 16-module MVC layout with `QAbstractTableModel` classes was much cleaner for our team to maintain than `GPT/`'s compact 3-file script layout.

Thank you for watching our presentation!"
