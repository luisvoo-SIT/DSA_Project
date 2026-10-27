Provision Shop Restocking GUI — labelled live execution flow

Requirements:
  python -m pip install PySide6 pandas

Run:
  python provision_restock_qt_live_execution.py

The Qt Graphics View flowchart uses explicit labels for each node and branch:
- Start -> load inventory CSV -> validate required columns/numeric values -> CSV valid?
- NO returns to load/correct CSV; YES continues through aggregation, balanced-tree lookup,
  expiry priority queue, linear-regression forecast + merge-sort ranking, budget allocation,
  and within-budget decision.
- Over-budget routes to adjustment and a retry loop to budget allocation.
- Within-budget offers the restocking plan export.

Nodes are clickable for details. Ctrl+mouse-wheel zooms; drag pans; Fit flowchart resets view.
Inventory editing, adding/deleting rows, CSV saving, analysis and export are retained.

Note: the flowchart labels describe the intended algorithm stages. Check the actual algorithm implementation before presenting the software as implementing balanced trees, priority queues, linear regression, merge sort, or both allocation methods; the existing analysis implementation may still use simplified pandas-based calculations/sorting.
