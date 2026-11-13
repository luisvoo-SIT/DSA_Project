"""
Main Window for Market Expand application.
"""
import os
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QFileDialog, QMessageBox,
    QStatusBar, QInputDialog
)
import pandas as pd
from core.models import BatchRecord
from core.csv_importer import import_monthly_csv
from core.csv_exporter import save_edited_csv, export_recommendations_csv
from ui.inventory_view import InventoryView
from ui.expiry_view import ExpiryView
from ui.recommendations_view import RecommendationsView
from ui.flowchart_view import ProcessDiagramWindow


class MainWindow(QMainWindow):
    """Market Expand main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Expand - Monthly Outlet Inventory & Restocking Allocation")
        self.resize(1200, 800)

        # In-memory master storage: list of all loaded BatchRecords
        self.master_batches: List[BatchRecord] = []
        # Keep track of imported files: (outlet, year, month) -> filepath
        self.imported_months: Dict[Tuple[str, int, int], str] = {}

        self.diagram_window: Optional[ProcessDiagramWindow] = None

        self._init_ui()
        self._init_toolbar()
        self._init_statusbar()

    def _init_ui(self):
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        # Tab 1: Inventory View
        self.inventory_view = InventoryView(self.master_batches, self)
        self.tabs.addTab(self.inventory_view, "Monthly Inventory")

        # Tab 2: Expiry Inspection View
        self.expiry_view = ExpiryView(self)
        self.tabs.addTab(self.expiry_view, "Batch Expiry Inspection")

        # Tab 3: Recommendations View
        self.recs_view = RecommendationsView(self)
        self.tabs.addTab(self.recs_view, "Restocking Recommendations")

        # Signals
        self.inventory_view.filterChanged.connect(self._sync_expiry_view)
        self.inventory_view.dataEdited.connect(self._on_inventory_data_edited)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _init_toolbar(self):
        toolbar = QToolBar("Main Toolbar", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        # Action: Import Monthly CSV
        import_act = QAction("Import monthly CSV", self)
        import_act.setStatusTip("Import one or more monthly outlet inventory CSV files")
        import_act.triggered.connect(self.import_csv_dialog)
        toolbar.addAction(import_act)

        # Action: Save Edited CSV
        save_act = QAction("Save edited CSV", self)
        save_act.setStatusTip("Persist in-memory edits for an outlet month to CSV")
        save_act.triggered.connect(self.save_edited_csv_dialog)
        toolbar.addAction(save_act)

        # Action: Export Recommendations CSV
        export_act = QAction("Export recommendations CSV", self)
        export_act.setStatusTip("Export all restocking recommendations and allocations to CSV")
        export_act.triggered.connect(self.export_recommendations_dialog)
        toolbar.addAction(export_act)

        toolbar.addSeparator()

        # Action: Process Diagram
        diagram_act = QAction("Process Diagram", self)
        diagram_act.setStatusTip("Open editable process flowchart and live calculation panel")
        diagram_act.triggered.connect(self.open_process_diagram)
        toolbar.addAction(diagram_act)

    def _init_statusbar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Click 'Import monthly CSV' to load inventory data.")

    def import_csv_dialog(self):
        """Allows selecting one or more monthly CSV files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Monthly CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not files:
            return

        imported_count = 0
        for fp in files:
            try:
                outlet, year, month, batches = import_monthly_csv(fp)
                key = (outlet, year, month)

                # Check if outlet and month already exist in memory
                if key in self.imported_months:
                    reply = QMessageBox.question(
                        self,
                        "Replace Existing Month Records?",
                        f"Records for {outlet} ({year}-{month:02d}) already exist.\n\n"
                        f"Do you want to replace that month's records with '{os.path.basename(fp)}'?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        continue
                    # Remove existing records for this outlet/month
                    self.master_batches = [
                        b for b in self.master_batches
                        if not (b.outlet == outlet and b.report_year == year and b.report_month == month)
                    ]

                self.imported_months[key] = fp
                self.master_batches.extend(batches)
                imported_count += 1

            except Exception as e:
                QMessageBox.critical(self, f"Import Error ({os.path.basename(fp)})", str(e))

        if imported_count > 0:
            self._refresh_all_views()
            self.status_bar.showMessage(
                f"Successfully imported {imported_count} file(s). Total batches: {len(self.master_batches)}"
            )

    def save_edited_csv_dialog(self):
        """Persists edited in-memory records for a selected month."""
        if not self.master_batches:
            QMessageBox.information(self, "No Data", "No inventory data loaded to save.")
            return

        # List unique (outlet, year, month)
        month_keys = sorted(list({(b.outlet, b.report_year, b.report_month) for b in self.master_batches}))
        options = [f"{o} ({y}-{m:02d})" for o, y, m in month_keys]

        choice, ok = QInputDialog.getItem(
            self,
            "Save Edited CSV",
            "Select outlet and month to save:",
            options,
            0,
            False
        )
        if not ok or not choice:
            return

        idx = options.index(choice)
        sel_outlet, sel_year, sel_month = month_keys[idx]

        # Filter batches for selected outlet and month
        target_batches = [
            b for b in self.master_batches
            if b.outlet == sel_outlet and b.report_year == sel_year and b.report_month == sel_month
        ]

        default_name = f"{sel_outlet}_{sel_year:04d}_{sel_month:02d}.csv"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Edited CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not save_path:
            return

        try:
            save_edited_csv(save_path, target_batches)
            QMessageBox.information(
                self,
                "CSV Saved",
                f"Successfully persisted {len(target_batches)} records for {sel_outlet} ({sel_year}-{sel_month:02d}) to:\n{save_path}"
            )
            self.status_bar.showMessage(f"Saved {os.path.basename(save_path)}.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def export_recommendations_dialog(self):
        """Exports calculated restocking recommendations to CSV."""
        recs = self.recs_view.get_all_recommendations()
        if not recs:
            QMessageBox.information(self, "No Recommendations", "No recommendations available to export.")
            return

        default_name = "restocking_recommendations.csv"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Recommendations CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not save_path:
            return

        try:
            export_recommendations_csv(save_path, recs)
            QMessageBox.information(
                self,
                "Recommendations Exported",
                f"Successfully exported {len(recs)} recommendation records to:\n{save_path}"
            )
            self.status_bar.showMessage(f"Exported recommendations to {os.path.basename(save_path)}.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def open_process_diagram(self):
        """Opens or displays the editable process diagram window."""
        if self.diagram_window is None:
            self.diagram_window = ProcessDiagramWindow()
        self.diagram_window.show()
        self.diagram_window.raise_()
        self.diagram_window.activateWindow()

    def _sync_expiry_view(self):
        """Synchronizes the expiry view using the filtered dataframe from inventory view."""
        df_filtered = self.inventory_view.get_filtered_dataframe()
        self.expiry_view.update_view(df_filtered, self.master_batches)

    def _on_inventory_data_edited(self):
        """Called when user edits values in inventory table."""
        self._sync_expiry_view()
        self.recs_view.set_master_batches(self.master_batches)
        self.status_bar.showMessage("Inventory edits applied and recommendations recalculated.")

    def _refresh_all_views(self):
        """Refreshes all views after import or major updates."""
        self.inventory_view.master_batches = self.master_batches
        self.inventory_view.table_model.master_batches = self.master_batches
        self.inventory_view.refresh()
        self._sync_expiry_view()
        self.recs_view.set_master_batches(self.master_batches)

    def _on_tab_changed(self, index: int):
        if index == 1:
            self._sync_expiry_view()
        elif index == 2:
            self.recs_view.recalculate_and_display()



