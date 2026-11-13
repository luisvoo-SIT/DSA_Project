import os
import unittest
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.flowchart_view import ProcessDiagramWindow

# Ensure QApplication exists for GUI tests
app = QApplication.instance()
if app is None:
    app = QApplication([])


class TestUI(unittest.TestCase):

    def setUp(self):
        self.window = MainWindow()

    def test_window_init_and_tabs(self):
        self.assertEqual(self.window.tabs.count(), 3)
        self.assertEqual(self.window.tabs.tabText(0), "Monthly Inventory")
        self.assertEqual(self.window.tabs.tabText(1), "Batch Expiry Inspection")
        self.assertEqual(self.window.tabs.tabText(2), "Restocking Recommendations")

    def test_sample_files_import_into_ui(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        files = [
            os.path.join(sample_dir, "Outlet_A_2026_05.csv"),
            os.path.join(sample_dir, "Outlet_A_2026_06.csv"),
            os.path.join(sample_dir, "Outlet_B_2026_06.csv"),
        ]

        from core.csv_importer import import_monthly_csv
        for fp in files:
            outlet, y, m, batches = import_monthly_csv(fp)
            self.window.imported_months[(outlet, y, m)] = fp
            self.window.master_batches.extend(batches)

        self.window._refresh_all_views()

        # Check inventory table model rows
        self.assertEqual(self.window.inventory_view.table_model.rowCount(), 25)

        # Switch to tab 1 (Expiry)
        self.window.tabs.setCurrentIndex(1)
        self.assertEqual(self.window.expiry_view.table_model.rowCount(), 25)

        # Switch to tab 2 (Recommendations)
        self.window.tabs.setCurrentIndex(2)
        self.assertGreater(self.window.recs_view.table_model.rowCount(), 0)

        # Check flowchart window
        diagram = ProcessDiagramWindow()
        self.assertGreater(len(diagram.scene.nodes), 0)


if __name__ == "__main__":
    unittest.main()
