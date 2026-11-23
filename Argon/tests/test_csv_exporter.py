import os
import tempfile
import unittest
from core.models import BatchRecord, ProductRecommendation
from core.csv_exporter import save_edited_csv, export_recommendations_csv
from core.csv_importer import import_monthly_csv


class TestCSVExporter(unittest.TestCase):

    def test_save_edited_csv_preserves_leading_zeroes_and_schema(self):
        b = BatchRecord(
            outlet="Outlet_SaveTest", report_year=2026, report_month=6,
            item_id="ITM-001", item_name="Fresh Milk", category="Dairy",
            unit_cost=2.25, unit_sell=3.50, current_total_stock=15,
            mth_purchase=80, lead_time=7, shelf_life=45,
            batch_no="0426", supplier_rating=4.5
        )

        tmp_dir = tempfile.mkdtemp()
        save_path = os.path.join(tmp_dir, "Outlet_SaveTest_2026_06.csv")

        save_edited_csv(save_path, [b])
        self.assertTrue(os.path.exists(save_path))

        # Re-import to verify round-trip integrity
        outlet, y, m, reloaded = import_monthly_csv(save_path)
        self.assertEqual(outlet, "Outlet_SaveTest")
        self.assertEqual(y, 2026)
        self.assertEqual(m, 6)
        self.assertEqual(len(reloaded), 1)
        r = reloaded[0]
        self.assertEqual(r.item_id, "ITM-001")
        self.assertEqual(r.batch_no, "0426")
        self.assertEqual(r.unit_cost, 2.25)
        self.assertEqual(r.unit_sell, 3.50)
        self.assertEqual(r.current_total_stock, 15)
        self.assertEqual(r.mth_purchase, 80)

    def test_export_recommendations_csv(self):
        rec = ProductRecommendation(
            outlet="Outlet_A", item_id="ITM-001", item_name="Milk",
            category="Dairy", unit_cost=2.00, unit_sell=3.50,
            predicted_monthly_demand=120, daily_demand=4.0,
            usable_stock=15, expiring_stock=10, target_stock=160,
            need=50, priority_value=250, value_per_cost=125.0, rank=1,
            allocated_units=30, allocated_cost=60.0, supplier_rating=4.8
        )

        tmp_dir = tempfile.mkdtemp()
        export_path = os.path.join(tmp_dir, "recs.csv")
        export_recommendations_csv(export_path, [rec])
        self.assertTrue(os.path.exists(export_path))

        with open(export_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)  # Header + 1 record
        self.assertIn("rank,objective,outlet,item_id", lines[0])
        self.assertIn("ITM-001", lines[1])
        self.assertIn("60.00", lines[1])


if __name__ == "__main__":
    unittest.main()
