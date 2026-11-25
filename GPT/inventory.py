"""Inventory loading and transparent, bounded restocking recommendations."""
import calendar
import csv
import heapq
import io
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

REQUIRED_FIELDS = ('item_id','item_name','category','unit_cost','unit_sell','current_total_stock','mth_purchase','lead_time','shelf_life','batch_no','supplier_rating')
FIELDS = REQUIRED_FIELDS + ('initial_stock_target', 'mth_expired')

@dataclass(frozen=True)
class Batch:
    location: str
    period: date
    item_id: str
    item_name: str
    category: str
    unit_cost: Decimal
    unit_sell: Decimal
    current_total_stock: int
    mth_purchase: int
    lead_time: int
    shelf_life: int
    batch_no: str
    supplier_rating: float
    initial_stock_target: int | None = None
    mth_expired: int | None = None

    @property
    def delivery(self):
        month, year = int(self.batch_no[:2]), 2000 + int(self.batch_no[2:])
        return date(year, month, calendar.monthrange(year, month)[1]) + timedelta(days=self.lead_time)
    @property
    def remaining(self):
        return self.shelf_life - (self.period - self.delivery).days


def load_csv(path, text=None):
    path = Path(path)
    match = re.fullmatch(r'(.+)_(\d{4})_(\d{2})', path.stem)
    if not match: raise ValueError('Filename must be Location_YYYY_MM.csv, e.g. Outlet_A_2026_06.csv')
    location, year, month = match.group(1), int(match.group(2)), int(match.group(3))
    if not 1 <= month <= 12 or year < 2000: raise ValueError('Invalid report year or month')
    period = date(year, month, calendar.monthrange(year, month)[1])
    rows=[]; seen=set(); purchases={}; losses={}
    with (path.open(encoding='utf-8-sig', newline='') if text is None else io.StringIO(text, newline='')) as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or any(f not in reader.fieldnames for f in REQUIRED_FIELDS):
            raise ValueError('Required CSV columns: '+', '.join(REQUIRED_FIELDS))
        for line, raw in enumerate(reader, 2):
            try:
                values={f:(raw.get(f) or '').strip() for f in FIELDS}
                for f in ('item_id','item_name','category'):
                    if not values[f]: raise ValueError(f'{f} is required')
                if not re.fullmatch(r'(0[1-9]|1[0-2])\d{2}',values['batch_no']): raise ValueError('batch_no must be MMYY')
                for f in ('current_total_stock','mth_purchase','lead_time','shelf_life'):
                    if not re.fullmatch(r'\d+', values[f]): raise ValueError(f'{f} must be a non-negative integer')
                cost, sell = Decimal(values['unit_cost']), Decimal(values['unit_sell'])
                if not cost.is_finite() or not sell.is_finite() or cost <= 0 or sell < 0: raise ValueError('unit_cost must be positive and unit_sell non-negative')
                if cost.as_tuple().exponent < -2 or sell.as_tuple().exponent < -2: raise ValueError('prices must have at most two decimal places')
                rating=float(values['supplier_rating'])
                if not math.isfinite(rating) or not 0 <= rating <= 5: raise ValueError('supplier_rating must be between 0 and 5')
                raw_target=values['initial_stock_target']
                if raw_target and not re.fullmatch(r'\d+',raw_target): raise ValueError('initial_stock_target must be blank or a non-negative integer')
                raw_expired=values['mth_expired']
                if raw_expired and not re.fullmatch(r'\d+',raw_expired): raise ValueError('mth_expired must be blank or a non-negative integer')
                row=Batch(location,period,values['item_id'],values['item_name'],values['category'],cost,sell,*(int(values[f]) for f in ('current_total_stock','mth_purchase','lead_time','shelf_life')),values['batch_no'],rating,int(raw_target) if raw_target else None,int(raw_expired) if raw_expired else None)
                if row.delivery > period: raise ValueError('assumed batch delivery is after report date')
                key=(row.item_id,row.batch_no)
                if key in seen: raise ValueError('duplicate product and batch')
                seen.add(key)
                if row.item_id in purchases and purchases[row.item_id] != row.mth_purchase: raise ValueError('mth_purchase differs across batches of the same product')
                purchases[row.item_id]=row.mth_purchase; rows.append(row)
                if row.item_id in losses and losses[row.item_id] != row.mth_expired: raise ValueError('mth_expired differs across batches of the same product')
                losses[row.item_id]=row.mth_expired
            except (ValueError, InvalidOperation, OverflowError) as exc: raise ValueError(f'Line {line}: {exc}') from exc
    if not rows: raise ValueError('CSV contains no product rows')
    return rows


