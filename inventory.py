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

FIELDS = ('item_id','item_name','category','unit_cost','unit_sell','current_total_stock','mth_purchase','lead_time','shelf_life','batch_no','supplier_rating')

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
    rows=[]; seen=set(); purchases={}
    with (path.open(encoding='utf-8-sig', newline='') if text is None else io.StringIO(text, newline='')) as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or any(f not in reader.fieldnames for f in FIELDS):
            raise ValueError('Required CSV columns: '+', '.join(FIELDS))
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
                row=Batch(location,period,values['item_id'],values['item_name'],values['category'],cost,sell,*(int(values[f]) for f in ('current_total_stock','mth_purchase','lead_time','shelf_life')),values['batch_no'],rating)
                if row.delivery > period: raise ValueError('assumed batch delivery is after report date')
                key=(row.item_id,row.batch_no)
                if key in seen: raise ValueError('duplicate product and batch')
                seen.add(key)
                if row.item_id in purchases and purchases[row.item_id] != row.mth_purchase: raise ValueError('mth_purchase differs across batches of the same product')
                purchases[row.item_id]=row.mth_purchase; rows.append(row)
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

def recommendations(records):
    by=defaultdict(list)
    for r in records: by[(r.location,r.item_id)].append(r)
    result=[]
    for (location,item), rows in by.items():
        latest=max(r.period for r in rows); current=[r for r in rows if r.period==latest]
        history={r.period:r.mth_purchase for r in rows}
        predicted=forecast(history); representative=current[0]
        stock=sum(r.current_total_stock for r in current)
        expiring=sum(r.current_total_stock for r in current if r.remaining<=14)
        usable=stock-expiring
        days=calendar.monthrange(latest.year,latest.month)[1]
        target=math.ceil(predicted/days*(representative.lead_time+30))
        # Limit the proposed order to expected sales during its shelf life.
        shelf_cap=math.ceil(predicted/days*representative.shelf_life)
        need=max(0,min(target-usable,shelf_cap))
        margin=representative.unit_sell-representative.unit_cost
        # One point for stock availability plus nonnegative gross margin, per unit.
        value=100+max(0,int((margin*100).to_integral_value(rounding=ROUND_HALF_UP)))
        result.append(dict(location=location,item_id=item,name=representative.item_name,period=latest,forecast=predicted,stock=stock,expiring=expiring,need=need,cost=representative.unit_cost,margin=margin,value=value,qty=0))
    return merge_sort(result,lambda r:(-r['value']/int(r['cost']*100),r['location'],r['item_id']))

def allocate(items, budget, method):
    cents=int((Decimal(str(budget))*100).to_integral_value(rounding=ROUND_HALF_UP))
    if cents<0: raise ValueError('Budget must be non-negative')
    items=[dict(r,qty=0) for r in items]
    if method=='Greedy':
        for r in items:
            price=int(r['cost']*100); r['qty']=min(r['need'],cents//price); cents-=r['qty']*price
        return items
    if cents>100000: raise ValueError('Knapsack is limited to a budget of 1,000.00 to keep the desktop application responsive. Use Greedy for larger budgets.')
    # Bounded knapsack, binary-decomposed bundles; sparse Pareto frontier with immutable paths.
    states={0:(0,None)}
    for index,r in enumerate(items):
        price=int(r['cost']*100); remaining=min(r['need'],cents//price); chunk=1
        while remaining:
            count=min(chunk,remaining); remaining-=count; chunk*=2; weight=price*count; val=r['value']*count
            new=dict(states)
            for cost,(score,path) in states.items():
                nc=cost+weight
                if nc<=cents and (nc not in new or new[nc][0]<score+val): new[nc]=(score+val,(index,count,path))
            states={}; best=-1
            for cost in sorted(new):
                if new[cost][0]>best: states[cost]=new[cost]; best=new[cost][0]
    _,path=max(states.values(), key=lambda p:p[0])
    while path:
        index,count,path=path; items[index]['qty']+=count
    return items

def expiry_queue(rows):
    heap=[(r.remaining,r.location,r.item_id,r.batch_no,r) for r in rows]; heapq.heapify(heap)
    return [heapq.heappop(heap)[-1] for _ in range(len(heap))]
