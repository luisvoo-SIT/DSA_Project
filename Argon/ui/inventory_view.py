"""
Editable Inventory View with Pandas filtering, numeric sorting, and batch synchronization.
"""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QTableView, QHeaderView, QMessageBox, QFrame
)
import pandas as pd
from typing import Dict, List, Optional
from core.models import BatchRecord, parse_batch_dates
from core.bst import AVLTree


class BatchTableModel(QAbstractTableModel):
    """
    QAbstractTableModel backed by a Pandas DataFrame and synchronized
    with in-memory BatchRecord list.
    """
    dataModified = Signal()

    COLUMNS = [
        ("outlet", "Outlet", False),
        ("report_month_str", "Report Month", False),
        ("item_id", "Item ID", False),
        ("item_name", "Item Name", True),
        ("category", "Category", True),
        ("unit_cost", "Unit Cost ($)", True),
        ("unit_sell", "Unit Sell ($)", True),
        ("current_total_stock", "Stock", True),
        ("mth_purchase", "Mth Purchase", True),
        ("mth_expired", "Mth Expired", True),
        ("lead_time", "Lead Time (d)", True),
        ("shelf_life", "Shelf Life (d)", True),
        ("batch_no", "Batch No", False),
        ("supplier_rating", "Rating (0-5)", True),
        ("remaining_shelf_life", "Remaining Life (d)", False),
        ("status_label", "Status", False),
    ]

    def __init__(self, master_batches: List[BatchRecord], parent=None):
        super().__init__(parent)
        self.master_batches = master_batches
        self.df_display = pd.DataFrame()
        self.rebuild_dataframe()

    def rebuild_dataframe(self, df_filtered: Optional[pd.DataFrame] = None):
        """Rebuilds the underlying dataframe from master batches or uses filtered df."""
        self.beginResetModel()
        if df_filtered is not None:
            self.df_display = df_filtered.copy()
        else:
            rows = []
            for b in self.master_batches:
                rows.append({
                    "outlet": b.outlet,
                    "report_year": b.report_year,
                    "report_month": b.report_month,
                    "report_month_str": b.report_month_str,
                    "item_id": b.item_id,
                    "item_name": b.item_name,
                    "category": b.category,
                    "unit_cost": b.unit_cost,
                    "unit_sell": b.unit_sell,
                    "current_total_stock": b.current_total_stock,
                    "mth_purchase": b.mth_purchase,
                    "mth_expired": "" if b.mth_expired is None else b.mth_expired,
                    "lead_time": b.lead_time,
                    "shelf_life": b.shelf_life,
                    "batch_no": b.batch_no,
                    "supplier_rating": b.supplier_rating,
                    "remaining_shelf_life": b.remaining_shelf_life,
                    "is_expiring": b.is_expiring,
                    "status_label": "EXPIRING" if b.is_expiring else "USABLE",
                    "batch_ref": b,
                })
            self.df_display = pd.DataFrame(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.df_display)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section][1]
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        col_key, _, editable = self.COLUMNS[index.column()]
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.df_display):
            return None

        col_key = self.COLUMNS[index.column()][0]
        val = self.df_display.iloc[index.row()][col_key]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col_key in ("unit_cost", "unit_sell"):
                return f"{float(val):.2f}"
            elif col_key in ("current_total_stock", "mth_purchase"):
                return f"{int(val)}" if float(val).is_integer() else f"{float(val):.1f}"
            elif col_key == "mth_expired":
                return "" if (val == "" or val is None or int(val) < 0) else str(int(val))
            elif col_key == "supplier_rating":
                return f"{float(val):.1f}"
            elif col_key in ("remaining_shelf_life", "lead_time", "shelf_life"):
                return str(int(val))
            return str(val)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("unit_cost", "unit_sell", "current_total_stock", "mth_purchase", "mth_expired",
                           "lead_time", "shelf_life", "supplier_rating", "remaining_shelf_life"):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            elif col_key in ("status_label", "report_month_str", "batch_no"):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "status_label":
                from PySide6.QtGui import QColor
                is_exp = self.df_display.iloc[index.row()]["is_expiring"]
                return QColor("#c0392b" if is_exp else "#27ae60")

        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        col_key, _, editable = self.COLUMNS[index.column()]
        if not editable:
            return False

        row_idx = index.row()
        batch: BatchRecord = self.df_display.iloc[row_idx]["batch_ref"]
        str_val = str(value).strip()

        try:
            if col_key == "mth_purchase":
                new_val = float(str_val)
                if new_val < 0:
                    raise ValueError("Monthly purchase cannot be negative.")
                # Requirement: editing monthly purchases updates all batches for that product in that file
                target_outlet = batch.outlet
                target_year = batch.report_year
                target_month = batch.report_month
                target_item = batch.item_id

                for b in self.master_batches:
                    if (b.outlet == target_outlet and b.report_year == target_year and
                        b.report_month == target_month and b.item_id == target_item):
                        b.mth_purchase = new_val

            elif col_key == "mth_expired":
                if str_val == "":
                    new_exp = None
                else:
                    if not str_val.isdigit():
                        raise ValueError("Monthly expired units must be blank or a non-negative integer.")
                    new_exp = int(str_val)
                for b in self.master_batches:
                    if (b.outlet == batch.outlet and b.report_year == batch.report_year and
                        b.report_month == batch.report_month and b.item_id == batch.item_id):
                        b.mth_expired = new_exp

            elif col_key == "item_name":
                if not str_val:
                    raise ValueError("Item name cannot be empty.")
                batch.item_name = str_val
                # Keep consistent across batches of same product in file
                for b in self.master_batches:
                    if b.outlet == batch.outlet and b.item_id == batch.item_id:
                        b.item_name = str_val

            elif col_key == "category":
                batch.category = str_val
                for b in self.master_batches:
                    if b.outlet == batch.outlet and b.item_id == batch.item_id:
                        b.category = str_val

            elif col_key == "unit_cost":
                if "." in str_val and len(str_val.split(".")[1]) > 2:
                    raise ValueError("Price has more than 2 decimal places.")
                new_val = float(str_val)
                if new_val < 0:
                    raise ValueError("Unit cost cannot be negative.")
                batch.unit_cost = new_val

            elif col_key == "unit_sell":
                if "." in str_val and len(str_val.split(".")[1]) > 2:
                    raise ValueError("Price has more than 2 decimal places.")
                new_val = float(str_val)
                if new_val < 0:
                    raise ValueError("Unit sell cannot be negative.")
                batch.unit_sell = new_val

            elif col_key == "current_total_stock":
                new_val = float(str_val)
                if new_val < 0:
                    raise ValueError("Stock cannot be negative.")
                batch.current_total_stock = new_val

            elif col_key == "lead_time":
                new_val = int(str_val)
                if new_val < 0:
                    raise ValueError("Lead time cannot be negative.")
                # Validate delivery date doesn't exceed report date
                parse_batch_dates(batch.batch_no, new_val, batch.shelf_life, batch.report_year, batch.report_month)
                batch.lead_time = new_val
                # Recompute batch dates
                batch.__post_init__()

            elif col_key == "shelf_life":
                new_val = int(str_val)
                if new_val < 0:
                    raise ValueError("Shelf life cannot be negative.")
                batch.shelf_life = new_val
                batch.__post_init__()

            elif col_key == "supplier_rating":
                new_val = float(str_val)
                if new_val < 0.0 or new_val > 5.0:
                    raise ValueError("Supplier rating must be between 0 and 5.")
                batch.supplier_rating = new_val

            self.dataModified.emit()
            return True

        except Exception as e:
            QMessageBox.warning(None, "Invalid Edit", str(e))
            return False