def merge_sort(items, key):
    if len(items)<2: return list(items)
    mid=len(items)//2; a=merge_sort(items[:mid],key); b=merge_sort(items[mid:],key); out=[]; i=j=0
    while i<len(a) and j<len(b):
        if key(a[i]) <= key(b[j]): out.append(a[i]); i+=1
        else: out.append(b[j]); j+=1
    return out+a[i:]+b[j:]

class Tree:
    def __init__(self, pairs):
        pairs=sorted(pairs, key=lambda p:p[0]); self.root=self._build(pairs)
    def _build(self, pairs):
        if not pairs: return None
        m=len(pairs)//2
        return (pairs[m],self._build(pairs[:m]),self._build(pairs[m+1:]))
    def find(self,key):
        node=self.root
        while node:
            (k,value),left,right=node
            if key==k:return value
            node=left if key<k else right
        return None

def linear_search(rows, query):
    query=query.casefold()
    return [r for r in rows if query in r.item_id.casefold() or query in r.item_name.casefold()]

def forecast(observations):
    # Calendar month indices retain gaps, unlike treating missing months as adjacent.
    points=sorted(observations.items())
    if len(points)==1:return float(points[0][1])
    xs=[d.year*12+d.month for d,_ in points]; ys=[y for _,y in points]
    xmean=sum(xs)/len(xs); ymean=sum(ys)/len(ys)
    denom=sum((x-xmean)**2 for x in xs)
    slope=sum((x-xmean)*(y-ymean) for x,y in zip(xs,ys))/denom if denom else 0
    return max(0.0,ymean+slope*(xs[-1]+1-xmean))

EXPIRED_REPLACEMENT_PERCENT = 75
OBJECTIVES = ('Availability + margin', 'Popularity', 'Profit')
ALLOCATION_METHODS = ('Greedy', 'Knapsack', 'Balanced budget')


def monthly_expired_units(current):
    """Actual monthly losses when supplied; otherwise an estimate from dates.

    Retained expired stock from earlier months is not a new monthly loss.
    Explicit mth_expired counts once per product, never once per batch.
    """
    values = {r.mth_expired for r in current if r.mth_expired is not None}
    if len(values) > 1:
        raise ValueError('Conflicting mth_expired for the same product/month')
    if values:
        return next(iter(values)), 'Reported monthly losses'
    month_start = current[0].period.replace(day=1)
    units = sum(r.current_total_stock for r in current
                if month_start <= r.delivery + timedelta(days=r.shelf_life) <= r.period)
    return units, 'Estimated from current-month expiry dates'


def recommendations(records, objective=OBJECTIVES[0]):
    if objective not in OBJECTIVES:
        raise ValueError(f'Unknown restocking objective: {objective}')
    grouped = defaultdict(list)
    for row in records:
        grouped[(row.location, row.item_id)].append(row)
    result = []
    for (location,item_id), rows in grouped.items():
        latest = max(r.period for r in rows)
        current = [r for r in rows if r.period == latest]
        product = current[0]
        history = {r.period:r.mth_purchase for r in rows}
        predicted = forecast(history)
        stock = sum(r.current_total_stock for r in current)
        expired = sum(r.current_total_stock for r in current if r.remaining <= 0)
        usable = stock - expired
        near_expiry = sum(r.current_total_stock for r in current if 0 < r.remaining <= 14)
        expired_this_month, loss_source = monthly_expired_units(current)
        expired_replacement = expired_this_month * EXPIRED_REPLACEMENT_PERCENT // 100
        need = product.mth_purchase + expired_replacement
        target = usable + need
        margin = product.unit_sell-product.unit_cost
        # Same objective scores as main. Only the per-unit value changes;
        # quantity and allocation algorithms are shared across objectives.
        margin_points = max(0, int(margin * 100))
        if objective == 'Popularity':
            value = int((Decimal(str(predicted)) * 100).to_integral_value(rounding=ROUND_HALF_UP))
        elif objective == 'Profit':
            value = margin_points
        else:
            value = 100 + margin_points
        notes = []
        if near_expiry:
            notes.append(f'{near_expiry} near-expiry units remain available; review before buying')
        if loss_source.startswith('Estimated'):
            notes.append('Supply mth_expired to include losses already disposed of')
        if need and value <= 0:
            notes.append('Zero objective score: no budget allocated')
        result.append(dict(location=location,item_id=item_id,name=product.item_name,period=latest,
                           latest_sales=product.mth_purchase,forecast=predicted,
                           stock=stock,expired=expired,usable=usable,near_expiry=near_expiry,
                           expired_this_month=expired_this_month,expired_replacement=expired_replacement,
                           loss_source=loss_source,stock_target=target,need=need,
                           cost=product.unit_cost,margin=margin,objective=objective,value=value,qty=0,
                           review='; '.join(notes)))
    return merge_sort(result,lambda r:(-r['value']/int(r['cost']*100),r['location'],r['item_id']))


