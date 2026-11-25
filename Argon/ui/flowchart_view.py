"""
Editable Process Diagram (Flowchart) and Live Illustrative Calculation Panel.
"""
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsRectItem, QGraphicsPathItem, QPushButton,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QSplitter,
    QInputDialog, QMessageBox, QTextEdit, QFrame, QToolBar
)
import math
from typing import List, Optional
from core.forecasting import predict_demand


class FlowchartNodeItem(QGraphicsRectItem):
    """Draggable, selectable visual node representing a process step."""

    def __init__(self, step_num: int, title: str, description: str, x: float, y: float, w: float = 200, h: float = 80):
        super().__init__(0, 0, w, h)
        self.step_num = step_num
        self.title = title
        self.description = description
        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background color
        is_selected = self.isSelected()
        bg_color = QColor("#ebf5fb") if not is_selected else QColor("#d4efdf")
        border_color = QColor("#2980b9") if not is_selected else QColor("#27ae60")
        border_width = 2.0 if not is_selected else 3.0

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, border_width))
        rect = self.rect()
        painter.drawRoundedRect(rect, 8, 8)

        # Header badge
        badge_rect = QRectF(rect.x() + 8, rect.y() + 8, 22, 22)
        painter.setBrush(QBrush(border_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(badge_rect)

        painter.setPen(QPen(Qt.GlobalColor.white))
        font_badge = QFont("Arial", 9, QFont.Weight.Bold)
        painter.setFont(font_badge)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(self.step_num))

        # Title text
        painter.setPen(QPen(QColor("#2c3e50")))
        font_title = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font_title)
        title_rect = QRectF(rect.x() + 36, rect.y() + 8, rect.width() - 42, 22)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)

        # Description text
        painter.setPen(QPen(QColor("#555555")))
        font_desc = QFont("Arial", 8)
        painter.setFont(font_desc)
        desc_rect = QRectF(rect.x() + 10, rect.y() + 34, rect.width() - 20, rect.height() - 38)
        painter.drawText(desc_rect, Qt.TextFlag.TextWordWrap, self.description)


class ConnectionArrow(QGraphicsPathItem):
    """Draws an arrow connecting two flowchart nodes."""

    def __init__(self, start_node: FlowchartNodeItem, end_node: FlowchartNodeItem):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.setZValue(-1)
        self.update_path()

    def update_path(self):
        p1 = self.start_node.pos() + QPointF(self.start_node.rect().width() / 2, self.start_node.rect().bottom())
        p2 = self.end_node.pos() + QPointF(self.end_node.rect().width() / 2, self.end_node.rect().top())

        path = QPainterPath()
        path.moveTo(p1)

        # Draw smooth bezier curve between nodes
        mid_y = (p1.y() + p2.y()) / 2
        path.cubicTo(QPointF(p1.x(), mid_y), QPointF(p2.x(), mid_y), p2)

        self.setPath(path)
        self.setPen(QPen(QColor("#7f8c8d"), 2, Qt.PenStyle.SolidLine))


