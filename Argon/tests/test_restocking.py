import os
import unittest
from core.models import BatchRecord
from core.csv_importer import import_monthly_csv
from core.restocking import OBJECTIVES, calculate_restocking_recommendations
from core.allocation import allocate_budget


class TestRestocking(unittest.TestCase):

    def test_restocking_replacement_rule_and_objectives(self):
        # 1 Product at Outlet A across 2 months
        b_may = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=5,
            item_id="ITM-001", item_name="Milk", category="Dairy",
            unit_cost=2.00, unit_sell=3.50, current_total_stock=20,
            mth_purchase=60, lead_time=10, shelf_life=40,
            batch_no="0426", supplier_rating=4.5
        )
        # June 2026: mth_purchase = 90
        # Batch 1: order 0526, lead 10 -> delivery 2026-06-10, shelf 40 -> exp 2026-07-20 (remaining: 20d > 0 -> Usable)
        b_june1 = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=6,
            item_id="ITM-001", item_name="Milk", category="Dairy",
            unit_cost=2.00, unit_sell=3.50, current_total_stock=15,
            mth_purchase=90, lead_time=10, shelf_life=40,
            batch_no="0526", supplier_rating=4.5
        )
        # Batch 2: order 0426, lead 10 -> delivery 2026-05-10, shelf 40 -> exp 2026-06-19 (falls in June 2026 -> expired this month!)
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

        # Forecast: May = 60, June = 90 (+30 trend) -> Target July forecast = 120.0
        self.assertAlmostEqual(r.predicted_monthly_demand, 120.0, places=4)
        self.assertAlmostEqual(r.daily_demand, 4.0, places=4)

        # Usable (unexpired) stock: 15 units. Expired stock on hand: 10 units (expired in June 2026).
        self.assertEqual(r.usable_stock, 15.0)
        self.assertEqual(r.expired_stock, 10.0)
        self.assertEqual(r.expired_this_month, 10)
        self.assertEqual(r.expired_replacement, 7)  # floor(10 * 75%) = 7

        # Replacement need = sold (90) + expired_replacement (7) = 97
        self.assertEqual(r.need, 97)
        # New total target = usable (15) + need (97) = 112
        self.assertEqual(r.target_stock, 112.0)

        # Default objective: Availability + margin = 100 + 150 = 250
        self.assertEqual(r.objective, "Availability + margin")
        self.assertEqual(r.priority_value, 250)
        self.assertAlmostEqual(r.value_per_cost, 125.0, places=4)

        # Profit objective: margin cents = 150
        profit_rec = calculate_restocking_recommendations(batches, objective="Profit")[0]
        self.assertEqual(profit_rec.priority_value, 150)
        self.assertEqual(profit_rec.need, 97)

        # Popularity objective: forecast (120) * 100 = 12000
        pop_rec = calculate_restocking_recommendations(batches, objective="Popularity")[0]
        self.assertEqual(pop_rec.priority_value, 12000)
        self.assertEqual(pop_rec.need, 97)

    def test_five_month_expiry_series_progression(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data", "expiry_series")
        batches = []
        for month in (7, 8, 9, 10, 11):
            fp = os.path.join(sample_dir, f"Outlet_ExpirySeries_2026_{month:02d}.csv")
            batches.extend(import_monthly_csv(fp)[3])

        expected = [
            # (month, sold, expired_this_month, usable_left, replace_75, buy_need, new_target)
            (7, 7, 40, 3, 30, 37, 40),
            (8, 10, 24, 6, 18, 28, 34),
            (9, 12, 16, 6, 12, 24, 30),
            (10, 14, 10, 6, 7, 21, 27),
            (11, 18, 0, 9, 0, 18, 27),
        ]
        for month, sold, exp_mth, usable, repl, buy, target in expected:
            rec = calculate_restocking_recommendations(batches, as_of_ym=(2026, month))[0]
            allocate_budget([rec], 1000.0, method="Greedy")
            self.assertEqual(rec.latest_sales, sold)
            self.assertEqual(rec.expired_this_month, exp_mth)
            self.assertEqual(rec.usable_stock, usable)
            self.assertEqual(rec.expired_replacement, repl)
            self.assertEqual(rec.need, buy)
            self.assertEqual(rec.target_stock, target)
            self.assertEqual(rec.allocated_units, buy)
            self.assertEqual(rec.projected_stock, target)


if __name__ == "__main__":
    unittest.main()