class AllocationCancelled(Exception):
    """A newer UI request has replaced this calculation."""


def allocate_balanced(items, cents, cancel=None):
    """Progressively fund the least-funded outlet/product first.

    Fairness is measured by money spent, not equal unit counts. Existing
    score/cost rank breaks ties. Whole-unit prices may overshoot a spending
    level, and unmet need receives leftover money when another item is full.
    """
    heap=[(0,index) for index,r in enumerate(items) if r['need']>0 and r['value']>0]
    heapq.heapify(heap)
    while heap and cents>0:
        if cancel and cancel(): raise AllocationCancelled()
        spent,index=heapq.heappop(heap)
        item=items[index]
        price=int(item['cost']*100)
        if price>cents:
            continue  # Remaining budget can only shrink; this item cannot fit.
        if heap:
            gap=max(0,heap[0][0]-spent)
            catch_up=max(1,(gap+price-1)//price)
        else:
            catch_up=cents//price
        count=min(item['need']-item['qty'],cents//price,catch_up)
        item['qty']+=count
        cents-=count*price
        spent+=count*price
        if item['qty']<item['need']:
            heapq.heappush(heap,(spent,index))
    return items


def allocate(items, budget, method, cancel=None, balance_percent=0):
    if method not in ALLOCATION_METHODS: raise ValueError(f'Unknown allocation method: {method}')
    if not isinstance(balance_percent,int) or not 0<=balance_percent<=100:
        raise ValueError('Balanced share must be a whole percentage from 0 to 100')
    if method=='Balanced budget' and balance_percent:
        raise ValueError('Balance first is used with Greedy or Knapsack; Balanced budget already balances the full budget')
    cents=int((Decimal(str(budget))*100).to_integral_value(rounding=ROUND_HALF_UP))
    if cents<0: raise ValueError('Budget must be non-negative')
    if method=='Knapsack' and cents>100000:
        raise ValueError('Knapsack is limited to a budget of 1,000.00 to keep the desktop application responsive. Use Greedy for larger budgets.')
    items=[dict(r,qty=0,allocation_method=method,balance_percent=0,balanced_units=0,priority_units=0) for r in items]
    if balance_percent:
        # Lock in a balanced base, then optimize only remaining need and money.
        # Unspent money from the first stage remains available in stage two.
        allocate_balanced(items,cents*balance_percent//100,cancel)
        remaining_cents=cents-sum(r['qty']*int(r['cost']*100) for r in items)
        remaining_items=[dict(r,need=r['need']-r['qty']) for r in items]
        extra=allocate(remaining_items,Decimal(remaining_cents)/100,method,cancel=cancel)
        for base,added in zip(items,extra):
            base['balanced_units']=base['qty']
            base['priority_units']=added['qty']
            base['qty']+=added['qty']
            base['balance_percent']=balance_percent
            base['allocation_method']=f'Balanced first + {method}'
        return items
    if method=='Balanced budget':
        allocate_balanced(items,cents,cancel)
        for r in items:
            r['balanced_units']=r['qty']
            r['balance_percent']=100
        return items
    if method=='Greedy':
        for r in items:
            if cancel and cancel(): raise AllocationCancelled()
            if r['value']<=0: continue
            price=int(r['cost']*100); r['qty']=min(r['need'],cents//price); cents-=r['qty']*price
            r['priority_units']=r['qty']
        return items
    # Bounded knapsack, binary-decomposed bundles; sparse Pareto frontier with immutable paths.
    states={0:(0,None)}
    for index,r in enumerate(items):
        if cancel and cancel(): raise AllocationCancelled()
        if r['value']<=0: continue
        price=int(r['cost']*100); remaining=min(r['need'],cents//price); chunk=1
        while remaining:
            count=min(chunk,remaining); remaining-=count; chunk*=2; weight=price*count; val=r['value']*count
            new=dict(states)
            for state_index,(cost,(score,path)) in enumerate(states.items()):
                if state_index % 2048 == 0 and cancel and cancel(): raise AllocationCancelled()
                nc=cost+weight
                if nc<=cents and (nc not in new or new[nc][0]<score+val): new[nc]=(score+val,(index,count,path))
            states={}; best=-1
            for cost in sorted(new):
                if new[cost][0]>best: states[cost]=new[cost]; best=new[cost][0]
    _,path=max(states.values(), key=lambda p:p[0])
    while path:
        index,count,path=path; items[index]['qty']+=count
    for r in items:r['priority_units']=r['qty']
    return items

def expiry_queue(rows):
    heap=[(r.remaining,r.location,r.item_id,r.batch_no,r) for r in rows]; heapq.heapify(heap)
    return [heapq.heappop(heap)[-1] for _ in range(len(heap))]
