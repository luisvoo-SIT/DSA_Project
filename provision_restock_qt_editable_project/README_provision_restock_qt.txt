Provision Shop Restocking System — Editable Qt GUI

Requirements:
    pip install PySide6 pandas

Run from the folder containing the files:
    python provision_restock_qt.py

Inventory editing:
- Load inventory CSV.
- Double-click a cell to edit its value.
- Click Add row to append a batch/product row.
- Select rows by clicking their row headers (Ctrl/Shift for multiple rows), then click Delete selected row(s).
- Click Save changes to CSV to save the edited inventory to a CSV file.
- You can edit before or after analysis. Any edit invalidates the displayed recommendation; click Run analysis again to refresh it.
- Export restocking plan exports the latest successful analysis.

The sample CSV contains three Monster Energy batches, with one batch expiring in 21 days and 24 units marked as near expiry.
