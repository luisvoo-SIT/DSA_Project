import os
import unittest
from core.csv_importer import import_monthly_csv
from core.restocking import calculate_restocking_recommendations
from core.allocation import allocate_budget
from core.bst import AVLTree
from core.priority_queue import BatchPriorityQueue


class TestEndToEnd(unittest.TestCase):

    def test_full_pipeline_with_sample_data(self):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        files = [
            os.path.join(sample_dir, "Outlet_A_2026_05.csv"),
            os.path.join(sample_dir, "Outlet_A_2026_06.csv"),
            os.path.join(sample_dir, "Outlet_B_2026_06.csv"),
        ]

        # 1. Import all files
        all_batches = []
        for fp in files:
            outlet, y, m, batches = import_monthly_csv(fp)
            self.assertTrue(len(batches) > 0)
            all_batches.extend(batches)

        self.assertEqual(len(all_batches), 25)

        # 2. Expiry inspection with Priority Queue
        pq = BatchPriorityQueue()
        for b in all_batches:
            pq.push(b)
        sorted_expiry = pq.to_sorted_list()
        self.assertEqual(len(sorted_expiry), 25)
        # Ensure remaining shelf life is non-decreasing in the priority queue
        for i in range(len(sorted_expiry) - 1):
            self.assertLessEqual(sorted_expiry[i].remaining_shelf_life, sorted_expiry[i + 1].remaining_shelf_life)

        # 3. Restocking Recommendations (Shared Budget across Outlet A & Outlet B)
        recs = calculate_restocking_recommendations(all_batches)
        self.assertGreater(len(recs), 0)

        # Verify rank order (value per cost descending)
        for i in range(len(recs) - 1):
            self.assertGreaterEqual(recs[i].value_per_cost, recs[i + 1].value_per_cost)

        # 4. Budget Allocation with Greedy
        budget = 500.0
        recs_greedy, rem_greedy = allocate_budget(recs, budget=budget, method="Greedy")
        self.assertGreaterEqual(rem_greedy, 0.0)
        total_greedy_spent = sum(r.allocated_cost for r in recs_greedy)
        self.assertLessEqual(total_greedy_spent, budget)

        # 5. Budget Allocation with Bounded Knapsack
        recs_knap, rem_knap = allocate_budget(recs, budget=budget, method="Knapsack")
        self.assertGreaterEqual(rem_knap, 0.0)
        total_knap_spent = sum(r.allocated_cost for r in recs_knap)
        self.assertLessEqual(total_knap_spent, budget)

        # 6. Exact Product Lookup with AVL Tree
        tree = AVLTree()
        for r in recs:
            tree.insert(r.item_id, r)

        match = tree.search("ITM-001")
        self.assertIsNotNone(match)
        self.assertEqual(match.item_id, "ITM-001")


if __name__ == "__main__":
    unittest.main()
