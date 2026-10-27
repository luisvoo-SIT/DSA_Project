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
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPolygonF
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

class ClickableFlowNode(QGraphicsRectItem):
    """A clickable flowchart node with a detail panel supplied by its tooltip."""
    def __init__(self, rect, title, detail, fill, border, on_click):
        super().__init__(rect)
        self.title = title
        self.detail = detail
        self.on_click = on_click
        self.setBrush(QBrush(QColor(fill)))
        self.setPen(QPen(QColor(border), 2))
        self.setToolTip(f"{title}\n\n{detail}\n\nClick for details")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.title, self.detail)
        super().mousePressEvent(event)


class FlowchartView(QGraphicsView):
    """Data-driven, clickable flowchart with zoom and hand-drag panning."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#F7FAFC"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMinimumHeight(520)
        self._zoom = 1.0

    def wheelEvent(self, event):
        # Ctrl+wheel zooms; ordinary wheel scrolling remains available.
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            new_zoom = self._zoom * factor
            if 0.25 <= new_zoom <= 3.5:
                self.scale(factor, factor)
                self._zoom = new_zoom
            event.accept()
        else:
            super().wheelEvent(event)

    def reset_zoom(self):
        self._zoom = 1.0
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _node_clicked(self, title, detail):
        QMessageBox.information(self, title, detail)

    def draw_flowchart(self, state: dict):
        """Render a labelled, data-driven workflow with the actual path highlighted."""
        scene = self.scene()
        scene.clear()
        scene.setBackgroundBrush(QColor("#F7FAFC"))
        title = scene.addText("PROVISION SHOP RESTOCKING — LIVE EXECUTION FLOW")
        title.setPos(24, 12); title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setDefaultTextColor(QColor(COLORS["navy"]))
        subtitle = scene.addText(state.get("subtitle", "Load a CSV and run analysis."))
        subtitle.setPos(25, 42); subtitle.setFont(QFont("Arial", 9))
        subtitle.setDefaultTextColor(QColor(COLORS["muted"]))

        valid = bool(state.get("valid", True))
        analysed = bool(state.get("analysed", False))
        expiry_count = int(state.get("expiry_count", 0))
        candidate_count = int(state.get("candidate_count", 0))
        under_budget = bool(state.get("under_budget", True))
        method = state.get("selected_method", "Knapsack DP")

        # node: key, label, x, y, w, h, kind, executed, detail, status
        specs = [
            ("start", "START", 455, 78, 150, 48, "start", True, "Restocking workflow begins.", "normal"),
            ("load", "Load inventory CSV\n(all outlets / batches)", 420, 158, 220, 64, "process", True, "Load the inventory CSV. Edit, add, or delete batch rows in the Inventory tab, then save if required.", "normal"),
            ("validate", "Validate required columns\nand numeric values", 420, 260, 220, 64, "process", (analysed or not valid), state.get("validation_detail", "Check required columns and numeric fields."), "normal"),
            ("decision", "CSV valid?", 465, 360, 130, 70, "decision", (analysed or not valid), "YES continues processing. NO returns to loading/correcting the CSV.", "normal"),
            ("aggregate", "Combine records + calculate\nstock, demand and expiry risk", 420, 470, 220, 68, "process", analysed and valid, state.get("aggregate_detail", "Combine batches by product and calculate stock, demand and expiry risk."), "normal"),
            ("lookup", "Product lookup\nBalanced search tree only", 420, 570, 220, 64, "process", analysed and valid, state.get("lookup_detail", "Use a balanced search tree for product lookup; no linear-search alternative is used in this workflow."), "normal"),
            ("expiry", "Expiry management\nPriority queue: earliest batch first", 420, 666, 220, 68, "process", analysed and valid, state.get("expiry_detail", "Prioritise batches by earliest expiry date/duration."), "normal"),
            ("forecast", "Demand forecast + ranking\nLinear regression + merge sort", 420, 766, 220, 68, "process", analysed and valid, state.get("forecast_detail", "Forecast demand with linear regression, then rank products using merge sort."), "normal"),
            ("optimise", "Budget allocation\nGreedy or Knapsack DP", 760, 766, 230, 68, "process", analysed and valid, state.get("optimise_detail", "Greedy is fast and suitable for ranking-based incremental allocation. Knapsack DP is better for discrete choices under a hard budget when maximising total value; it can cost more time and memory. The selected method is shown in the node."), "normal"),
            ("budget", "Within budget?", 810, 875, 130, 70, "decision", analysed and valid, state.get("budget_detail", "Compare selected order cost with the budget."), "normal"),
            ("output", "Option: export restocking plan\nQuantities, spend, profit, risk", 420, 990, 240, 70, "output", analysed and valid and under_budget, state.get("output_detail", "Export the final restocking plan and report."), "normal"),
            ("adjust", "Over budget: adjust selections,\nreduce quantities or raise budget", 760, 990, 260, 70, "error", analysed and valid and not under_budget, state.get("budget_detail", "Adjust selected items, reduce quantities, or revise the budget, then redo budget allocation."), "error"),
        ]
        nodes = {}
        def palette(executed, kind, status):
            if status == "error": return ("#FFE0E3", "#B42332")
            if executed: return (("#EAE2FF", "#7048B8") if kind == "output" else ("#DDF5E5", "#16803D"))
            return ("#E8EDF1", "#9AA9B5")
        for key,label,x,y,w,h,kind,executed,detail,status in specs:
            fill,border=palette(executed,kind,status)
            if kind == "start":
                item=scene.addEllipse(QRectF(x,y,w,h),QPen(QColor(border),2),QBrush(QColor(fill)))
            elif kind == "decision":
                poly=QPolygonF([QPointF(x+w/2,y),QPointF(x+w,y+h/2),QPointF(x+w/2,y+h),QPointF(x,y+h/2)])
                item=scene.addPolygon(poly,QPen(QColor(border),2),QBrush(QColor(fill)))
            elif kind == "output":
                poly=QPolygonF([QPointF(x+14,y),QPointF(x+w,y),QPointF(x+w-14,y+h),QPointF(x,y+h)])
                item=scene.addPolygon(poly,QPen(QColor(border),2),QBrush(QColor(fill)))
            else:
                item=ClickableFlowNode(QRectF(x,y,w,h),label,detail,fill,border,self._node_clicked)
            item.setToolTip(f"{label}\n\n{detail}")
            item.setZValue(1); scene.addItem(item)
            text=scene.addText(label); text.setFont(QFont("Arial",9,QFont.Weight.DemiBold)); text.setDefaultTextColor(QColor(COLORS["text"]))
            text.setTextWidth(w-20); text.setPos(x+10,y+(h-text.boundingRect().height())/2); text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            text.setZValue(1) 
            nodes[key]=(x,y,w,h)

        def edge(a,b,label="",active=False,warning=False,mode="down",color=None):
            if a not in nodes or b not in nodes: return
            ax,ay,aw,ah=nodes[a]; bx,by,bw,bh=nodes[b]
            c=color or ("#16803D" if active else ("#B42332" if warning else "#AAB6BF"))
            pen=QPen(QColor(c),3 if active else 1.6)
            if not active: pen.setStyle(Qt.PenStyle.DashLine)
            if mode=="right":
                p1=QPointF(ax+aw,ay+ah/2); p2=QPointF(bx,by+bh/2); mid=(p1.x()+p2.x())/2
                pts=[p1,QPointF(mid,p1.y()),QPointF(mid,p2.y()),p2]
            elif mode=="left":
                p1=QPointF(ax,ay+ah/2); p2=QPointF(bx+bw,by+bh/2); mid=min(p1.x(),p2.x())-35
                pts=[p1,QPointF(mid,p1.y()),QPointF(mid,p2.y()),p2]
            elif mode=="up":
                p1=QPointF(ax+aw/2,ay); p2=QPointF(bx+bw/2,by+bh); mid=(p1.y()+p2.y())/2
                pts=[p1,QPointF(p1.x(),mid),QPointF(p2.x(),mid),p2]
            else:
                p1=QPointF(ax+aw/2,ay+ah); p2=QPointF(bx+bw/2,by); mid=(p1.y()+p2.y())/2
                pts=[p1,QPointF(p1.x(),mid),QPointF(p2.x(),mid),p2]
            for p1,p2 in zip(pts,pts[1:]): scene.addLine(p1.x(),p1.y(),p2.x(),p2.y(),pen).setZValue(-1)
            p1,p2=pts[-2],pts[-1]; ang=math.atan2(p2.y()-p1.y(),p2.x()-p1.x()); size=8
            for d in (-0.55,0.55): scene.addLine(p2.x(),p2.y(),p2.x()-size*math.cos(ang+d),p2.y()-size*math.sin(ang+d),pen).setZValue(-1)
            if label:
                t=scene.addText(label); t.setFont(QFont("Arial",8,QFont.Weight.Bold)); t.setDefaultTextColor(QColor(c))
                t.setPos((pts[0].x()+pts[-1].x())/2+3,(pts[0].y()+pts[-1].y())/2-14)

        edge("start","load",active=True)
        edge("load","validate",active=True)
        edge("validate","decision",active=analysed or not valid)
        edge("decision","aggregate",label="YES",active=analysed and valid)
        # Invalid CSV branch loops back to the load/edit stage.
        if not valid:
            x,y,w,h=95,350,240,76
            bad=ClickableFlowNode(QRectF(x,y,w,h),"NO — correct CSV and reload",state.get("validation_detail","Fix missing columns or invalid numeric values, then load/validate again."),"#FFE0E3","#B42332",self._node_clicked)
            scene.addItem(bad); bad.setZValue(1)
            t=scene.addText("NO — return to Load inventory"); t.setFont(QFont("Arial",8,QFont.Weight.Bold)); t.setDefaultTextColor(QColor("#B42332")); t.setPos(95,330)
            edge("decision","load",label="NO / RELOAD",active=False,warning=True,mode="left")
            scene.addLine(215,350,215,222,QPen(QColor("#B42332"),2,Qt.PenStyle.DashLine))
        else:
            edge("aggregate","lookup",active=analysed)
            edge("lookup","expiry",active=analysed)
            edge("expiry","forecast",active=analysed)
            edge("forecast","optimise",active=analysed,mode="right",label=f"Selected: {method}" if analysed else "choose method")
            edge("optimise","budget",active=analysed)
            edge("budget","output",label="YES",active=analysed and under_budget,mode="left")
            edge("budget","adjust",label="NO",active=analysed and not under_budget,warning=analysed and not under_budget,mode="right")
            # A retry connector makes the budget reallocation loop explicit.
            if analysed and not under_budget:
                scene.addLine(1020,1025,1080,1025,QPen(QColor("#B42332"),2,Qt.PenStyle.DashLine))
                scene.addLine(1080,1025,1080,800,QPen(QColor("#B42332"),2,Qt.PenStyle.DashLine))
                scene.addLine(1080,800,990,800,QPen(QColor("#B42332"),2,Qt.PenStyle.DashLine))
                t=scene.addText("REVISE + REALLOCATE"); t.setFont(QFont("Arial",8,QFont.Weight.Bold)); t.setDefaultTextColor(QColor("#B42332")); t.setPos(990,785)
            if analysed and expiry_count:
                x,y,w,h=700,455,330,70
                detail=state.get("expiry_detail",f"{expiry_count} batch(es) are approaching expiry.")
                alert=ClickableFlowNode(QRectF(x,y,w,h),f"EXPIRY ALERT: {expiry_count} batch(es)",detail,"#FFF0CC","#D97706",self._node_clicked); scene.addItem(alert); alert.setZValue(1)
                scene.addItem(alert)
                alert.setZValue(1)
                
                t=scene.addText("Near-expiry batches are flagged before recommendation."); t.setFont(QFont("Arial",8)); t.setDefaultTextColor(QColor("#B45309")); t.setPos(x+8,y+48)
                t.setPos(x + 8, y + 48)
                t.setZValue(2)
                scene.addLine(640,504,700,490,QPen(QColor("#D97706"),2))
            if analysed:
                why=state.get("method_reason", "Knapsack DP selected for a hard budget with discrete order choices." if "knapsack" in str(method).lower() else "Greedy selected for a fast priority-based allocation.")
                x,y,w,h=1010,690,270,95
                rationale=ClickableFlowNode(QRectF(x,y,w,h),"WHY THIS METHOD?",why,"#DCEEFF",COLORS["border"],self._node_clicked); scene.addItem(rationale); rationale.setZValue(1)
                scene.addItem(rationale)
                rationale.setZValue(1)
                t=scene.addText("Click for method rationale"); t.setFont(QFont("Arial",8)); t.setDefaultTextColor(QColor(COLORS["muted"])); t.setPos(x+8,y+70)
                t.setPos(x + 8, y + 70)
                t.setZValue(2)
                scene.addLine(990,800,1010,738,QPen(QColor(COLORS["border"]),1.5,Qt.PenStyle.DashLine))

        footer=scene.addText("Green = executed path • Amber = expiry warning • Red = invalid CSV / over-budget retry • Grey dashed = inactive • Click nodes for details • Ctrl+wheel zoom • Drag to pan")
        footer.setFont(QFont("Arial",8)); footer.setDefaultTextColor(QColor(COLORS["muted"])); footer.setPos(24,1090)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-25,-20,30,35))
        self._zoom=1.0
        self.fitInView(scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)

    def _detail_for(self, key, state):
        return {
            "start": "Start the restocking workflow.",
            "load": "Load inventory CSV for all outlets and batches. Edit, add, or delete rows before analysis.",
            "validate": state.get("validation_detail", "Validate required columns and numeric values."),
            "decision": "If valid, continue. If invalid, correct the CSV and return to Load inventory.",
            "aggregate": state.get("aggregate_detail", "Combine batch records and calculate stock, demand, and expiry risk."),
            "lookup": state.get("lookup_detail", "Product lookup is via balanced search tree only."),
            "expiry": state.get("expiry_detail", "Use a priority queue so the earliest-expiring batch is handled first."),
            "forecast": state.get("forecast_detail", "Use linear regression for demand forecasting and merge sort for ranking."),
            "optimise": state.get("optimise_detail", "Choose greedy for speed and priority-based allocation, or knapsack DP for a discrete-value optimum under a hard budget."),
            "budget": state.get("budget_detail", "If over budget, adjust selection/quantities and rerun budget allocation. If within budget, offer plan export."),
            "output": state.get("output_detail", "Optionally export the final restocking plan."),
            "adjust": state.get("budget_detail", "Adjust item selection, reduce quantities, or review the budget, then redo budget allocation."),
        }.get(key, "Workflow step.")


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
        flow_tools = QHBoxLayout()
        flow_tools.addWidget(QLabel("Ctrl + mouse wheel: zoom • Drag: pan • Click a node: details"))
        flow_tools.addStretch(1)
        reset_flow_btn = QPushButton("Fit flowchart")
        reset_flow_btn.clicked.connect(self.flow_reset_zoom if hasattr(self, "flow_reset_zoom") else lambda: self.flow.reset_zoom())
        flow_tools.addWidget(reset_flow_btn)
        flow_layout.addLayout(flow_tools)
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
            "valid": True, "analysed": False,
            "subtitle": "Waiting for inventory CSV and analysis.",
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
                "valid": True, "analysed": False,
                "subtitle": f"CSV loaded: {len(df)} rows. Run analysis to generate a data-specific path.",
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
                "valid": False, "analysed": False,
                "subtitle": "CSV validation failed: invalid or missing data.",
                "validation_detail": "\n".join(errors),
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
            "valid": True, "analysed": True,
            "subtitle": f"CSV valid • {len(df)} batch rows • budget {money(budget)} • selected method: {selected_method}",
            "expiry_count": len(expiry_rows), "candidate_count": len(candidates),
            "under_budget": under_budget,
            "selected_method": selected_method,
            "method_reason": ("Knapsack DP evaluates discrete item/order choices under a hard budget; use it when maximising total value matters more than speed." if "knapsack" in selected_method.lower() else "Greedy allocates quickly in priority order and is simpler, but may not find the globally best combination under a hard budget."),
            "validation_detail": f"All {len(df)} rows passed required-column and numeric validation.",
            "aggregate_detail": f"Grouped {len(df)} batch rows into {grouped['item_id'].nunique()} unique products. Stock and expiry quantities were aggregated per product.",
            "expiry_detail": expiry_note,
            "forecast_detail": f"Daily demand × 30 used as the monthly estimate. {len(candidates)} product(s) have a positive recommended quantity.",
            "candidate_detail": f"{len(candidates)} candidate product(s) passed the positive-recommended-quantity filter.",
            "optimise_detail": f"Greedy spend: {money(greedy_spend)}; knapsack spend: {money(dp_spend)}. Selected: {selected_method}.",
            "budget_detail": f"Final spend {money(final_spend)} against budget {money(budget)}. " + ("Within budget." if under_budget else "Exceeds budget."),
            "output_detail": f"Final estimated spend: {money(final_spend)}; estimated gross profit: {money(final_profit)}; method: {selected_method}.",
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
