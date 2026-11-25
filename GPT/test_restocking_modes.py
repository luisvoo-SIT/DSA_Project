import os
import unittest
import threading
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from inventory import allocate, load_csv, recommendations, monthly_expired_units, FIELDS, OBJECTIVES, AllocationCancelled


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

    def test_balanced_spending_and_redistribution(self):
        from decimal import Decimal
        items=[dict(cost=Decimal(cost),need=100,value=value) for cost,value in [('10',100),('5',30),('2',5)]]
        result=allocate(items,60,'Balanced budget')
        self.assertEqual([r['qty']*r['cost'] for r in result],[20,20,20])
        self.assertTrue(all(r['allocation_method']=='Balanced budget' for r in result))
        # One capped product gives its unneeded share to the others.
        equal=[dict(cost=Decimal('10'),need=need,value=1) for need in (1,100,100)]
        result=allocate(equal,90,'Balanced budget')
        self.assertEqual([r['qty'] for r in result],[1,4,4])
        # Rank determines who gets a final indivisible unit when spending ties.
        result=allocate([dict(r,need=100) for r in equal],100,'Balanced budget')
        self.assertEqual([r['qty'] for r in result],[4,3,3])
        self.assertNotIn('qty',items[0])

    def test_balanced_budget_boundaries_and_cancellation(self):
        from decimal import Decimal
        items=[dict(cost=Decimal(cost),need=need,value=value) for cost,need,value in
               [('100',5,100),('3',5,20),('2',5,10),('1',5,0),('1',0,1)]]
        result=allocate(items,9,'Balanced budget')
        self.assertEqual([r['qty'] for r in result],[0,1,3,0,0])
        self.assertEqual(sum(r['qty']*r['cost'] for r in result),9)
        self.assertTrue(all(r['qty']==0 for r in allocate(items,0,'Balanced budget')))
        self.assertEqual(allocate([],600,'Balanced budget'),[])
        full=allocate(items,2000,'Balanced budget')
        self.assertTrue(all(r['qty']==r['need'] for r in full if r['value']>0))
        with self.assertRaises(AllocationCancelled):allocate(items,600,'Balanced budget',cancel=lambda:True)

    def test_balance_first_preserves_base_and_reuses_unspent_share(self):
        from decimal import Decimal
        items=[dict(cost=Decimal('10'),need=100,value=v) for v in (30,20,10)]
        for method in ('Greedy','Knapsack'):
            result=allocate(items,90,method,balance_percent=50)
            # $45 is reserved for balancing, but only $40 buys whole units.
            # The remaining $50, including that unused $5, goes to stage two.
            self.assertEqual([r['balanced_units'] for r in result],[2,1,1])
            self.assertEqual([r['priority_units'] for r in result],[5,0,0])
            self.assertEqual([r['qty'] for r in result],[7,1,1])
            self.assertEqual(sum(r['qty']*r['cost'] for r in result),90)
            self.assertTrue(all(r['qty']==r['balanced_units']+r['priority_units'] for r in result))
            self.assertTrue(all(r['allocation_method']==f'Balanced first + {method}' for r in result))

    def test_balance_first_second_stage_really_uses_chosen_algorithm(self):
        from decimal import Decimal
        items=[dict(cost=Decimal('6'),need=2,value=13),dict(cost=Decimal('5'),need=4,value=10)]
        greedy=allocate(items,16,'Greedy',balance_percent=50)
        knapsack=allocate(items,16,'Knapsack',balance_percent=50)
        self.assertEqual([r['balanced_units'] for r in greedy],[1,0])
        self.assertEqual([r['balanced_units'] for r in knapsack],[1,0])
        self.assertEqual([r['qty'] for r in greedy],[2,0])
        self.assertEqual([r['qty'] for r in knapsack],[1,2])
        for result in (greedy,knapsack):
            self.assertTrue(all(r['qty']<=r['need'] for r in result))
            self.assertLessEqual(sum(r['qty']*r['cost'] for r in result),16)

    def test_balance_first_percent_boundaries_and_limits(self):
        from decimal import Decimal
        items=[dict(cost=Decimal('2'),need=4,value=20),dict(cost=Decimal('3'),need=2,value=10)]
        for method in ('Greedy','Knapsack'):
            self.assertEqual(allocate(items,10,method),allocate(items,10,method,balance_percent=0))
            full=allocate(items,10,method,balance_percent=100)
            balanced=allocate(items,10,'Balanced budget')
            self.assertEqual([r['qty'] for r in full],[r['qty'] for r in balanced])
            self.assertTrue(all(r['priority_units']==0 for r in full))
            self.assertEqual(allocate([],10,method,balance_percent=50),[])
        for percent in (-1,101,12.5):
            with self.assertRaises(ValueError):allocate(items,10,'Greedy',balance_percent=percent)
        with self.assertRaises(ValueError):allocate(items,2000,'Knapsack',balance_percent=100)
        with self.assertRaises(ValueError):allocate(items,10,'Balanced budget',balance_percent=50)
        with self.assertRaises(AllocationCancelled):
            allocate(items,10,'Greedy',cancel=lambda:True,balance_percent=50)

    def test_balanced_youth_funds_variety_in_both_modes(self):
        rows=[r for r in self.records if r.location=='Outlet_Youth' and r.period.month==9]
        for objective in ('Popularity','Profit'):
            recs=recommendations(rows,objective)
            greedy=allocate(recs,600,'Greedy')
            balanced=allocate(recs,600,'Balanced budget')
            self.assertEqual(sum(r['qty']>0 for r in greedy),4)
            self.assertEqual(sum(r['qty']>0 for r in balanced),40)
            self.assertLessEqual(sum(r['qty']*r['cost'] for r in balanced),600)
            self.assertTrue(all(0<=r['qty']<=r['need'] for r in balanced))
            self.assertEqual([r['value'] for r in recs],[r['value'] for r in balanced])

    def test_main_objectives_change_only_scores_and_ranking(self):
        from datetime import date
        from decimal import Decimal
        a=replace(self.records[0],period=date(2026,11,30),batch_no='1126',lead_time=0,
                  shelf_life=90,item_id='A',unit_cost=Decimal('2.00'),unit_sell=Decimal('3.50'),
                  mth_purchase=120,mth_expired=0,current_total_stock=10)
        b=replace(a,item_id='B',unit_cost=Decimal('3.00'),unit_sell=Decimal('6.00'),mth_purchase=40)
        expected={'Availability + margin':{'A':250,'B':400},
                  'Popularity':{'A':12000,'B':4000},'Profit':{'A':150,'B':300}}
        for objective in OBJECTIVES:
            recs=recommendations([a,b],objective)
            self.assertEqual({r['item_id']:r['value'] for r in recs},expected[objective])
            self.assertEqual({r['item_id']:r['need'] for r in recs},{'A':120,'B':40})
            self.assertEqual(recs[0]['item_id'],'A' if objective=='Popularity' else 'B')
            self.assertTrue(all(r['objective']==objective for r in recs))
        # Main's availability base value is retained even at zero margin.
        zero=replace(a,unit_sell=a.unit_cost)
        self.assertEqual(recommendations([zero])[0]['value'],100)
        self.assertEqual(recommendations([zero],'Profit')[0]['value'],0)
        with self.assertRaises(ValueError):recommendations([a],'unknown')

    def test_replacement_series_and_allocation(self):
        sample = Path(__file__).parent / 'sample_data' / 'expiry_series'
        rows = []
        for month,target,usable,need in [(7,40,3,37),(8,34,6,28),(9,30,6,24),(10,27,6,21),(11,27,9,18)]:
            rows.extend(load_csv(sample / f'Outlet_ExpirySeries_2026_{month:02}.csv'))
            for objective in ('Profit','Popularity'):
                result = recommendations(rows,objective)
                r = result[0]
                self.assertEqual((r['stock_target'],r['usable'],r['need']),(target,usable,need))
                for method in ('Greedy','Knapsack'):
                    allocated = allocate(result,1000,method)[0]
                    self.assertEqual(allocated['qty'],need)
                    self.assertEqual(allocated['usable']+allocated['qty'],target)
            self.assertEqual(recommendations(rows),recommendations(list(reversed(rows))))

    def test_exact_example_and_disposed_expired_stock(self):
        from datetime import date
        base = replace(self.records[0],period=date(2026,11,30),lead_time=0,shelf_life=20,
                       current_total_stock=3,batch_no='1126',mth_purchase=7,mth_expired=40)
        expired = replace(base,current_total_stock=40,batch_no='1026')
        for records in ([base,expired],[base]):
            r = recommendations(records)[0]
            self.assertEqual(r['expired_this_month'],40)
            self.assertEqual(r['expired_replacement'],30)
            self.assertEqual(r['need'],37)
            self.assertEqual(r['stock_target'],40)
        # An unused historical initial target cannot affect the new rule.
        self.assertEqual(recommendations([base]),recommendations([replace(base,initial_stock_target=999)]))

    def test_no_expiry_odd_units_and_no_losses(self):
        from datetime import date
        row=replace(self.records[0],period=date(2026,11,30),batch_no='1126',lead_time=0,shelf_life=20,
                    current_total_stock=10,mth_purchase=7,mth_expired=0)
        r=recommendations([row])[0]
        self.assertEqual(r['need'],7)
        self.assertEqual(r['stock_target'],17)
        self.assertEqual(recommendations([replace(row,mth_expired=3)])[0]['need'],9)
        self.assertEqual(recommendations([replace(row,mth_purchase=0,mth_expired=0)])[0]['need'],0)
        # Unexpired stock with five days left is available, without a second credit rule.
        near=replace(row,batch_no='1026',shelf_life=35)
        r=recommendations([near])[0]
        self.assertEqual(r['usable'],10)
        self.assertEqual(r['near_expiry'],10)
        self.assertEqual(r['need'],7)

    def test_old_expired_batches_are_not_new_monthly_losses(self):
        from datetime import date
        row=replace(self.records[0],period=date(2026,11,30),batch_no='1026',lead_time=0,shelf_life=20,
                    current_total_stock=40,mth_purchase=7,mth_expired=None)
        self.assertEqual(monthly_expired_units([row])[0],40)
        retained=replace(row,period=date(2026,12,31))
        self.assertEqual(monthly_expired_units([retained])[0],0)
        r=recommendations([row,retained])[0]
        self.assertEqual(r['expired'],40)
        self.assertEqual(r['expired_this_month'],0)
        self.assertEqual(r['need'],7)
        self.assertEqual(r['need'],recommendations([retained])[0]['need'])

    def test_monthly_expired_roundtrip_and_validation(self):
        import csv,io
        sample = Path(__file__).parent / 'sample_data' / 'expiry_series'
        path = sample / 'Outlet_ExpirySeries_2026_07.csv'
        rows = load_csv(path)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer,fieldnames=FIELDS);writer.writeheader()
        writer.writerows({f:getattr(r,f) for f in FIELDS} for r in rows)
        self.assertEqual(rows,load_csv(path,buffer.getvalue()))
        # The same product's monthly losses repeat across batches, not sum.
        self.assertEqual(monthly_expired_units(rows)[0],40)
        with self.assertRaises(ValueError):
            load_csv(path,buffer.getvalue().replace(',40\r\n',',-1\r\n'))
        bad=io.StringIO();writer=csv.DictWriter(bad,fieldnames=FIELDS);writer.writeheader()
        writer.writerows({f:getattr(r,f) for f in FIELDS} for r in [rows[0],replace(rows[1],mth_expired=39)])
        with self.assertRaises(ValueError):load_csv(path,bad.getvalue())

    def test_latest_snapshot_and_asof_use_correct_history(self):
        from PySide6.QtWidgets import QApplication
        from app import MainWindow
        sample = Path(__file__).parent / 'sample_data' / 'expiry_series'
        paths = [sample / f'Outlet_ExpirySeries_2026_{month:02}.csv' for month in (7,8,9,10,11)]
        app = QApplication.instance() or QApplication([])
        window = MainWindow();window.files={str(p):load_csv(p) for p in paths};window.sync()
        self.wait_for(lambda:bool(window.all_results))
        self.assertEqual(window.all_results[0]['stock_target'],27)
        self.assertEqual(window.all_results[0]['stock'],9)
        window.asof.setCurrentIndex(1)
        self.wait_for(lambda:bool(window.all_results))
        r=window.all_results[0]
        self.assertEqual(r['forecast'],7)
        self.assertEqual(r['expired_this_month'],40)
        self.assertEqual(r['need'],37)
        window.budget.setValue(99)
        self.wait_for(lambda:bool(window.all_results))
        self.assertEqual(window.all_results[0]['stock_target'],40)
        # Editing monthly losses synchronizes across the product's batches.
        loss_column=2+FIELDS.index('mth_expired')
        window.table.item(0,loss_column).setText('20')
        self.wait_for(lambda:bool(window.all_results))
        self.assertEqual(window.all_results[0]['need'],22)
        july=[r for values in window.files.values() for r in values if r.period.month==7]
        self.assertTrue(all(r.mth_expired==20 for r in july))
        window.close()

    def test_ui_switch_recalculates(self):
        from PySide6.QtWidgets import QApplication
        from app import MainWindow
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        self.assertEqual([window.objective.itemText(i) for i in range(window.objective.count())],list(OBJECTIVES))
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

    def test_live_diagram_uses_replacement_rule(self):
        from PySide6.QtWidgets import QApplication
        from flowchart import Window
        app = QApplication.instance() or QApplication([])
        window = Window()
        text = window.preview_output.text()
        self.assertIn('Target stock: 40 units',text)
        self.assertIn('Indicative need: 37 units',text)
        window.inputs['mth_expired'].setValue(0)
        self.assertIn('Indicative need: 7 units',window.preview_output.text())
        window.close()

    def test_balanced_ui_search_and_export(self):
        import csv,tempfile
        from PySide6.QtWidgets import QApplication
        from app import MainWindow
        app=QApplication.instance() or QApplication([])
        window=MainWindow()
        window.rows=[r for r in self.records if r.location=='Outlet_Youth' and r.period.month==9]
        window.budget.setValue(600)
        window.objective.setCurrentText('Popularity')
        window.method.setCurrentText('Balanced budget')
        self.wait_for(lambda:bool(window.all_results))
        self.assertIn('Products funded: 40/40',window.summary.text())
        allocation={r['item_id']:r['qty'] for r in window.all_results}
        window.search.setText('DEMO001')
        self.wait_for(lambda:bool(window.all_results))
        self.assertEqual(window.results.rowCount(),1)
        self.assertEqual(allocation,{r['item_id']:r['qty'] for r in window.all_results})
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'balanced.csv')
            with patch('app.QFileDialog.getSaveFileName',return_value=(path,'CSV files (*.csv)')):
                window.export()
            with open(path,newline='',encoding='utf-8') as f:exported=list(csv.DictReader(f))
            self.assertEqual(len(exported),40)
            self.assertTrue(all(r['allocation_method']=='Balanced budget' for r in exported))
        window.close()

    def test_balance_first_controls_and_export(self):
        import csv,tempfile
        from PySide6.QtWidgets import QApplication
        from app import MainWindow
        app=QApplication.instance() or QApplication([])
        window=MainWindow()
        window.rows=[r for r in self.records if r.location=='Outlet_Youth' and r.period.month==9]
        window.budget.setValue(600); window.objective.setCurrentText('Profit')
        window.balance_first.setChecked(True)
        self.wait_for(lambda:bool(window.all_results))
        self.assertTrue(window.balance_share.isEnabled())
        self.assertEqual(sum(r['qty']>0 for r in window.all_results),40)
        self.assertTrue(all(r['balance_percent']==50 for r in window.all_results))
        self.assertLessEqual(sum(r['balanced_units']*r['cost'] for r in window.all_results),300)
        self.assertTrue(all(r['qty']==r['balanced_units']+r['priority_units'] for r in window.all_results))
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'hybrid.csv')
            with patch('app.QFileDialog.getSaveFileName',return_value=(path,'')):window.export()
            with open(path,newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
            self.assertTrue(all(r['allocation_method']=='Balanced first + Greedy' for r in rows))
            self.assertTrue(all(r['balance_percent']=='50' for r in rows))
        window.method.setCurrentText('Balanced budget')
        self.wait_for(lambda:bool(window.all_results))
        self.assertFalse(window.balance_first.isEnabled())
        self.assertFalse(window.balance_share.isEnabled())
        self.assertTrue(all(r['priority_units']==0 for r in window.all_results))
        window.method.setCurrentText('Greedy'); window.balance_first.setChecked(False)
        self.wait_for(lambda:bool(window.all_results))
        self.assertTrue(all(r['balanced_units']==0 for r in window.all_results))
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

        def slow_allocate(items, budget, method, cancel=None, balance_percent=0):
            if not started.is_set():
                started.set()
                release.wait(5)
            return allocate(items, budget, method, cancel=cancel,balance_percent=balance_percent)

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
