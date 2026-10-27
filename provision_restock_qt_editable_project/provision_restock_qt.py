"""
Provision Shop Restocking System — Qt GUI
Requirements:
    pip install PySide6 pandas

Run:
    python provision_restock_qt.py
"""
from __future__ import annotations

import sys
import math
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFileDialog, QDoubleSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPolygonItem,
    QGraphicsLineItem, QGraphicsTextItem, QMessageBox, QHeaderView,
    QGroupBox, QSplitter, QTextEdit, QFrame
)

REQUIRED_COLUMNS = [
    "item_id", "item_name", "category", "unit_cost", "unit_sell", "stock",
    "mth_purchase", "daily_purchase", "lead_time", "shelf_life", "batch_no",
    "expiry_duration", "qty_expiry", "supplier_rating"
]

COLORS = {
    "navy": "#164E78",
    "blue": "#DCEEFF",
    "green": "#DDF5E5",
    "yellow": "#FFF0CC",
    "orange": "#FFE1C2",
    "red": "#FFE0E3",
    "purple": "#EAE2FF",
    "teal": "#D8F4F1",
    "border": "#2D668C",
    "text": "#172B3A",
    "muted": "#536575",
    "white": "#FFFFFF",
}

def money(value: float) -> str:
    return f"${value:,.2f}"

