import os
import unittest
from PySide6.QtWidgets import QApplication
from core.restocking import OBJECTIVES
from ui.main_window import MainWindow
from ui.flowchart_view import ProcessDiagramWindow

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
        view = self.window.recs_view
        self.assertEqual(
            [view.objective_combo.itemText(i) for i in range(view.objective_combo.count())],
            list(OBJECTIVES),
        )

    def test_objective_switch_reallocates_demo_data(self):
        from core.csv_importer import import_monthly_csv
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        batches = []
        for month in (9, 10, 11):
            batches.extend(import_monthly_csv(os.path.join(sample_dir, f"Outlet_Youth_2026_{month:02d}.csv"))[3])
        view = self.window.recs_view
        view.budget_spin.setValue(100.0)
        view.set_master_batches(batches)
        view.objective_combo.setCurrentIndex(view.objective_combo.findData("Profit"))
        profit = {r.item_id: r.allocated_units for r in view.all_recommendations}
        view.objective_combo.setCurrentIndex(view.objective_combo.findData("Popularity"))
        popularity = {r.item_id: r.allocated_units for r in view.all_recommendations}
        self.assertNotEqual(profit, popularity)
        self.assertTrue(all(r.objective == "Popularity" for r in view.all_recommendations))
        self.assertLessEqual(sum(r.allocated_cost for r in view.all_recommendations), 100.0)

    def test_asof_selector_and_mth_expired_batch_sync(self):
        from core.csv_importer import import_monthly_csv
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data", "expiry_series")
        for month in (7, 8, 9, 10, 11):
            fp = os.path.join(sample_dir, f"Outlet_ExpirySeries_2026_{month:02d}.csv")
            outlet, y, m, batches = import_monthly_csv(fp)
            self.window.imported_months[(outlet, y, m)] = fp
            self.window.master_batches.extend(batches)

        self.window._refresh_all_views()
        view = self.window.recs_view
        # Latest month (Nov 2026): target_stock = 27
        self.assertEqual(view.all_recommendations[0].target_stock, 27.0)

        # Select As of 2026-07 (index 1)
        view.asof_combo.setCurrentIndex(1)
        r_july = view.all_recommendations[0]
        self.assertEqual(r_july.expired_this_month, 40)
        self.assertEqual(r_july.need, 37)
        self.assertEqual(r_july.target_stock, 40.0)

        # Edit mth_expired in Inventory table for July 2026 from 40 to 20
        inv_model = self.window.inventory_view.table_model
        exp_col = [i for i, c in enumerate(inv_model.COLUMNS) if c[0] == "mth_expired"][0]
        idx = inv_model.index(0, exp_col)
        self.assertTrue(inv_model.setData(idx, "20"))
        july_batches = [b for b in self.window.master_batches if b.report_month == 7]
        self.assertTrue(all(b.mth_expired == 20 for b in july_batches))
        # Need updates to 7 + floor(20 * 0.75) = 22
        self.assertEqual(view.all_recommendations[0].need, 22)

    def test_live_diagram_uses_replacement_rule(self):
        diagram = ProcessDiagramWindow()
        text = diagram.output_view.toPlainText()
        self.assertIn("Target Stock: 3 + 37 = 40 units", text)
        self.assertIn("Indicative Need: 7 + 30 = 37 units", text)
        diagram.expired_spin.setValue(0)
        self.assertIn("Indicative Need: 7 + 0 = 7 units", diagram.output_view.toPlainText())

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
        self.assertEqual(self.window.inventory_view.table_model.rowCount(), 25)
        self.window.tabs.setCurrentIndex(1)
        self.assertEqual(self.window.expiry_view.table_model.rowCount(), 25)
        self.window.tabs.setCurrentIndex(2)
        self.assertGreater(self.window.recs_view.table_model.rowCount(), 0)



    def test_even_distribution_method_in_ui_increases_product_variety(self):
        from core.csv_importer import import_monthly_csv
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        batches = []
        for month in (9, 10, 11):
            batches.extend(import_monthly_csv(os.path.join(sample_dir, f"Outlet_Youth_2026_{month:02d}.csv"))[3])
        view = self.window.recs_view
        view.budget_spin.setValue(100.0)
        view.set_master_batches(batches)

        # Greedy at $100.00 funds only the top few products
        view.method_combo.setCurrentIndex(view.method_combo.findData("Greedy"))
        greedy_funded = sum(1 for r in view.all_recommendations if r.allocated_units > 0)

        # Switching to Even Distribution (Variety) funds many more products across the assortment
        view.method_combo.setCurrentIndex(view.method_combo.findData("Even"))
        even_funded = sum(1 for r in view.all_recommendations if r.allocated_units > 0)

        self.assertGreater(even_funded, greedy_funded)
        self.assertLessEqual(sum(r.allocated_cost for r in view.all_recommendations), 100.0)


if __name__ == "__main__":
    unittest.main()
