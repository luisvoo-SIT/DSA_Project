import os
import unittest
from core.models import ProductRecommendation
from core.allocation import AllocationCancelled, allocate_greedy, allocate_knapsack, allocate_even, allocate_budget
from core.csv_importer import import_monthly_csv
from core.restocking import calculate_restocking_recommendations


class TestBudgetAllocation(unittest.TestCase):

    def setUp(self):
        # Product 1: Cost $2.00, Need 50, Priority 150 (Val/Cost: 75.0) -> Rank 2
        self.p1 = ProductRecommendation(
            outlet="Outlet_A", item_id="ITM-001", item_name="Milk",
            category="Dairy", unit_cost=2.00, unit_sell=3.50,
            predicted_monthly_demand=120, daily_demand=4.0,
            usable_stock=15, expiring_stock=10, target_stock=160,
            need=50, priority_value=150, value_per_cost=75.0, rank=2
        )
        # Product 2: Cost $1.50, Need 40, Priority 100 (Val/Cost: 66.67) -> Rank 1
        self.p2 = ProductRecommendation(
            outlet="Outlet_A", item_id="ITM-002", item_name="Bread",
            category="Bakery", unit_cost=1.50, unit_sell=2.50,
            predicted_monthly_demand=90, daily_demand=3.0,
            usable_stock=10, expiring_stock=0, target_stock=100,
            need=40, priority_value=100, value_per_cost=66.67, rank=1
        )
        # Product 3: Cost $5.00, Need 20, Priority 200 (Val/Cost: 40.0) -> Rank 3
        self.p3 = ProductRecommendation(
            outlet="Outlet_B", item_id="ITM-003", item_name="Coffee",
            category="Beverages", unit_cost=5.00, unit_sell=7.00,
            predicted_monthly_demand=60, daily_demand=2.0,
            usable_stock=20, expiring_stock=0, target_stock=80,
            need=20, priority_value=200, value_per_cost=40.0, rank=3
        )

    def test_greedy_allocation_partial_budget(self):
        items = [self.p2, self.p1, self.p3]
        budget = 100.00  # $100

        # p2: needs 40 @ $1.50 = $60.00. Fits completely! Rem = $40.00
        # p1: needs 50 @ $2.00 = $100.00. Can afford 40 / 2 = 20 units ($40.00). Rem = $0.00
        # p3: 0 units
        recs, rem = allocate_greedy(items, budget)

        self.assertEqual(rem, 0.0)
        self.assertEqual(recs[0].allocated_units, 40)
        self.assertEqual(recs[0].allocated_cost, 60.00)

        self.assertEqual(recs[1].allocated_units, 20)
        self.assertEqual(recs[1].allocated_cost, 40.00)

        self.assertEqual(recs[2].allocated_units, 0)
        self.assertEqual(recs[2].allocated_cost, 0.00)

    def test_knapsack_maximizes_score(self):
        items = [self.p2, self.p1, self.p3]
        budget = 120.00
        recs, rem = allocate_knapsack(items, budget)

        self.assertLessEqual(budget - rem, budget)
        total_spent = sum(r.allocated_cost for r in recs)
        self.assertAlmostEqual(total_spent + rem, budget, places=2)
        for r in recs:
            self.assertLessEqual(r.allocated_units, r.need)
            self.assertGreaterEqual(r.allocated_units, 0)

    def test_knapsack_budget_limit_exceeded(self):
        items = [self.p1, self.p2]
        with self.assertRaises(ValueError):
            allocate_knapsack(items, 1000.01)

    def test_zero_priority_score_not_allocated(self):
        zero_item = ProductRecommendation(
            outlet="Outlet_A", item_id="ITM-ZERO", item_name="Zero Margin",
            category="Dairy", unit_cost=2.00, unit_sell=2.00,
            predicted_monthly_demand=100, daily_demand=3.3,
            usable_stock=0, expiring_stock=0, target_stock=120,
            need=50, priority_value=0, value_per_cost=0.0, rank=1
        )
        for method in ("Greedy", "Knapsack"):
            recs, rem = allocate_budget([zero_item], 100.0, method=method)
            self.assertEqual(recs[0].allocated_units, 0)
            self.assertEqual(rem, 100.0)

    def test_profit_and_popularity_objectives_on_youth_dataset(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        batches = []
        for month in (9, 10, 11):
            fp = os.path.join(sample_dir, f"Outlet_Youth_2026_{month:02d}.csv")
            batches.extend(import_monthly_csv(fp)[3])

        for method in ("Greedy", "Knapsack"):
            profit_recs = calculate_restocking_recommendations(batches, objective="Profit")
            pop_recs = calculate_restocking_recommendations(batches, objective="Popularity")
            allocate_budget(profit_recs, 100.0, method=method)
            allocate_budget(pop_recs, 100.0, method=method)
            self.assertNotEqual(
                {r.item_id: r.allocated_units for r in profit_recs},
                {r.item_id: r.allocated_units for r in pop_recs},
            )

    def test_allocation_cancellation(self):
        with self.assertRaises(AllocationCancelled):
            allocate_budget([self.p1, self.p2], 100.0, method="Knapsack", cancel=lambda: True)



    def test_even_distribution_spreads_budget_across_variety_of_items(self):
        # 3 products: p2 ($1.50, need 40), p1 ($2.00, need 50), p3 ($5.00, need 20)
        # Under a $60.00 budget:
        # - Greedy spends all $60.00 on p2 (40 units) and funds 0 units of p1 and p3 (1 product funded).
        # - Even Distribution splits $60.00 into $20.00 shares across all 3 products:
        #   p2 gets 13 units ($19.50), p1 gets 10 units ($20.00), p3 gets 4 units ($20.00) -> all 3 products funded!
        items_greedy = [
            ProductRecommendation(**{**self.p2.__dict__}),
            ProductRecommendation(**{**self.p1.__dict__}),
            ProductRecommendation(**{**self.p3.__dict__}),
        ]
        items_even = [
            ProductRecommendation(**{**self.p2.__dict__}),
            ProductRecommendation(**{**self.p1.__dict__}),
            ProductRecommendation(**{**self.p3.__dict__}),
        ]
        allocate_budget(items_greedy, 60.0, method="Greedy")
        recs_even, rem_even = allocate_budget(items_even, 60.0, method="Even")

        greedy_funded = sum(1 for r in items_greedy if r.allocated_units > 0)
        even_funded = sum(1 for r in recs_even if r.allocated_units > 0)

        self.assertEqual(greedy_funded, 1)
        self.assertEqual(even_funded, 3)
        self.assertEqual(recs_even[0].allocated_units, 13)  # $19.50
        self.assertEqual(recs_even[1].allocated_units, 10)  # $20.00
        self.assertEqual(recs_even[2].allocated_units, 4)   # $20.00
        self.assertEqual(rem_even, 0.50)

    def test_even_distribution_round_robin_on_small_budget(self):
        # When budget ($9.00) is smaller than equal share for all 3 items, round-robin buys 1 unit of each
        items = [
            ProductRecommendation(**{**self.p2.__dict__}),  # $1.50
            ProductRecommendation(**{**self.p1.__dict__}),  # $2.00
            ProductRecommendation(**{**self.p3.__dict__}),  # $5.00
        ]
        recs, rem = allocate_even(items, 9.0)
        self.assertEqual([r.allocated_units for r in recs], [1, 1, 1])
        self.assertEqual(rem, 0.50)


if __name__ == "__main__":
    unittest.main()