class FlowchartScene(QGraphicsScene):
    """Graphics scene holding nodes and connecting arrows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes: List[FlowchartNodeItem] = []
        self.arrows: List[ConnectionArrow] = []
        self.reset_default_diagram()

    def reset_default_diagram(self):
        self.clear()
        self.nodes = []
        self.arrows = []

        default_steps = [
            ("Import Monthly CSV", "Parse Outlet_Name_YYYY_MM.csv and validate headers & schemas."),
            ("Validation & Delivery Check", "Verify non-negative quantities, date integrity & delivery <= report date."),
            ("Batch Expiry Inspection", "Min-heap Priority Queue orders batches by remaining shelf life. Flag <= 14d."),
            ("Demand Forecasting", "Linear regression across calendar month indices; 1-month uses purchases; clamp >= 0."),
            ("Replacement Need & Target", "Need = Sold + floor(75% * Expired This Month). Target = Available + Need."),
            ("Priority Ranking", "Availability score (100) + gross margin cents. Merge sort ranks value per cost."),
            ("Budget Allocation", "Shared budget: Greedy buys in rank order; Bounded Knapsack maximizes score <= $1000."),
            ("Decision Support Export", "Display top 20 chart, full data table, and export recommendations CSV."),
        ]

        x = 50.0
        y = 30.0
        for idx, (title, desc) in enumerate(default_steps, start=1):
            node = FlowchartNodeItem(idx, title, desc, x, y, w=280, h=75)
            self.addItem(node)
            self.nodes.append(node)
            y += 115.0

        self._rebuild_arrows()
        self.setSceneRect(0, 0, 380, y + 50)

    def _rebuild_arrows(self):
        for arr in self.arrows:
            self.removeItem(arr)
        self.arrows = []

        for i in range(len(self.nodes) - 1):
            arrow = ConnectionArrow(self.nodes[i], self.nodes[i + 1])
            self.addItem(arrow)
            self.arrows.append(arrow)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        for arrow in self.arrows:
            arrow.update_path()

    def add_custom_node(self, title: str, description: str):
        next_num = len(self.nodes) + 1
        last_pos = self.nodes[-1].pos() if self.nodes else QPointF(50, 30)
        new_node = FlowchartNodeItem(next_num, title, description, last_pos.x(), last_pos.y() + 115, w=280, h=75)
        self.addItem(new_node)
        self.nodes.append(new_node)
        self._rebuild_arrows()
        self.setSceneRect(0, 0, max(400, new_node.pos().x() + 320), new_node.pos().y() + 120)

    def remove_selected_node(self):
        selected = [item for item in self.selectedItems() if isinstance(item, FlowchartNodeItem)]
        if not selected:
            return
        for node in selected:
            if node in self.nodes:
                self.nodes.remove(node)
            self.removeItem(node)
        # Renumber
        for idx, node in enumerate(self.nodes, start=1):
            node.step_num = idx
            node.update()
        self._rebuild_arrows()


class ProcessDiagramWindow(QWidget):
    """
    Dedicated window/tab for the Editable Process Diagram and Live Calculation Panel.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Market Expand - Process Diagram & Live Calculation")
        self.resize(1100, 720)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Toolbar for diagram actions
        toolbar = QToolBar()
        add_btn = QPushButton("Add Node")
        add_btn.clicked.connect(self._add_node_dialog)
        toolbar.addWidget(add_btn)

        del_btn = QPushButton("Delete Selected Node")
        del_btn.clicked.connect(self._delete_node)
        toolbar.addWidget(del_btn)

        edit_btn = QPushButton("Edit Selected Node")
        edit_btn.clicked.connect(self._edit_node_dialog)
        toolbar.addWidget(edit_btn)

        reset_btn = QPushButton("Reset to Default Diagram")
        reset_btn.clicked.connect(self._reset_diagram)
        toolbar.addWidget(reset_btn)

        main_layout.addWidget(toolbar)

        # Splitter: Left is Flowchart Canvas, Right is Live Calculation Panel
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Flowchart Scene & View
        self.scene = FlowchartScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        splitter.addWidget(self.view)

        # Right: Live Calculation Panel
        calc_widget = self._create_live_calc_panel()
        splitter.addWidget(calc_widget)

        splitter.setSizes([450, 650])
        main_layout.addWidget(splitter, stretch=1)

        # Initial live calculation run
        self._recalculate_illustration()

    def _create_live_calc_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        title = QLabel("<h3>Live Illustrative Calculation Panel</h3>")
        desc = QLabel(
            "<i>Interactive step-by-step mathematical illustration of the decision model. "
            "Modify the parameters below to see intermediate and final formulas update live.</i>"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; margin-bottom: 6px;")
        layout.addWidget(title)
        layout.addWidget(desc)

        # Input Form Grid
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.Shape.StyledPanel)
        in_layout = QVBoxLayout(input_frame)
        in_layout.setSpacing(6)

        # Row 1: Cost & Sell
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Unit Cost ($):"))
        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0.01, 1000.0)
        self.cost_spin.setValue(2.20)
        self.cost_spin.setSingleStep(0.20)
        r1.addWidget(self.cost_spin)

        r1.addWidget(QLabel("Unit Sell ($):"))
        self.sell_spin = QDoubleSpinBox()
        self.sell_spin.setRange(0.01, 1000.0)
        self.sell_spin.setValue(3.50)
        self.sell_spin.setSingleStep(0.20)
        r1.addWidget(self.sell_spin)
        in_layout.addLayout(r1)

        # Row 2: Purchases History (Month 1, Month 2)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Mth 1 Purchase:"))
        self.p1_spin = QSpinBox()
        self.p1_spin.setRange(0, 10000)
        self.p1_spin.setValue(7)
        r2.addWidget(self.p1_spin)

        r2.addWidget(QLabel("Sold This Mth:"))
        self.p2_spin = QSpinBox()
        self.p2_spin.setRange(0, 10000)
        self.p2_spin.setValue(7)
        r2.addWidget(self.p2_spin)

        r2.addWidget(QLabel("Expired This Mth:"))
        self.expired_spin = QSpinBox()
        self.expired_spin.setRange(0, 10000)
        self.expired_spin.setValue(40)
        r2.addWidget(self.expired_spin)
        in_layout.addLayout(r2)

        # Row 3: Lead Time & Shelf Life
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Lead Time (days):"))
        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(0, 365)
        self.lead_spin.setValue(7)
        r3.addWidget(self.lead_spin)

        r3.addWidget(QLabel("Shelf Life (days):"))
        self.shelf_spin = QSpinBox()
        self.shelf_spin.setRange(1, 1000)
        self.shelf_spin.setValue(45)
        r3.addWidget(self.shelf_spin)
        in_layout.addLayout(r3)

        # Row 4: Usable Stock & Budget
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Usable Stock:"))
        self.stock_spin = QSpinBox()
        self.stock_spin.setRange(0, 10000)
        self.stock_spin.setValue(3)
        r4.addWidget(self.stock_spin)

        r4.addWidget(QLabel("Budget ($):"))
        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setRange(0.0, 1000.0)
        self.budget_spin.setValue(250.0)
        self.budget_spin.setSingleStep(25.0)
        r4.addWidget(self.budget_spin)
        in_layout.addLayout(r4)

        # Row 5: Method
        r5 = QHBoxLayout()
        r5.addWidget(QLabel("Allocation Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItem("Greedy (Rank Order)", "Greedy")
        self.method_combo.addItem("Bounded Knapsack (DP)", "Knapsack")
        self.method_combo.addItem("Balanced Budget (Even Distribution)", "Even")
        r5.addWidget(self.method_combo)

        r5.addWidget(QLabel("Balanced Base (%):"))
        self.base_share_spin = QDoubleSpinBox()
        self.base_share_spin.setRange(0.0, 100.0)
        self.base_share_spin.setValue(25.0)
        self.base_share_spin.setDecimals(0)
        self.base_share_spin.setSingleStep(5.0)
        self.base_share_spin.setSuffix(" %")
        r5.addWidget(self.base_share_spin)
        in_layout.addLayout(r5)

        layout.addWidget(input_frame)

        # Output Text Area with formatting
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setStyleSheet("background: #fafafa; font-family: monospace; font-size: 12px; padding: 8px;")
        layout.addWidget(self.output_view, stretch=1)

        # Hook signals
        self.cost_spin.valueChanged.connect(self._recalculate_illustration)
        self.sell_spin.valueChanged.connect(self._recalculate_illustration)
        self.p1_spin.valueChanged.connect(self._recalculate_illustration)
        self.p2_spin.valueChanged.connect(self._recalculate_illustration)
        self.expired_spin.valueChanged.connect(self._recalculate_illustration)
        self.expired_spin.valueChanged.connect(self._recalculate_illustration)
        self.lead_spin.valueChanged.connect(self._recalculate_illustration)
        self.shelf_spin.valueChanged.connect(self._recalculate_illustration)
        self.stock_spin.valueChanged.connect(self._recalculate_illustration)
        self.budget_spin.valueChanged.connect(self._recalculate_illustration)
        self.method_combo.currentIndexChanged.connect(self._recalculate_illustration)
        self.base_share_spin.valueChanged.connect(self._recalculate_illustration)

        return panel

    def _recalculate_illustration(self):
        cost = self.cost_spin.value()
        sell = self.sell_spin.value()
        p1 = self.p1_spin.value()
        sold = self.p2_spin.value()
        mth_expired = self.expired_spin.value()
        lead = self.lead_spin.value()
        shelf = self.shelf_spin.value()
        usable_stock = self.stock_spin.value()
        budget = self.budget_spin.value()
        method = self.method_combo.currentText()
        base_share = 100.0 if self.method_combo.currentData() == 'Even' else self.base_share_spin.value()
        base_budget = round(budget * (base_share / 100.0), 2)
        opt_budget = round(budget - base_budget, 2)

        # Step 1: Demand Forecast (used for Popularity objective)
        history = [(2026, 5, float(p1)), (2026, 6, float(sold))]
        forecast_monthly = predict_demand(history)
        days_in_month = 30
        daily_demand = forecast_monthly / days_in_month

        # Step 2: 75% Partial Expiry Replacement Rule
        replaced = (mth_expired * 75) // 100
        need_units = sold + replaced
        target_stock = usable_stock + need_units

        # Step 3: Priority Scoring across all 3 objectives
        gross_margin = max(0.0, sell - cost)
        margin_cents = int(round(gross_margin * 100))
        avail_margin_score = 100 + margin_cents
        profit_score = margin_cents
        popularity_value = int(round(forecast_monthly * 100))
        val_per_cost = avail_margin_score / cost if cost > 0 else float("inf")

        # Step 4: Restocking Simulation
        can_afford = int(math.floor(budget / cost)) if cost > 0 else need_units
        allocated_units = min(need_units, can_afford) if avail_margin_score > 0 else 0
        allocated_cost = allocated_units * cost
        rem_budget = budget - allocated_cost

        text = f"""========================================================================
LIVE DECISION MODEL STEP-BY-STEP BREAKDOWN
========================================================================

1. DEMAND FORECASTING (Linear Regression for Popularity Score):
   Historical Months: Month 1 = {p1} units, Current Month Sold = {sold} units
   Linear Trend Slope: {sold - p1:+d} units/month
   Forecasted Monthly Demand: {forecast_monthly:.2f} units ({daily_demand:.2f} units/day)

2. PARTIAL EXPIRY REPLACEMENT RULE (75% Expiry Replacement):
   Sold This Month: {sold} units; Expired This Month: {mth_expired} units
   Replace Expired Units: floor({mth_expired} x 75%) = {replaced} units
   Indicative Need: {sold} + {replaced} = {need_units} units
   Usable (Unexpired) Stock: {usable_stock} units
   Target Stock: {usable_stock} + {need_units} = {target_stock} units
   (Lead Time: {lead}d, Shelf Life: {shelf}d)

3. PRIORITY SCORING (Three Selectable Objectives):
   Gross Margin: ${sell:.2f} - ${cost:.2f} = ${gross_margin:.2f} ({margin_cents} cents)
   - Availability + margin score: 100 + {margin_cents} = {avail_margin_score} points/unit
   - Profit score: {profit_score} points/unit (margin in cents)
   - Popularity score: {forecast_monthly:.2f} x 100 = {popularity_value} points/unit
   Unit Cost: ${cost:.2f} -> Value/Cost Ratio: {val_per_cost:.2f} pts/$

4. SINGLE-PRODUCT BUDGET SIMULATION ({method}, Balanced Base: {base_share:.0f}%):
   Total Restocking Budget: ${budget:.2f} (Balanced Base: ${base_budget:.2f} | Optimization Remainder: ${opt_budget:.2f})
   Indicative Need: {need_units} units @ ${cost:.2f}
   Max Affordable Quantity: floor(${budget:.2f} / ${cost:.2f}) = {can_afford} units
   -> Affordable Recommendation: {allocated_units} units
   -> Estimated Spend: ${allocated_cost:.2f} (Remaining Budget: ${rem_budget:.2f})
========================================================================"""
        self.output_view.setPlainText(text)

    def _add_node_dialog(self):
        title, ok1 = QInputDialog.getText(self, "Add Step Node", "Enter Step Title:")
        if not ok1 or not title.strip():
            return
        desc, ok2 = QInputDialog.getText(self, "Add Step Node", "Enter Step Description:")
        if not ok2:
            desc = ""
        self.scene.add_custom_node(title.strip(), desc.strip())

    def _delete_node(self):
        self.scene.remove_selected_node()

    def _edit_node_dialog(self):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, FlowchartNodeItem)]
        if not selected:
            QMessageBox.information(self, "Edit Node", "Please select a flowchart node to edit.")
            return
        node = selected[0]
        new_title, ok1 = QInputDialog.getText(self, "Edit Step Node", "Update Step Title:", text=node.title)
        if not ok1 or not new_title.strip():
            return
        new_desc, ok2 = QInputDialog.getText(self, "Edit Step Node", "Update Step Description:", text=node.description)
        if ok2:
            node.title = new_title.strip()
            node.description = new_desc.strip()
            node.update()

    def _reset_diagram(self):
        self.scene.reset_default_diagram()
