"""
Restocking Recommendations View with budget allocation, embedded Matplotlib chart,
AVL Tree exact ID search, and linear partial search.
"""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableView, QHeaderView,
    QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QFrame, QMessageBox
)
import pandas as pd
from typing import Dict, List, Optional
from core.models import BatchRecord, ProductRecommendation
from core.restocking import calculate_restocking_recommendations
from core.allocation import allocate_budget
from core.bst import AVLTree
from ui.chart_canvas import MatplotlibCanvas, plot_recommendations_chart


class RecommendationTableModel(QAbstractTableModel):
    """Table model displaying calculated restocking recommendations."""

    COLUMNS = [
        ("rank", "Rank"),
        ("outlet", "Outlet"),
        ("item_id", "Item ID"),
        ("item_name", "Item Name"),
        ("category", "Category"),
        ("unit_cost", "Unit Cost ($)"),
        ("unit_sell", "Unit Sell ($)"),
        ("daily_demand", "Daily Demand"),
        ("target_stock", "Target Stock"),
        ("usable_stock", "Usable Stock"),
        ("expiring_stock", "Expiring Stock"),
        ("need", "Need"),
        ("allocated_units", "Allocated"),
        ("allocated_cost", "Allocated Cost ($)"),
        ("priority_value", "Priority Score"),
        ("value_per_cost", "Value/Cost"),
        ("supplier_rating", "Supplier Rating"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[ProductRecommendation] = []

    def set_items(self, items: List[ProductRecommendation]):
        self.beginResetModel()
        self.items = list(items)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.items)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.items):
            return None

        col_key = self.COLUMNS[index.column()][0]
        rec = self.items[index.row()]
        val = getattr(rec, col_key, None)

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key in ("unit_cost", "unit_sell", "allocated_cost"):
                return f"{float(val):.2f}"
            elif col_key in ("daily_demand", "target_stock"):
                return f"{float(val):.1f}"
            elif col_key in ("usable_stock", "expiring_stock"):
                return f"{int(val)}" if float(val).is_integer() else f"{float(val):.1f}"
            elif col_key in ("rank", "need", "allocated_units", "priority_value"):
                return str(int(val))
            elif col_key == "value_per_cost":
                import math
                return "INF" if math.isinf(val) else f"{float(val):.2f}"
            elif col_key == "supplier_rating":
                return f"{float(val):.1f}"
            return str(val)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("rank", "outlet", "item_id"):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            elif col_key in ("unit_cost", "unit_sell", "daily_demand", "target_stock",
                           "usable_stock", "expiring_stock", "need", "allocated_units",
                           "allocated_cost", "priority_value", "value_per_cost", "supplier_rating"):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "allocated_units" and rec.allocated_units > 0:
                from PySide6.QtGui import QColor
                return QColor("#27ae60")
            elif col_key == "need" and rec.need > 0 and rec.allocated_units == 0:
                from PySide6.QtGui import QColor
                return QColor("#d35400")

        return None


