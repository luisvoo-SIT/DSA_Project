import os
import tempfile
import unittest
from core.csv_importer import import_monthly_csv, parse_filename, validate_price_precision
from core.models import parse_batch_dates


class TestCSVImporter(unittest.TestCase):

    def test_parse_filename_valid(self):
        outlet, year, month = parse_filename("Outlet_A_2026_06.csv")
        self.assertEqual(outlet, "Outlet_A")
        self.assertEqual(year, 2026)
        self.assertEqual(month, 6)

        outlet, year, month = parse_filename("/path/to/Downtown_Store_North_2025_12.csv")
        self.assertEqual(outlet, "Downtown_Store_North")
        self.assertEqual(year, 2025)
        self.assertEqual(month, 12)

    def test_parse_filename_invalid(self):
        with self.assertRaises(ValueError):
            parse_filename("invalid_name.csv")
        with self.assertRaises(ValueError):
            parse_filename("Outlet_2026_13.csv")  # Month 13 invalid
        with self.assertRaises(ValueError):
            parse_filename("Outlet_2026_00.csv")  # Month 00 invalid

    def test_price_precision(self):
        self.assertEqual(validate_price_precision("2.50"), 2.50)
        self.assertEqual(validate_price_precision("10"), 10.0)
        self.assertEqual(validate_price_precision("0.99"), 0.99)
        with self.assertRaises(ValueError):
            validate_price_precision("1.234")  # 3 decimal places rejected

    def test_sample_files_import(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        files = [
            "Outlet_A_2026_05.csv",
            "Outlet_A_2026_06.csv",
            "Outlet_B_2026_06.csv",
        ]
        for fname in files:
            fp = os.path.join(sample_dir, fname)
            outlet, year, month, batches = import_monthly_csv(fp)
            self.assertTrue(len(batches) > 0)
            for b in batches:
                self.assertEqual(b.outlet, outlet)
                self.assertEqual(b.report_year, year)
                self.assertEqual(b.report_month, month)
                self.assertEqual(len(b.batch_no), 4)

    def _create_temp_csv(self, filename: str, content: str) -> str:
        tmp_dir = tempfile.mkdtemp()
        path = os.path.join(tmp_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        return path

    def test_reject_duplicate_product_batch(self):
        content = """item_id,item_name,category,unit_cost,unit_sell,current_total_stock,mth_purchase,lead_time,shelf_life,batch_no,supplier_rating
ITM-001,Milk,Dairy,2.00,3.00,10,50,5,30,0526,4.5
ITM-001,Milk,Dairy,2.00,3.00,15,50,5,30,0526,4.5
"""
        csv_path = self._create_temp_csv("Outlet_Test_2026_06.csv", content)
        with self.assertRaises(ValueError) as ctx:
            import_monthly_csv(csv_path)
        self.assertIn("Duplicate product/batch pair detected", str(ctx.exception))

    def test_reject_negative_quantity(self):
        content = """item_id,item_name,category,unit_cost,unit_sell,current_total_stock,mth_purchase,lead_time,shelf_life,batch_no,supplier_rating
ITM-001,Milk,Dairy,2.00,3.00,-5,50,5,30,0526,4.5
"""
        csv_path = self._create_temp_csv("Outlet_Test_2026_06.csv", content)
        with self.assertRaises(ValueError) as ctx:
            import_monthly_csv(csv_path)
        self.assertIn("current_total_stock cannot be negative", str(ctx.exception))

    def test_reject_mismatched_monthly_purchases(self):
        content = """item_id,item_name,category,unit_cost,unit_sell,current_total_stock,mth_purchase,lead_time,shelf_life,batch_no,supplier_rating
ITM-001,Milk,Dairy,2.00,3.00,10,50,5,30,0526,4.5
ITM-001,Milk,Dairy,2.00,3.00,15,60,5,30,0426,4.5
"""
        csv_path = self._create_temp_csv("Outlet_Test_2026_06.csv", content)
        with self.assertRaises(ValueError) as ctx:
            import_monthly_csv(csv_path)
        self.assertIn("Inconsistent mth_purchase", str(ctx.exception))

    def test_reject_delivery_after_report_date(self):
        # Order month 0626 (last day: 2026-06-30). Lead time 5 days -> delivery: 2026-07-05.
        # Report month: 2026_06 (report date: 2026-06-30). Delivery > Report Date!
        content = """item_id,item_name,category,unit_cost,unit_sell,current_total_stock,mth_purchase,lead_time,shelf_life,batch_no,supplier_rating
ITM-001,Milk,Dairy,2.00,3.00,10,50,5,30,0626,4.5
"""
        csv_path = self._create_temp_csv("Outlet_Test_2026_06.csv", content)
        with self.assertRaises(ValueError) as ctx:
            import_monthly_csv(csv_path)
        self.assertIn("assumed delivery date", str(ctx.exception))
        self.assertIn("is after report date", str(ctx.exception))



    def test_optional_mth_expired_validation(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data", "expiry_series")
        fp = os.path.join(sample_dir, "Outlet_ExpirySeries_2026_07.csv")
        _, _, _, batches = import_monthly_csv(fp)
        self.assertEqual(len(batches), 2)
        self.assertTrue(all(b.mth_expired == 40 for b in batches))

        # Reject conflicting mth_expired across batches of same product
        bad_content = """item_id,item_name,category,unit_cost,unit_sell,current_total_stock,mth_purchase,lead_time,shelf_life,batch_no,supplier_rating,mth_expired
ITM-001,Milk,Dairy,2.00,3.00,10,50,5,30,0526,4.5,40
ITM-001,Milk,Dairy,2.00,3.00,15,50,5,30,0426,4.5,39
"""
        csv_path = self._create_temp_csv("Outlet_Test_2026_06.csv", bad_content)
        with self.assertRaises(ValueError) as ctx:
            import_monthly_csv(csv_path)
        self.assertIn("Inconsistent mth_expired", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
