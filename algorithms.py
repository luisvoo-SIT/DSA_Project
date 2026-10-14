"""
algorithms.py — reusable data structures & algorithms for the restock planner.

Contents:
  HashTable                      O(1) average key lookup
  linear_search(items, term)     scan-based search over object fields
  merge_sort(arr, key, reverse)  stable O(n log n) sort
  ols / forecast_next            linear-regression demand forecast
  simulate(...)                  priority-queue (heap) first-expiry-first-out batch simulation
  greedy_allocate / knapsack_allocate   fund allocation over lots (.cost, .value)

No dependency on the CSV format or the Item/Lot classes, so it can be imported anywhere:
    from algorithms import HashTable, merge_sort, knapsack_allocate
"""
import heapq, math


# ───────────────────────── Hash table (chaining) ─────────────────────────
class HashTable:
    """Separate-chaining hash table: O(1) average put/get by key."""
    def __init__(self, size=31):
        self.buckets = [[] for _ in range(size)]
        self.count = 0

    def _idx(self, key):
        h = 5381
        for ch in str(key):
            h = (h * 33 + ord(ch)) & 0xFFFFFFFF   # djb2
        return h % len(self.buckets)

    def put(self, key, value):
        b = self.buckets[self._idx(key)]
        for i, (k, _) in enumerate(b):
            if k == key:
                b[i] = (key, value)
                return
        b.append((key, value))
        self.count += 1
        if self.count > 2 * len(self.buckets):
            self._grow()

    def get(self, key, default=None):
        for k, v in self.buckets[self._idx(key)]:
            if k == key:
                return v
        return default

    def _grow(self):
        old = [kv for b in self.buckets for kv in b]
        self.buckets = [[] for _ in range(len(self.buckets) * 2)]
        self.count = 0
        for k, v in old:
            self.put(k, v)

    def values(self):
        return [v for b in self.buckets for _, v in b]


# ───────────────────────── Linear search ─────────────────────────
def linear_search(items, term, fields=("name", "category")):
    """Scan every item; match `term` in any of `fields` (case-insensitive)."""
    t = term.lower()
    return [it for it in items if any(t in str(getattr(it, f)).lower() for f in fields)]


# ───────────────────────── Merge sort ─────────────────────────
def merge_sort(arr, key, reverse=False):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    L, R = merge_sort(arr[:mid], key, reverse), merge_sort(arr[mid:], key, reverse)
    out, i, j = [], 0, 0
    while i < len(L) and j < len(R):
        take_left = key(L[i]) >= key(R[j]) if reverse else key(L[i]) <= key(R[j])
        if take_left:
            out.append(L[i]); i += 1
        else:
            out.append(R[j]); j += 1
    return out + L[i:] + R[j:]


# ───────────────────────── Linear regression ─────────────────────────
def ols(ys):
    """Least-squares line through (0,y0),(1,y1)... ; returns (slope, intercept)."""
    n = len(ys)
    xs = range(n)
    mx, my = (n - 1) / 2, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return slope, my - slope * mx


def forecast_next(history):
    """Predict next month's avg daily demand. Flat if <2 months of history."""
    if len(history) < 2:
        return history[-1], False
    slope, icpt = ols(history)
    pred = icpt + slope * len(history)
    return max(0.0, min(pred, 2 * history[-1])), True   # clamp wild extrapolation


# ───────────────────────── Priority queue: FEFO batch simulation ─────────────────────────
def simulate(stock, rem_life, demand, order_q, lead, shelf, horizon):
    """
    Day-by-day simulation. Batches sit in a min-heap keyed by expiry day, so the
    soonest-expiring batch is sold first (FEFO) and expired batches pop off as waste.
    Returns (units_sold, units_lost, units_wasted).
    """
    heap = [(rem_life, float(stock))] if stock > 0 else []
    heapq.heapify(heap)
    sold = lost = waste = 0.0
    for d in range(horizon):
        if order_q > 0 and d == lead:
            heapq.heappush(heap, (d + shelf, float(order_q)))
        while heap and heap[0][0] <= d:
            waste += heapq.heappop(heap)[1]
        need = demand
        while need > 1e-9 and heap:
            exp, q = heapq.heappop(heap)
            take = min(q, need)
            sold += take; need -= take; q -= take
            if q > 1e-9:
                heapq.heappush(heap, (exp, q))
        lost += need
    return sold, lost, waste


# ───────────────────────── Allocation: greedy & DP knapsack ─────────────────────────
def greedy_allocate(lots, budget):
    """Take lots (anything with .cost and .value) in value-per-dollar order while funds last."""
    ranked = merge_sort(lots, key=lambda l: l.value / l.cost if l.cost else 0.0, reverse=True)
    chosen, spent = [], 0.0
    for l in ranked:
        if spent + l.cost <= budget + 1e-9:
            chosen.append(l); spent += l.cost
    return chosen


def knapsack_allocate(lots, budget, unit):
    """0/1 knapsack over funds in `unit`-dollar steps (lot costs rounded UP, so never overspends)."""
    cap = int(budget / unit)
    w = [max(1, math.ceil(l.cost / unit - 1e-9)) for l in lots]
    n = len(lots)
    dp = [0.0] * (cap + 1)
    keep = [bytearray(cap + 1) for _ in range(n)]
    for i, l in enumerate(lots):
        wi, vi, ki = w[i], l.value, keep[i]
        for c in range(cap, wi - 1, -1):
            cand = dp[c - wi] + vi
            if cand > dp[c]:
                dp[c] = cand; ki[c] = 1
    chosen, c = [], cap
    for i in range(n - 1, -1, -1):
        if keep[i][c]:
            chosen.append(lots[i]); c -= w[i]
    return chosen