class RecommendationsView(QWidget):
    """
    Recommendations tab with restocking calculation, shared budget allocation,
    embedded Matplotlib chart for the first 20 products, and dual search (BST + Linear).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.master_batches: List[BatchRecord] = []
        self.all_recommendations: List[ProductRecommendation] = []
        self.displayed_recommendations: List[ProductRecommendation] = []
        self.bst_index = AVLTree()

        self.table_model = RecommendationTableModel(self)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Controls Bar
        ctrl_frame = QFrame()
        ctrl_frame.setFrameShape(QFrame.Shape.StyledPanel)
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(8, 6, 8, 6)
        ctrl_layout.setSpacing(12)

        # Budget Input
        ctrl_layout.addWidget(QLabel("Shared Restocking Budget ($):"))
        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setRange(0.0, 100000.0)
        self.budget_spin.setValue(500.0)
        self.budget_spin.setDecimals(2)
        self.budget_spin.setSingleStep(50.0)
        self.budget_spin.setPrefix("$ ")
        ctrl_layout.addWidget(self.budget_spin)

        # Allocation Method
        ctrl_layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItem("Greedy (Rank Order)", "Greedy")
        self.method_combo.addItem("Bounded Knapsack (Max Score)", "Knapsack")
        ctrl_layout.addWidget(self.method_combo)

        # Outlet Selector
        ctrl_layout.addWidget(QLabel("Outlets:"))
        self.outlet_combo = QComboBox()
        self.outlet_combo.addItem("All Outlets (Shared Budget)", "all")
        ctrl_layout.addWidget(self.outlet_combo)

        # Product Search
        ctrl_layout.addWidget(QLabel("Product Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Exact Item ID (BST) or partial text...")
        self.search_edit.setClearButtonEnabled(True)
        ctrl_layout.addWidget(self.search_edit, stretch=1)

        layout.addWidget(ctrl_frame)

        # Metrics / Summary Cards Banner
        self.metrics_label = QLabel()
        self.metrics_label.setStyleSheet(
            "background: #f8f9fa; border: 1px solid #e2e8f0; border-radius: 4px; padding: 6px 12px; font-size: 12px;"
        )
        layout.addWidget(self.metrics_label)

        # Splitter with Chart (top) and Table (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Chart Canvas
        self.chart_canvas = MatplotlibCanvas(self, width=8, height=3.5)
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
        splitter.setSizes([300, 360])

        layout.addWidget(splitter, stretch=1)

        # Connect signals for immediate updates
        self.budget_spin.valueChanged.connect(self.recalculate_and_display)
        self.method_combo.currentIndexChanged.connect(self.recalculate_and_display)
        self.outlet_combo.currentIndexChanged.connect(self.recalculate_and_display)
        self.search_edit.textChanged.connect(self.filter_display_only)

    def set_master_batches(self, batches: List[BatchRecord]):
        self.master_batches = batches
        self._update_outlets_dropdown()
        self.recalculate_and_display()

    def _update_outlets_dropdown(self):
        current = self.outlet_combo.currentData()
        self.outlet_combo.blockSignals(True)
        self.outlet_combo.clear()
        self.outlet_combo.addItem("All Outlets (Shared Budget)", "all")

        outlets = sorted(list({b.outlet for b in self.master_batches}))
        for o in outlets:
            self.outlet_combo.addItem(f"{o} Only", o)

        idx = self.outlet_combo.findData(current)
        if idx != -1:
            self.outlet_combo.setCurrentIndex(idx)
        else:
            self.outlet_combo.setCurrentIndex(0)
        self.outlet_combo.blockSignals(False)

    def recalculate_and_display(self):
        """
        Recalculates restocking recommendations and budget allocation.
        Note requirement: "The budget, allocation method, search and outlet filter update results immediately.
        The search affects the displayed recommendations, not how the selected outlets share the budget."
        """
        if not self.master_batches:
            self.all_recommendations = []
            self.displayed_recommendations = []
            self.table_model.set_items([])
            plot_recommendations_chart(self.chart_canvas, [])
            self.metrics_label.setText("No data loaded. Please import monthly CSV files.")
            return

        # 1. Determine selected outlets for budget sharing
        outlet_data = self.outlet_combo.currentData()
        selected_outlets = None if outlet_data == "all" else [outlet_data]

        # 2. Compute recommendations across selected outlets
        self.all_recommendations = calculate_restocking_recommendations(
            self.master_batches, selected_outlets=selected_outlets
        )

        # 3. Build Balanced BST (AVL Tree) for exact item_id lookup
        self.bst_index.clear()
        # Group by item_id (a product may be at multiple outlets)
        item_groups: Dict[str, List[ProductRecommendation]] = {}
        for r in self.all_recommendations:
            if r.item_id not in item_groups:
                item_groups[r.item_id] = []
            item_groups[r.item_id].append(r)

        for item_id, rec_list in item_groups.items():
            self.bst_index.insert(item_id, rec_list)

        # 4. Allocate Budget across ALL applicable recommendations
        budget = self.budget_spin.value()
        method = self.method_combo.currentData()

        remaining_budget = budget
        try:
            self.all_recommendations, remaining_budget = allocate_budget(
                self.all_recommendations, budget=budget, method=method
            )
        except ValueError as e:
            QMessageBox.warning(self, "Knapsack Budget Limit Exceeded", str(e))
            # Fallback to greedy
            self.method_combo.blockSignals(True)
            self.method_combo.setCurrentIndex(0)
            self.method_combo.blockSignals(False)
            self.all_recommendations, remaining_budget = allocate_budget(
                self.all_recommendations, budget=budget, method="Greedy"
            )

        # 5. Filter display based on search
        self.filter_display_only(remaining_budget=remaining_budget)

    def filter_display_only(self, remaining_budget: Optional[float] = None):
        """
        Filters what is displayed in recommendation chart and table without affecting budget allocation.
        Uses AVL Tree for exact product ID lookup; linear search for partial matches.
        """
        query = self.search_edit.text().strip()

        if not query:
            self.displayed_recommendations = list(self.all_recommendations)
        else:
            # Check exact product ID lookup using balanced BST (AVL Tree)
            exact_match = self.bst_index.search(query)
            if exact_match is not None:
                # Found exact product ID in AVL Tree!
                self.displayed_recommendations = list(exact_match)
            else:
                # Partial search uses linear search over item_id, item_name, category
                q_lower = query.lower()
                self.displayed_recommendations = [
                    r for r in self.all_recommendations
                    if q_lower in r.item_id.lower() or q_lower in r.item_name.lower() or q_lower in r.category.lower()
                ]

        # Update Table Model
        self.table_model.set_items(self.displayed_recommendations)

        # Update Chart: "shows need and allocation for the first 20 ranked, displayed products"
        plot_recommendations_chart(self.chart_canvas, self.displayed_recommendations, top_n=20)

        # Update Summary Metrics
        total_budget = self.budget_spin.value()
        total_spent = sum(r.allocated_cost for r in self.all_recommendations)
        rem = total_budget - total_spent if remaining_budget is None else remaining_budget
        total_units = sum(r.allocated_units for r in self.all_recommendations)
        prods_allocated = sum(1 for r in self.all_recommendations if r.allocated_units > 0)
        total_prods = len(self.all_recommendations)

        self.metrics_label.setText(
            f"<b>Budget:</b> ${total_budget:,.2f} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Allocated Spend:</b> ${total_spent:,.2f} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Remaining:</b> ${rem:,.2f} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Total Units Restocked:</b> {total_units:,} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Products Funded:</b> {prods_allocated} of {total_prods} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Displayed:</b> {len(self.displayed_recommendations)} products"
        )

    def get_all_recommendations(self) -> List[ProductRecommendation]:
        """Returns all calculated recommendations for export."""
        return self.all_recommendations
