import unittest
from core.models import BatchRecord
from core.priority_queue import BatchPriorityQueue


class TestBatchPriorityQueue(unittest.TestCase):

    def setUp(self):
        # Outlet A, 2026-06 (report date: 2026-06-30)
        # Batch 1: order 0526, lead 5 -> deliv 2026-06-05, shelf 30 -> exp 2026-07-05 -> remaining: 5 days
        self.b1 = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=6,
            item_id="ITM-001", item_name="Milk", category="Dairy",
            unit_cost=2.0, unit_sell=3.0, current_total_stock=10,
            mth_purchase=50, lead_time=5, shelf_life=30,
            batch_no="0526", supplier_rating=4.5
        )
        # Batch 2: order 0426, lead 10 -> deliv 2026-05-10, shelf 120 -> exp 2026-09-07 -> remaining: 69 days
        self.b2 = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=6,
            item_id="ITM-002", item_name="Bread", category="Bakery",
            unit_cost=1.5, unit_sell=2.5, current_total_stock=20,
            mth_purchase=80, lead_time=10, shelf_life=120,
            batch_no="0426", supplier_rating=4.0
        )
        # Batch 3: order 0326, lead 15 -> deliv 2026-04-15, shelf 45 -> exp 2026-05-30 -> remaining: -31 days (Expired)
        self.b3 = BatchRecord(
            outlet="Outlet_A", report_year=2026, report_month=6,
            item_id="ITM-003", item_name="Juice", category="Beverages",
            unit_cost=3.0, unit_sell=5.0, current_total_stock=5,
            mth_purchase=40, lead_time=15, shelf_life=45,
            batch_no="0326", supplier_rating=4.8
        )

    def test_priority_queue_ordering(self):
        pq = BatchPriorityQueue()
        pq.push(self.b2)  # remaining 69
        pq.push(self.b1)  # remaining 5
        pq.push(self.b3)  # remaining -31

        self.assertEqual(len(pq), 3)

        # Earliest remaining shelf life first
        first = pq.pop()
        self.assertEqual(first.item_id, "ITM-003")
        self.assertEqual(first.remaining_shelf_life, -31)

        second = pq.pop()
        self.assertEqual(second.item_id, "ITM-001")
        self.assertEqual(second.remaining_shelf_life, 5)

        third = pq.pop()
        self.assertEqual(third.item_id, "ITM-002")
        self.assertEqual(third.remaining_shelf_life, 69)

        self.assertTrue(pq.is_empty())

    def test_to_sorted_list_non_destructive(self):
        pq = BatchPriorityQueue()
        pq.push(self.b2)
        pq.push(self.b1)
        pq.push(self.b3)

        sorted_list = pq.to_sorted_list()
        self.assertEqual(len(sorted_list), 3)
        self.assertEqual(sorted_list[0].item_id, "ITM-003")
        self.assertEqual(sorted_list[1].item_id, "ITM-001")
        self.assertEqual(sorted_list[2].item_id, "ITM-002")

        # Ensure pq itself was not emptied
        self.assertEqual(len(pq), 3)


if __name__ == "__main__":
    unittest.main()