class InventoryView(QWidget):
    """
    Inventory tab widget containing filter/sort toolbar and editable table view.
    """
    filterChanged = Signal()
    dataEdited = Signal()

    def __init__(self, master_batches: List[BatchRecord], parent=None):
        super().__init__(parent)
        self.master_batches = master_batches
        self.table_model = BatchTableModel(self.master_batches, self)
        self.table_model.dataModified.connect(self._on_model_modified)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Filter / Sort Controls Frame
        ctrl_frame = QFrame()
        ctrl_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(8, 6, 8, 6)
        ctrl_layout.setSpacing(10)

        # Search Column
        ctrl_layout.addWidget(QLabel("Search in:"))
        self.col_combo = QComboBox()
        self.col_combo.addItem("All Columns", "all")
        for key, name, _ in BatchTableModel.COLUMNS:
            self.col_combo.addItem(name, key)
        ctrl_layout.addWidget(self.col_combo)

        # Search Query
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter inventory...")
        self.search_edit.setClearButtonEnabled(True)
        ctrl_layout.addWidget(self.search_edit, stretch=1)

        # Sort Column
        ctrl_layout.addWidget(QLabel("Sort by:"))
        self.sort_col_combo = QComboBox()
        for key, name, _ in BatchTableModel.COLUMNS:
            self.sort_col_combo.addItem(name, key)
        ctrl_layout.addWidget(self.sort_col_combo)

        # Sort Order
        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItem("Ascending", True)
        self.sort_order_combo.addItem("Descending", False)
        ctrl_layout.addWidget(self.sort_order_combo)

        # Outlet Filter
        ctrl_layout.addWidget(QLabel("Outlet:"))
        self.outlet_combo = QComboBox()
        self.outlet_combo.addItem("All Outlets", "all")
        ctrl_layout.addWidget(self.outlet_combo)

        layout.addWidget(ctrl_frame)

        # Table View
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_view, stretch=1)

        # Connections
        self.search_edit.textChanged.connect(self.apply_filter_sort)
        self.col_combo.currentIndexChanged.connect(self.apply_filter_sort)
        self.sort_col_combo.currentIndexChanged.connect(self.apply_filter_sort)
        self.sort_order_combo.currentIndexChanged.connect(self.apply_filter_sort)
        self.outlet_combo.currentIndexChanged.connect(self.apply_filter_sort)

    def _on_model_modified(self):
        self.apply_filter_sort()
        self.dataEdited.emit()

    def update_outlets(self):
        """Updates the outlet dropdown based on loaded master batches."""
        current = self.outlet_combo.currentData()
        self.outlet_combo.blockSignals(True)
        self.outlet_combo.clear()
        self.outlet_combo.addItem("All Outlets", "all")

        outlets = sorted(list({b.outlet for b in self.master_batches}))
        for o in outlets:
            self.outlet_combo.addItem(o, o)

        # Restore previous selection if still valid
        idx = self.outlet_combo.findData(current)
        if idx != -1:
            self.outlet_combo.setCurrentIndex(idx)
        else:
            self.outlet_combo.setCurrentIndex(0)

        self.outlet_combo.blockSignals(False)

    def refresh(self):
        self.update_outlets()
        self.apply_filter_sort()

    def apply_filter_sort(self):
        """Filters and sorts master batches using Pandas DataFrame."""
        if not self.master_batches:
            self.table_model.rebuild_dataframe(pd.DataFrame())
            self.filterChanged.emit()
            return

        # Build full dataframe from master batches
        rows = []
        for b in self.master_batches:
            rows.append({
                "outlet": b.outlet,
                "report_year": b.report_year,
                "report_month": b.report_month,
                "report_month_str": b.report_month_str,
                "item_id": b.item_id,
                "item_name": b.item_name,
                "category": b.category,
                "unit_cost": float(b.unit_cost),
                "unit_sell": float(b.unit_sell),
                "current_total_stock": float(b.current_total_stock),
                "mth_purchase": float(b.mth_purchase),
                "mth_expired": -1 if b.mth_expired is None else int(b.mth_expired),
                "lead_time": int(b.lead_time),
                "shelf_life": int(b.shelf_life),
                "batch_no": b.batch_no,
                "supplier_rating": float(b.supplier_rating),
                "remaining_shelf_life": int(b.remaining_shelf_life),
                "is_expiring": bool(b.is_expiring),
                "status_label": "EXPIRING" if b.is_expiring else "USABLE",
                "batch_ref": b,
            })
        df = pd.DataFrame(rows)

        # 1. Outlet Filter
        selected_outlet = self.outlet_combo.currentData()
        if selected_outlet and selected_outlet != "all":
            df = df[df["outlet"] == selected_outlet]

        # 2. Text Search Filter
        query = self.search_edit.text().strip().lower()
        search_col = self.col_combo.currentData()

        if query:
            if search_col == "all":
                # Match query across all string representations of columns
                mask = pd.Series([False] * len(df), index=df.index)
                for col_key, _, _ in BatchTableModel.COLUMNS:
                    mask = mask | df[col_key].astype(str).str.lower().str.contains(query, na=False)
                df = df[mask]
            else:
                if search_col in df.columns:
                    mask = df[search_col].astype(str).str.lower().str.contains(query, na=False)
                    df = df[mask]

        # 3. Sorting (Numeric columns sorted numerically)
        sort_col = self.sort_col_combo.currentData()
        ascending = self.sort_order_combo.currentData()
        if sort_col in df.columns:
            df = df.sort_values(by=sort_col, ascending=ascending)

        self.table_model.rebuild_dataframe(df)
        self.filterChanged.emit()

    def get_filtered_dataframe(self) -> pd.DataFrame:
        """Returns the currently filtered & sorted DataFrame."""
        return self.table_model.df_display.copy()
