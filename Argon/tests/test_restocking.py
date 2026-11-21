import unittest
from core.models import BatchRecord
from core.restocking import calculate_restocking_recommendations


class TestRestocking(unittest.TestCase):

    def test_restocking_calculations(self):
        # 1 Product at Outlet A across 2 months
        # May 2026 (31 days): mth_purchase = 60
        b_may = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=5,
            item_id="ITM-001", item_name="Milk", category="Dairy",
            unit_cost=2.00, unit_sell=3.50, current_total_stock=20,
            mth_purchase=60, lead_time=10, shelf_life=40,
            batch_no="0426", supplier_rating=4.5
        )
        # June 2026 (30 days): mth_purchase = 90
        # Two batches in June:
        # Batch 1: order 0526, lead 10 -> delivery 2026-06-10. Shelf 40 -> exp 2026-07-20.
        # Report date: 2026-06-30. Remaining: 20 days (>14d -> Usable!)
        b_june1 = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=6,
            item_id="ITM-001", item_name="Milk", category="Dairy",
            unit_cost=2.00, unit_sell=3.50, current_total_stock=15,
            mth_purchase=90, lead_time=10, shelf_life=40,
            batch_no="0526", supplier_rating=4.5
        )
        # Batch 2: order 0426, lead 10 -> delivery 2026-05-10. Shelf 40 -> exp 2026-06-19.
        # Report date: 2026-06-30. Remaining: -11 days (Expired! <=14d -> Expiring stock!)
        b_june2 = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=6,
            item_id="ITM-001", item_name="Milk", category="Dairy",
            unit_cost=2.00, unit_sell=3.50, current_total_stock=10,
            mth_purchase=90, lead_time=10, shelf_life=40,
            batch_no="0426", supplier_rating=4.5
        )

        batches = [b_may, b_june1, b_june2]
        recs = calculate_restocking_recommendations(batches)

        self.assertEqual(len(recs), 1)
        r = recs[0]

        # Forecast: May = 60, June = 90 (+30 trend) -> Target July forecast = 120
        self.assertAlmostEqual(r.predicted_monthly_demand, 120.0, places=4)

        # Days in June = 30 -> Daily demand = 120 / 30 = 4.0
        self.assertAlmostEqual(r.daily_demand, 4.0, places=4)

        # Lead time = 10 -> Target stock covers lead time + 30 days = 40 days -> 4.0 * 40 = 160.0
        self.assertAlmostEqual(r.target_stock, 160.0, places=4)

        # Usable stock: only batch 1 (15 units). Expiring stock: batch 2 (10 units).
        self.assertEqual(r.usable_stock, 15.0)
        self.assertEqual(r.expiring_stock, 10.0)

        # Raw need = target_stock - usable_stock = 160 - 15 = 145.0
        # Shelf life cap = daily_demand * shelf_life = 4.0 * 40 = 160.0
        # Capped need = min(145.0, 160.0) = 145 discrete units
        self.assertEqual(r.need, 145)

        # Priority value:
        # Gross margin = 3.50 - 2.00 = 1.50 -> 150 cents
        # Priority value = 100 + 150 = 250 points
        self.assertEqual(r.priority_value, 250)

        # Value per cost = 250 / 2.00 = 125.0
        self.assertAlmostEqual(r.value_per_cost, 125.0, places=4)


if __name__ == "__main__":
    unittest.main()
