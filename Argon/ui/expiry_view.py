"""
Expiry View displaying batch expiry priority queue table and Matplotlib distribution chart.
"""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableView, QHeaderView, QLabel, QFrame
)
import pandas as pd
from typing import List, Optional
from core.models import BatchRecord
from core.priority_queue import BatchPriorityQueue
from ui.chart_canvas import MatplotlibCanvas, plot_expiry_distribution


class ExpiryTableModel(QAbstractTableModel):
    """
    Table model for batch expiry inspection, showing report month and expiry details.
    """
    COLUMNS = [
        ("report_month_str", "Report Month"),
        ("outlet", "Outlet"),
        ("item_id", "Item ID"),
        ("item_name", "Item Name"),
        ("category", "Category"),
        ("batch_no", "Batch No"),
        ("current_total_stock", "Stock"),
        ("delivery_date", "Delivery Date"),
        ("expiry_date", "Expiry Date"),
        ("remaining_shelf_life", "Remaining Life (d)"),
        ("status_label", "Expiring Status"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.df_display = pd.DataFrame()

    def set_data(self, df: pd.DataFrame):
        self.beginResetModel()
        self.df_display = df.copy()
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

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.df_display):
            return None

        col_key = self.COLUMNS[index.column()][0]
        val = self.df_display.iloc[index.row()][col_key]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key == "current_total_stock":
                return f"{int(val)}" if float(val).is_integer() else f"{float(val):.1f}"
            elif col_key == "remaining_shelf_life":
                return str(int(val))
            elif col_key in ("delivery_date", "expiry_date"):
                return str(val)
            return str(val)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("current_total_stock", "remaining_shelf_life"):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            elif col_key in ("report_month_str", "batch_no", "status_label", "delivery_date", "expiry_date"):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "status_label":
                from PySide6.QtGui import QColor
                is_exp = self.df_display.iloc[index.row()]["is_expiring"]
                return QColor("#c0392b" if is_exp else "#27ae60")

        return None


class ExpiryView(QWidget):
    """
    Expiry inspection tab featuring priority queue ordered table and embedded Matplotlib chart.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table_model = ExpiryTableModel(self)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header info
        info_label = QLabel(
            "<b>Batch Expiry Inspection:</b> Batches prioritized earliest remaining shelf life first via Min-Heap Priority Queue. "
            "Batches with 14 days or less remaining (including expired units) are flagged as expiring."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #555; padding: 4px;")
        layout.addWidget(info_label)

        # Splitter between Chart and Table
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Matplotlib Chart Canvas
        self.chart_canvas = MatplotlibCanvas(self, width=8, height=3)
        splitter.addWidget(self.chart_canvas)

        # Table View
        table_container = QWidget()
        t_layout = QVBoxLayout(table_container)
        t_layout.setContentsMargins(0, 4, 0, 0)
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        t_layout.addWidget(self.table_view)

        splitter.addWidget(table_container)
        splitter.setSizes([260, 400])

        layout.addWidget(splitter, stretch=1)

    def update_view(self, filtered_df: pd.DataFrame, master_batches: List[BatchRecord]):
        """
        Updates the expiry view from filtered inventory dataframe.
        Applies Priority Queue to order batches earliest remaining shelf life first.
        """
        # Expiry chart groups batch quantities by remaining shelf life
        plot_expiry_distribution(self.chart_canvas, filtered_df)

        if filtered_df.empty:
            self.table_model.set_data(pd.DataFrame())
            return

        # Use Priority Queue (earliest remaining shelf life first)
        pq = BatchPriorityQueue()
        for _, row in filtered_df.iterrows():
            batch = row.get("batch_ref")
            if batch:
                pq.push(batch)

        sorted_batches = pq.to_sorted_list()

        # Build table rows from priority-queue ordered batches
        rows = []
        for b in sorted_batches:
            rows.append({
                "report_month_str": b.report_month_str,
                "outlet": b.outlet,
                "item_id": b.item_id,
                "item_name": b.item_name,
                "category": b.category,
                "batch_no": b.batch_no,
                "current_total_stock": b.current_total_stock,
                "delivery_date": b.delivery_date,
                "expiry_date": b.expiry_date,
                "remaining_shelf_life": b.remaining_shelf_life,
                "is_expiring": b.is_expiring,
                "status_label": "EXPIRING (<=14d)" if b.is_expiring else "USABLE",
            })

        df_sorted = pd.DataFrame(rows)
        self.table_model.set_data(df_sorted)
