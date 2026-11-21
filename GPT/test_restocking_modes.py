import os
import unittest
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from inventory import allocate, load_csv, recommendations


class RestockingModesTest(unittest.TestCase):
    def wait_for(self, predicate, timeout=10):
        from PySide6.QtTest import QTest
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertTrue(predicate(), 'Timed out waiting for background allocation')

    @classmethod
    def setUpClass(cls):
        sample = Path(__file__).parent / 'sample_data'
        cls.records = []
        for outlet in ('Outlet_C', 'Outlet_Youth', 'Outlet_Community'):
            for month in (9, 10, 11):
                rows = load_csv(sample / f'{outlet}_2026_{month:02}.csv')
                assert len(rows) == (100 if outlet == 'Outlet_C' else 40)
                cls.records.extend(rows)

    def test_objectives_use_forecast_or_margin_and_change_allocations(self):
        rows = [r for r in self.records if r.location == 'Outlet_Youth']
        profit = recommendations(rows, 'Profit')
        popularity = recommendations(rows, 'Popularity')
        for item in profit:
            self.assertEqual(item['value'], max(0, int(item['margin'] * 100)))
        for item in popularity:
            self.assertAlmostEqual(item['value'] / 100, item['forecast'], places=2)
        for method in ('Greedy', 'Knapsack'):
            a = allocate(profit, 100, method)
            b = allocate(popularity, 100, method)
            self.assertNotEqual({r['item_id']: r['qty'] for r in a},
                                {r['item_id']: r['qty'] for r in b})
            for allocation in (a, b):
                self.assertLessEqual(sum(r['qty'] * r['cost'] for r in allocation), 100)
                self.assertTrue(all(0 <= r['qty'] <= r['need'] for r in allocation))

    def test_zero_profit_is_not_allocated(self):
        row = self.records[0]
        row = replace(row, unit_sell=row.unit_cost, mth_purchase=100, current_total_stock=0)
        for method in ('Greedy', 'Knapsack'):
            self.assertEqual(allocate(recommendations([row], 'Profit'), 100, method)[0]['qty'], 0)

    def test_ui_switch_recalculates(self):
        from PySide6.QtWidgets import QApplication
        from app import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        window.rows = [r for r in self.records if r.location == 'Outlet_Youth']
        window.recalculate()
        self.wait_for(lambda: bool(window.all_results))
        before = {r['item_id']: r['qty'] for r in window.all_results}
        window.objective.setCurrentText('Popularity')
        self.wait_for(lambda: bool(window.all_results))
        after = {r['item_id']: r['qty'] for r in window.all_results}
        self.assertNotEqual(before, after)
        self.assertTrue(all(r['objective'] == 'Popularity' for r in window.all_results))
        window.close()

    def test_budget_changes_remain_responsive_and_discard_stale_results(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        from app import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        window.rows = [r for r in self.records if r.location == 'Outlet_Youth']
        started = threading.Event()
        release = threading.Event()
        ticked = []

        def slow_allocate(items, budget, method, cancel=None):
            if not started.is_set():
                started.set()
                release.wait(5)
            return allocate(items, budget, method, cancel=cancel)

        with patch('app.allocate', side_effect=slow_allocate):
            window.recalculate()
            self.wait_for(started.is_set)
            window.budget.setValue(200)
            window.budget.setValue(300)
            QTimer.singleShot(10, lambda: ticked.append(True))
            self.wait_for(lambda: bool(ticked))
            self.assertEqual(window.all_results, [])
            release.set()
            self.wait_for(lambda: bool(window.all_results))
            self.assertLessEqual(sum(r['qty'] * r['cost'] for r in window.all_results), 300)
            self.assertIn('of 300.00', window.summary.text())
        window.close()


if __name__ == '__main__':
    unittest.main()