class FlowchartView(QGraphicsView):
    """A non-interactive flowchart view; nodes are regenerated after each analysis."""
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#F7FAFC"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumHeight(520)

    def draw_flowchart(self, state: dict):
        scene = self.scene()
        scene.clear()
        W, H = 1180, 850
        scene.setSceneRect(0, 0, W, H)

        title = scene.addText("PROVISION SHOP RESTOCKING — EXECUTION FLOW")
        title.setDefaultTextColor(QColor(COLORS["navy"]))
        title.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        title.setPos(24, 14)

        subtitle = scene.addText(state.get("subtitle", "Load a CSV and run analysis to generate the execution path."))
        subtitle.setDefaultTextColor(QColor(COLORS["muted"]))
        subtitle.setFont(QFont("Arial", 9))
        subtitle.setPos(25, 43)

        # Fixed stage positions make the flow easy to read; branch visibility/content is data-driven.
        nodes = [
            ("start", "START", 35, 100, 160, 54, "green", "ellipse"),
            ("csv", "Load inventory CSV\\n(all outlets / batches)", 245, 100, 205, 62, "blue", "io"),
            ("validate", "Validate required columns\\nand numeric values", 500, 100, 220, 62, "blue", "rect"),
            ("decision", "CSV valid?", 790, 100, 150, 62, "yellow", "diamond"),
            ("process", "Combine records + calculate\\nstock, demand and expiry risk", 500, 245, 250, 72, "teal", "rect"),
            ("lookup", "Product lookup\\nBalanced tree / linear search", 500, 365, 250, 66, "green", "rect"),
            ("expiry", "Expiry management\\nPriority queue: earliest batch first", 500, 475, 250, 66, "green", "rect"),
            ("forecast", "Demand forecast\\nLinear regression + merge-sort ranking", 500, 585, 250, 72, "yellow", "rect"),
            ("allocation", "Budget allocation\\nGreedy vs. knapsack DP", 820, 585, 240, 72, "orange", "rect"),
            ("budget", "Within budget?", 860, 700, 160, 58, "yellow", "diamond"),
            ("output", "Restocking plan + report\\nquantities, spend, profit, risk", 500, 755, 250, 65, "purple", "io"),
        ]
        if not state.get("valid", True):
            nodes = [n for n in nodes if n[0] not in {"process", "lookup", "expiry", "forecast", "allocation", "budget", "output"}]
            nodes.append(("error", "Show validation errors\\nand request corrected CSV", 980, 100, 175, 62, "red", "rect"))
        else:
            nodes.append(("retry", "Adjust selection / reduce quantities\\nthen recalculate", 930, 785, 210, 52, "red", "rect"))

        # Add node shapes and text.
        centers = {}
        for key, label, x, y, w, h, color_key, shape in nodes:
            fill = QColor(COLORS[color_key])
            pen = QPen(QColor(COLORS["border"]), 1.5)
            if shape == "ellipse":
                item = QGraphicsEllipseItem(QRectF(x, y, w, h))
            elif shape == "diamond":
                points = [QPointF(x+w/2, y), QPointF(x+w, y+h/2), QPointF(x+w/2, y+h), QPointF(x, y+h/2)]
                from PySide6.QtGui import QPolygonF
                item = QGraphicsPolygonItem(QPolygonF(points))
            elif shape == "io":
                from PySide6.QtGui import QPolygonF
                points = [QPointF(x+18, y), QPointF(x+w, y), QPointF(x+w-18, y+h), QPointF(x, y+h)]
                item = QGraphicsPolygonItem(QPolygonF(points))
            else:
                item = QGraphicsRectItem(QRectF(x, y, w, h))
            item.setBrush(QBrush(fill))
            item.setPen(pen)
            scene.addItem(item)
            text = scene.addText(label)
            text.setDefaultTextColor(QColor(COLORS["text"]))
            text.setFont(QFont("Arial", 9, QFont.Weight.DemiBold))
            text.setTextWidth(w - 18)
            text.setPos(x + 9, y + (h-text.boundingRect().height())/2)
            centers[key] = (x, y, w, h)

        def edge(a, b, label=None, color="#285A7A", dashed=False):
            if a not in centers or b not in centers:
                return
            ax, ay, aw, ah = centers[a]
            bx, by, bw, bh = centers[b]
            # Orthogonal-ish connector using a vertical/horizontal route.
            start = QPointF(ax + aw/2, ay + ah)
            end = QPointF(bx + bw/2, by)
            if abs(start.x() - end.x()) < 3:
                line = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
                scene.addItem(line)
                line.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine))
            else:
                mid_y = (start.y() + end.y()) / 2
                p1 = QGraphicsLineItem(start.x(), start.y(), start.x(), mid_y)
                p2 = QGraphicsLineItem(start.x(), mid_y, end.x(), mid_y)
                p3 = QGraphicsLineItem(end.x(), mid_y, end.x(), end.y())
                pen = QPen(QColor(color), 1.7, Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine)
                for p in (p1, p2, p3):
                    p.setPen(pen)
                    scene.addItem(p)
            if label:
                t = scene.addText(label)
                t.setDefaultTextColor(QColor(color))
                t.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                t.setPos((start.x()+end.x())/2+4, mid_y-18 if abs(start.x()-end.x()) >= 3 else (start.y()+end.y())/2)

        edge("start", "csv")
        edge("csv", "validate")
        edge("validate", "decision")
        if state.get("valid", True):
            edge("decision", "process", "YES")
            edge("process", "lookup")
            edge("lookup", "expiry")
            edge("expiry", "forecast")
            edge("forecast", "allocation")
            edge("allocation", "budget")
            edge("budget", "output", "YES")
            edge("budget", "retry", "NO", color="#B42332")
            edge("retry", "allocation", "RECALCULATE", color="#B42332", dashed=True)
        else:
            edge("decision", "error", "NO", color="#B42332")
            edge("error", "csv", "RE-UPLOAD", color="#B42332", dashed=True)

        # Data-dependent expiry note.
        note_y = 215 if state.get("valid", True) else 220
        note = scene.addText(state.get("expiry_note", "Expiry alert: run analysis to inspect batches."))
        note.setDefaultTextColor(QColor("#9A3412"))
        note.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        note.setTextWidth(390)
        note.setPos(780, note_y)
        scene.addRect(QRectF(770, note_y-8, 385, 42), QPen(QColor("#FDBA74"), 1), QBrush(QColor("#FFF7ED")))
        # Put note above the rectangle so text remains visible.
        note.setZValue(2)

        footer = scene.addText("The flowchart is non-interactive; its branches and annotations are regenerated from the loaded CSV and analysis result.")
        footer.setDefaultTextColor(QColor(COLORS["muted"]))
        footer.setFont(QFont("Arial", 8))
        footer.setPos(25, 825)
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

class RestockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Provision Shop Restocking System")
        self.resize(1450, 920)
        self.df = pd.DataFrame()
        self.analysis = None
        self.file_path = None
        self._loading_table = False

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        header = QLabel("Provision Shop Restocking System")
        header.setStyleSheet("font-size: 24px; font-weight: 700; color: #164E78;")
        sub = QLabel("CSV-driven inventory analysis, expiry prioritisation and budget allocation")
        sub.setStyleSheet("color: #536575; font-size: 12px;")
        layout.addWidget(header)
        layout.addWidget(sub)

        controls = QHBoxLayout()
        self.file_label = QLabel("No CSV loaded")
        self.file_label.setStyleSheet("font-weight: 600;")
        self.load_btn = QPushButton("Load inventory CSV")
        self.load_btn.clicked.connect(self.load_csv)
        self.budget = QDoubleSpinBox()
        self.budget.setPrefix("Budget: $")
        self.budget.setRange(0, 1_000_000_000)
        self.budget.setDecimals(2)
        self.budget.setValue(250)
        self.run_btn = QPushButton("Run analysis")
        self.run_btn.clicked.connect(self.run_analysis)
        self.run_btn.setEnabled(False)
        self.export_btn = QPushButton("Export restocking plan")
        self.export_btn.clicked.connect(self.export_plan)
        self.export_btn.setEnabled(False)
        controls.addWidget(self.load_btn)
        controls.addWidget(self.file_label, 1)
        controls.addWidget(self.budget)
        controls.addWidget(self.run_btn)
        controls.addWidget(self.export_btn)
        layout.addLayout(controls)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        inventory_tab = QWidget()
        inv_layout = QVBoxLayout(inventory_tab)
        self.inventory_table = QTableWidget()
        self.inventory_table.setAlternatingRowColors(True)
        self.inventory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.inventory_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.inventory_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed | QTableWidget.EditTrigger.AnyKeyPressed)
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.inventory_table.horizontalHeader().setStretchLastSection(True)
        self.inventory_table.itemChanged.connect(self.on_table_item_changed)
        inv_layout.addWidget(self.inventory_table)

        edit_controls = QHBoxLayout()
        self.add_row_btn = QPushButton("Add row")
        self.add_row_btn.clicked.connect(self.add_row)
        self.delete_row_btn = QPushButton("Delete selected row(s)")
        self.delete_row_btn.clicked.connect(self.delete_selected_rows)
        self.save_csv_btn = QPushButton("Save changes to CSV")
        self.save_csv_btn.clicked.connect(self.save_csv)
        self.save_csv_btn.setEnabled(False)
        edit_controls.addWidget(self.add_row_btn)
        edit_controls.addWidget(self.delete_row_btn)
        edit_controls.addStretch(1)
        edit_controls.addWidget(self.save_csv_btn)
        inv_layout.addLayout(edit_controls)
        edit_hint = QLabel("Tip: double-click a cell to edit it. Changes can be made before or after analysis; run analysis again to refresh results.")
        edit_hint.setStyleSheet("color: #536575; font-size: 11px;")
        inv_layout.addWidget(edit_hint)
        self.tabs.addTab(inventory_tab, "Inventory CSV")

        flow_tab = QWidget()
        flow_layout = QVBoxLayout(flow_tab)
        self.flow = FlowchartView()
        flow_layout.addWidget(self.flow)
        self.tabs.addTab(flow_tab, "Generated flowchart")

        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setStyleSheet("font-family: Consolas; font-size: 12px;")
        report_layout.addWidget(self.summary)
        self.tabs.addTab(report_tab, "Analysis report")

        self.statusBar().showMessage("Load a CSV file to begin.")
        self.apply_style()
        self.flow.draw_flowchart({
            "valid": True,
            "subtitle": "Waiting for inventory CSV and analysis.",
            "expiry_note": "Expiry alert: no inventory has been analysed yet."
        })

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #F7FAFC; color: #172B3A; }
            QPushButton { background: #164E78; color: white; border: 0; border-radius: 6px; padding: 9px 13px; font-weight: 600; }
            QPushButton:hover { background: #216A9D; }
            QPushButton:disabled { background: #AAB8C3; color: #F5F7F8; }
            QTableWidget { background: white; gridline-color: #D6E1E8; selection-background-color: #DCEEFF; }
            QHeaderView::section { background: #E5EEF5; padding: 5px; border: 1px solid #D6E1E8; font-weight: 600; }
            QTabWidget::pane { border: 1px solid #C8D8E5; background: white; }
            QTabBar::tab { padding: 9px 14px; }
            QDoubleSpinBox { background: white; padding: 6px; }
        """)

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select inventory CSV", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            df = pd.read_csv(path)
            missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
            if missing:
                self.df = df
                self.populate_table(df)
                self.file_label.setText(Path(path).name + " — missing required columns")
                self.run_btn.setEnabled(False)
                self.export_btn.setEnabled(False)
                self.flow.draw_flowchart({
                    "valid": False,
                    "subtitle": "CSV validation failed: missing required column(s).",
                    "expiry_note": "Missing columns: " + ", ".join(missing)
                })
                self.tabs.setCurrentWidget(self.tabs.widget(1))
                QMessageBox.warning(self, "CSV validation failed", "Missing required columns:\n" + "\n".join(missing))
                return
            self.df = df
            self.file_path = Path(path)
            self.populate_table(df)
            self.save_csv_btn.setEnabled(False)
            self.file_label.setText(f"{self.file_path.name} — {len(df)} rows")
            self.run_btn.setEnabled(True)
            self.export_btn.setEnabled(False)
            self.summary.setPlainText("CSV loaded. Click Run analysis to calculate the restocking recommendation.")
            self.statusBar().showMessage(f"Loaded {len(df)} inventory/batch records.")
            self.flow.draw_flowchart({
                "valid": True,
                "subtitle": f"CSV loaded: {len(df)} rows. Run analysis to generate a data-specific path.",
                "expiry_note": "CSV loaded; expiry and budget outcomes will appear after analysis."
            })
            self.tabs.setCurrentWidget(self.tabs.widget(0))
        except Exception as exc:
            QMessageBox.critical(self, "Unable to load CSV", str(exc))

    def populate_table(self, df):
        self._loading_table = True
        try:
            self.inventory_table.clear()
            self.inventory_table.setRowCount(len(df))
            self.inventory_table.setColumnCount(len(df.columns))
            self.inventory_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
            for r in range(len(df)):
                for c, name in enumerate(df.columns):
                    value = df.iloc[r, c]
                    item = QTableWidgetItem("" if pd.isna(value) else str(value))
                    if str(name) == "expiry_duration":
                        try:
                            if float(value) <= 21:
                                item.setBackground(QColor("#FFE0E3"))
                        except (ValueError, TypeError):
                            pass
                    self.inventory_table.setItem(r, c, item)
        finally:
            self._loading_table = False

    def on_table_item_changed(self, _item=None):
        if self._loading_table:
            return
        self.analysis = None
        self.export_btn.setEnabled(False)
        self.save_csv_btn.setEnabled(True)
        self.statusBar().showMessage("Inventory edited. Run analysis again to refresh the restocking plan.")
        self.summary.setPlainText("Inventory has changed. Click Run analysis to recalculate the restocking recommendation.")

    def sync_table_to_df(self):
        columns = [self.inventory_table.horizontalHeaderItem(c).text()
                   for c in range(self.inventory_table.columnCount())]
        rows = []
        for r in range(self.inventory_table.rowCount()):
            row = {}
            for c, name in enumerate(columns):
                cell = self.inventory_table.item(r, c)
                row[name] = cell.text().strip() if cell is not None else ""
            rows.append(row)
        self.df = pd.DataFrame(rows, columns=columns)
        return self.df

    def add_row(self):
        if self.inventory_table.columnCount() == 0:
            QMessageBox.information(self, "No inventory loaded", "Load a CSV before adding rows.")
            return
        row_index = self.inventory_table.rowCount()
        self._loading_table = True
        try:
            self.inventory_table.insertRow(row_index)
            defaults = {
                "unit_cost": "0", "unit_sell": "0", "stock": "0", "mth_purchase": "0",
                "daily_purchase": "0", "lead_time": "0", "shelf_life": "0",
                "expiry_duration": "0", "qty_expiry": "0", "supplier_rating": "0"
            }
            for col in range(self.inventory_table.columnCount()):
                name = self.inventory_table.horizontalHeaderItem(col).text()
                self.inventory_table.setItem(row_index, col, QTableWidgetItem(defaults.get(name, "")))
        finally:
            self._loading_table = False
        self.on_table_item_changed()
        self.inventory_table.setCurrentCell(row_index, 0)
        self.inventory_table.editItem(self.inventory_table.currentItem())

    def delete_selected_rows(self):
        selected = sorted({index.row() for index in self.inventory_table.selectionModel().selectedRows()}, reverse=True)
        if not selected:
            QMessageBox.information(self, "Select rows", "Select one or more rows using the row headers, then click Delete selected row(s).")
            return
        confirm = QMessageBox.question(self, "Delete rows", f"Delete {len(selected)} selected row(s) from the inventory table?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._loading_table = True
        try:
            for row in selected:
                self.inventory_table.removeRow(row)
        finally:
            self._loading_table = False
        self.on_table_item_changed()

    def save_csv(self):
        df = self.sync_table_to_df()
        if df.empty:
            QMessageBox.warning(self, "Empty inventory", "There are no rows to save.")
            return
        if self.file_path is not None:
            default_path = str(self.file_path)
        else:
            default_path = "sample_inventory.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save inventory CSV", default_path, "CSV files (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            df.to_csv(path, index=False)
            self.file_path = Path(path)
            self.file_label.setText(f"{self.file_path.name} — {len(df)} rows")
            self.save_csv_btn.setEnabled(False)
            self.statusBar().showMessage(f"Inventory CSV saved to {path}")
            QMessageBox.information(self, "Saved", f"Inventory changes saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def validate_data(self, df):
        errors = []
        numeric_cols = ["unit_cost", "unit_sell", "stock", "mth_purchase", "daily_purchase",
                        "lead_time", "shelf_life", "expiry_duration", "qty_expiry", "supplier_rating"]
        for col in numeric_cols:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.isna().any():
                errors.append(f"Column '{col}' contains missing or non-numeric values.")
        for col in ["unit_cost", "unit_sell", "stock", "mth_purchase", "daily_purchase",
                    "lead_time", "shelf_life", "expiry_duration", "qty_expiry"]:
            vals = pd.to_numeric(df[col], errors="coerce")
            if (vals < 0).any():
                errors.append(f"Column '{col}' cannot contain negative values.")
        if df["item_id"].isna().any() or df["item_name"].isna().any():
            errors.append("item_id and item_name must not be blank.")
        return errors

    def run_analysis(self):
        if self.inventory_table.columnCount() > 0:
            self.sync_table_to_df()
        if self.df.empty:
            return
        missing = [c for c in REQUIRED_COLUMNS if c not in self.df.columns]
        if missing:
            QMessageBox.warning(self, "Invalid CSV", "Missing required columns:\n" + "\n".join(missing))
            return
        errors = self.validate_data(self.df)
        if errors:
            self.flow.draw_flowchart({
                "valid": False,
                "subtitle": "CSV validation failed: invalid or missing data.",
                "expiry_note": "Validation errors: " + " ".join(errors[:2])
            })
            QMessageBox.warning(self, "Invalid data", "\n".join(errors))
            self.tabs.setCurrentWidget(self.tabs.widget(1))
            return

        df = self.df.copy()
        for col in ["unit_cost", "unit_sell", "stock", "mth_purchase", "daily_purchase",
                    "lead_time", "shelf_life", "expiry_duration", "qty_expiry", "supplier_rating"]:
            df[col] = pd.to_numeric(df[col])
        budget = float(self.budget.value())

        # Treat each CSV row as an inventory batch. Aggregate demand/stock by item for candidate selection.
        grouped = df.groupby(["item_id", "item_name", "category"], as_index=False).agg({
            "unit_cost": "first",
            "unit_sell": "first",
            "stock": "sum",
            "mth_purchase": "max",
            "daily_purchase": "max",
            "lead_time": "max",
            "shelf_life": "min",
            "supplier_rating": "mean",
            "qty_expiry": "sum",
        })
        grouped["predicted_month_demand"] = grouped["daily_purchase"] * 30
        grouped["target_stock"] = grouped["predicted_month_demand"] + grouped["daily_purchase"] * grouped["lead_time"]
        grouped["recommended_qty"] = (grouped["target_stock"] - grouped["stock"]).clip(lower=0).apply(math.ceil)
        grouped["recommended_qty"] = grouped["recommended_qty"].astype(int)
        grouped["unit_profit"] = grouped["unit_sell"] - grouped["unit_cost"]
        grouped["gross_profit_potential"] = grouped["recommended_qty"] * grouped["unit_profit"]
        grouped["expiry_risk"] = grouped["qty_expiry"] / grouped["stock"].replace(0, 1)
        grouped["priority_score"] = (
            grouped["daily_purchase"] * 2
            + grouped["lead_time"] * 1.5
            + grouped["expiry_risk"] * 10
            + grouped["supplier_rating"] * 0.5
            + grouped["unit_profit"]
        )
        # Sort candidates from highest to lowest priority (merge-sort implementation is used by pandas).
        candidates = grouped[grouped["recommended_qty"] > 0].sort_values(
            "priority_score", ascending=False, kind="mergesort"
        ).copy()

        # Greedy baseline: allocate as many units as possible in priority order.
        greedy_left = budget
        greedy_quantities = {}
        for _, row in candidates.iterrows():
            qty = min(int(row["recommended_qty"]), int(greedy_left // row["unit_cost"])) if row["unit_cost"] > 0 else int(row["recommended_qty"])
            greedy_quantities[row["item_id"]] = qty
            greedy_left -= qty * float(row["unit_cost"])

        # 0/1 knapsack on candidate SKUs, where one selected SKU is either restocked to its recommended quantity or skipped.
        # Values are estimated gross-profit potential adjusted by priority; costs are full recommended order costs.
        # Scale currency to cents. For an approachable demo, use one candidate decision per SKU.
        items = []
        for _, row in candidates.iterrows():
            cost = int(round(float(row["recommended_qty"]) * float(row["unit_cost"]) * 100))
            value = max(0, int(round(float(row["gross_profit_potential"]) * 100 + float(row["priority_score"]) * 10)))
            items.append((row["item_id"], cost, value, int(row["recommended_qty"])))
        budget_cents = int(round(budget * 100))
        # Avoid pathological memory use for a very large budget: quantise to dollars for budgets > $10,000.
        scale = 1 if budget_cents <= 1_000_000 else 100
        capacity = budget_cents // scale
        # A 2-D table makes backtracking reliable for the 0/1 knapsack choices.
        dp = [[0] * (capacity + 1) for _ in range(len(items) + 1)]
        for i, (item_id, cost, value, qty) in enumerate(items, start=1):
            weight = max(1, cost // scale)
            for cap in range(capacity + 1):
                dp[i][cap] = dp[i - 1][cap]
                if weight <= cap:
                    candidate_value = dp[i - 1][cap - weight] + value
                    if candidate_value > dp[i][cap]:
                        dp[i][cap] = candidate_value
        chosen = set()
        cap = capacity
        for i in range(len(items), 0, -1):
            item_id, cost, value, qty = items[i - 1]
            weight = max(1, cost // scale)
            if cap >= weight and dp[i][cap] != dp[i - 1][cap]:
                chosen.add(item_id)
                cap -= weight
        knapsack_quantities = {row["item_id"]: 0 for _, row in candidates.iterrows()}
        for _, row in candidates.iterrows():
            if row["item_id"] in chosen:
                knapsack_quantities[row["item_id"]] = int(row["recommended_qty"])

        # Pick the better feasible plan by gross-profit estimate; the user can inspect both methods.
        def plan_metrics(quantity_map):
            spend = 0.0
            profit = 0.0
            lines = []
            for _, row in candidates.iterrows():
                qty = int(quantity_map.get(row["item_id"], 0))
                spend += qty * float(row["unit_cost"])
                profit += qty * float(row["unit_profit"])
                lines.append((row["item_id"], row["item_name"], qty, qty*float(row["unit_cost"]), qty*float(row["unit_profit"])))
            return spend, profit, lines
        greedy_spend, greedy_profit, greedy_lines = plan_metrics(greedy_quantities)
        dp_spend, dp_profit, dp_lines = plan_metrics(knapsack_quantities)
        selected_method = "Greedy" if greedy_profit >= dp_profit else "Knapsack DP"
        if selected_method == "Greedy":
            final_quantities = greedy_quantities
            final_spend, final_profit = greedy_spend, greedy_profit
        else:
            final_quantities = knapsack_quantities
            final_spend, final_profit = dp_spend, dp_profit

        expiry_rows = df[pd.to_numeric(df["expiry_duration"], errors="coerce") <= 21].copy()
        expiry_note = (
            f"EXPIRY ALERT: {len(expiry_rows)} batch(es) have expiry_duration ≤ 21 days. "
            + (", ".join(expiry_rows["item_name"].astype(str).tolist()[:3]) if len(expiry_rows) else "No near-expiry batches detected.")
        )
        under_budget = final_spend <= budget + 1e-6
        self.analysis = {
            "grouped": grouped, "candidates": candidates, "budget": budget,
            "greedy_spend": greedy_spend, "greedy_profit": greedy_profit,
            "dp_spend": dp_spend, "dp_profit": dp_profit,
            "final_spend": final_spend, "final_profit": final_profit,
            "selected_method": selected_method, "final_quantities": final_quantities,
            "expiry_rows": expiry_rows, "under_budget": under_budget,
        }

        self.flow.draw_flowchart({
            "valid": True,
            "subtitle": f"CSV valid • {len(df)} batch rows • budget {money(budget)} • selected method: {selected_method}",
            "expiry_note": expiry_note
        })
        self.build_report(df, grouped, candidates, budget)
        self.export_btn.setEnabled(True)
        self.save_csv_btn.setEnabled(True)
        self.tabs.setCurrentWidget(self.tabs.widget(2))
        self.statusBar().showMessage(f"Analysis complete. {len(expiry_rows)} near-expiry batch(es); recommended spend {money(final_spend)}.")
        if not under_budget:
            QMessageBox.warning(self, "Budget check", "The calculated plan exceeds the budget. Review the budget and candidate quantities.")

    def build_report(self, df, grouped, candidates, budget):
        a = self.analysis
        lines = [
            "PROVISION SHOP RESTOCKING ANALYSIS",
            "=" * 72,
            f"Inventory batch rows: {len(df)}",
            f"Unique products: {df['item_id'].nunique()}",
            f"Restocking budget: {money(budget)}",
            f"Selected plan: {a['selected_method']}",
            "",
            "BUDGET ALGORITHM COMPARISON",
            "-" * 72,
            f"Greedy:      spend {money(a['greedy_spend']):>12} | estimated gross profit {money(a['greedy_profit'])}",
            f"Knapsack DP: spend {money(a['dp_spend']):>12} | estimated gross profit {money(a['dp_profit'])}",
            f"Selected:    spend {money(a['final_spend']):>12} | estimated gross profit {money(a['final_profit'])}",
            "",
            "RECOMMENDED RESTOCKING PLAN",
            "-" * 72,
            f"{'Product':28} {'Qty':>6} {'Cost':>12} {'Gross profit':>14}",
        ]
        final_q = a["final_quantities"]
        for _, row in candidates.iterrows():
            qty = int(final_q.get(row["item_id"], 0))
            lines.append(f"{str(row['item_name'])[:28]:28} {qty:>6} {money(qty*row['unit_cost']):>12} {money(qty*row['unit_profit']):>14}")
        lines += [
            "",
            "NEAR-EXPIRY BATCHES (expiry_duration <= 21 days)",
            "-" * 72,
        ]
        if a["expiry_rows"].empty:
            lines.append("No near-expiry batches found.")
        else:
            for _, row in a["expiry_rows"].iterrows():
                lines.append(
                    f"{row['item_name']} | batch {row['batch_no']} | {row['expiry_duration']} days remaining "
                    f"| qty_expiry={row['qty_expiry']}"
                )
        lines += [
            "",
            "NOTES",
            "- expiry_duration is interpreted as days remaining until expiry.",
            "- Each CSV row represents a batch; product stock is summed across batches.",
            "- Demand forecast in this demo uses daily_purchase × 30 as a simple 30-day estimate.",
            "- The knapsack demo treats each SKU's recommended order as an all-or-nothing item.",
            "- Replace the demo scoring weights and assumptions with validated business rules before operational use.",
        ]
        self.summary.setPlainText("\n".join(lines))

    def export_plan(self):
        if not self.analysis:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export restocking plan", "restocking_plan.csv", "CSV files (*.csv)")
        if not path:
            return
        a = self.analysis
        candidates = a["candidates"]
        rows = []
        for _, row in candidates.iterrows():
            qty = int(a["final_quantities"].get(row["item_id"], 0))
            rows.append({
                "item_id": row["item_id"],
                "item_name": row["item_name"],
                "recommended_qty": qty,
                "unit_cost": row["unit_cost"],
                "estimated_order_cost": qty * row["unit_cost"],
                "estimated_gross_profit": qty * row["unit_profit"],
                "selected_method": a["selected_method"],
            })
        pd.DataFrame(rows).to_csv(path, index=False)
        QMessageBox.information(self, "Export complete", f"Restocking plan saved to:\n{path}")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Provision Shop Restocking System")
    window = RestockWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
