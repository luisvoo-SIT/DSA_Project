#!/usr/bin/env python3
"""
Restock prioritisation & fund allocation for a multi-outlet provision shop.

Usage:
  python restock.py shop_inventory.csv --budget 800
  python restock.py bishan_2026-08.csv bishan_2026-09.csv tampines_2026-09.csv --budget 3000
  python restock.py data_dir/ --budget 3000 --search tuna

File naming: <shop>_<YYYY-MM>.csv. Several months of the same shop feed the
regression; the newest month is the current end-of-month snapshot. A file with
no date suffix is a single snapshot (regression falls back to a flat forecast).
"""
import argparse, csv, math, os, re
from collections import defaultdict
from dataclasses import dataclass

from algorithms import (HashTable, linear_search, merge_sort, forecast_next, simulate,
                        greedy_allocate, knapsack_allocate)


# ───────────────────────── Data model & loading ─────────────────────────
@dataclass
class Item:
    shop: str
    id: str
    name: str
    category: str
    cost: float
    price: float
    stock: int
    demand: float          # forecast units/day
    lead: int
    shelf: int
    rating: float
    trend_fitted: bool = False
    # Optional expiry columns (None when the CSV doesn't have them):
    #   days_to_expiry = days left on the OLDEST batch in stock (the one that expires first)
    #   expiring_qty   = how many units are in that oldest batch
    days_to_expiry: int = None
    expiring_qty: int = None

    def batches(self, stock_age):
        """
        Turn the CSV's expiry info into batches for the priority queue: [(days_left, qty), ...]

        With days_to_expiry / expiring_qty:
          batch 1 = the oldest batch: expiring_qty units that expire in days_to_expiry days.
          batch 2 = the rest of the stock (stock - expiring_qty). The CSV gives no date for it,
                    so we assume it is fresher: it gets the longer of days_to_expiry and the
                    stock_age estimate, capped at the full shelf life.
        Without them (old CSV format):
          one batch holding all stock, assumed to have used `stock_age` of its shelf life.
        """
        guess = max(1, int(self.shelf * (1 - stock_age)))
        if self.days_to_expiry is None or self.expiring_qty is None:
            return [(guess, self.stock)]
        oldest_qty = min(self.expiring_qty, self.stock)
        rest_life = min(self.shelf, max(self.days_to_expiry, guess))
        return [(self.days_to_expiry, oldest_qty), (rest_life, self.stock - oldest_qty)]

    @property
    def units_at_risk(self):
        """
        Units of the oldest batch that will NOT sell before they expire.
        The oldest batch sells first (FEFO), at `demand` units/day for `days_to_expiry` days.
        e.g. 30 units, 4 days left, 6.2/day -> sells ~24.8 -> ~5.2 units at risk.
        """
        if self.days_to_expiry is None or self.expiring_qty is None:
            return 0.0
        return max(0.0, min(self.expiring_qty, self.stock) - self.demand * self.days_to_expiry)

    @property
    def margin(self): return self.price - self.cost
    @property
    def cover_days(self): return self.stock / self.demand if self.demand else float("inf")


@dataclass
class Lot:
    item: Item
    qty: int
    cost: float
    value: float
    @property
    def density(self): return self.value / self.cost if self.cost else 0.0


def read_csv(path):
    table = HashTable()
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            r = {k.strip(): v.strip() for k, v in r.items()}
            table.put(r["item_id"], r)
    return table


def collect_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith(".csv")]
        else:
            files.append(p)
    return files


def load_shops(paths):
    """Group files by shop; return {shop: [Item,...]} using newest snapshot + regression."""
    groups = defaultdict(list)
    for path in collect_files(paths):
        stem = os.path.splitext(os.path.basename(path))[0]
        m = re.match(r"^(.*?)_(\d{4}-\d{2})$", stem)
        shop, month = (m.group(1), m.group(2)) if m else (stem, "")
        groups[shop].append((month, read_csv(path)))

    shops = {}
    for shop, snaps in groups.items():
        snaps.sort(key=lambda s: s[0])
        latest = snaps[-1][1]
        items = []
        for r in latest.values():
            hist = []
            for _, tbl in snaps:                       # hash lookup per month
                row = tbl.get(r["item_id"])
                if row:
                    hist.append(float(row["avg_daily_demand"]))
            demand, fitted = forecast_next(hist)
            d_exp = r.get("days_to_expiry", "")            # optional columns: blank/missing -> None
            q_exp = r.get("expiring_qty", "")
            items.append(Item(
                shop, r["item_id"], r["item_name"], r["category"],
                float(r["unit_cost"]), float(r["selling_price"]),
                int(float(r["current_stock"])), demand,
                int(float(r["supplier_lead_time_days"])), int(float(r["shelf_life_days"])),
                float(r["supplier_rating"]), fitted,
                int(float(d_exp)) if d_exp else None, int(float(q_exp)) if q_exp else None))
        shops[shop] = items
    return shops


# ───────────────────────── Lot generation ─────────────────────────
def build_lots(item, horizon, n_lots, stock_age):
    """
    Split the item's restock need into lots. Each lot's value is the *marginal*
    gross profit (from the FEFO simulation) of adding it, minus expiry waste,
    scaled by supplier rating. Values naturally diminish for later lots.
    """
    if item.lead >= horizon or item.demand <= 0:
        return []
    q_max = math.ceil(1.1 * item.demand * horizon) - item.stock   # horizon demand + 10% buffer
    if q_max <= 0:
        return []
    batches = item.batches(stock_age)

    def V(q):
        s, _, w = simulate(batches, item.demand, q, item.lead, item.shelf, horizon)
        return item.margin * s - item.cost * w

    base, extra = divmod(q_max, min(n_lots, q_max))
    sizes = [base + (1 if i < extra else 0) for i in range(min(n_lots, q_max))]
    lots, cum, prev = [], 0, V(0)
    for sz in sizes:
        cum += sz
        cur = V(cum)
        val = (cur - prev) * item.rating / 5.0
        prev = cur
        if val > 0:
            lots.append(Lot(item, sz, sz * item.cost, val))
    return lots


# ───────────────────────── Reporting ─────────────────────────
def summarise(chosen):
    plan = defaultdict(lambda: [0, 0.0, 0.0])         # (shop,item_id) -> qty, cost, value
    for l in chosen:
        p = plan[(l.item.shop, l.item.id)]
        p[0] += l.qty; p[1] += l.cost; p[2] += l.value
    return plan


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("paths", nargs="+", help="CSV file(s) or directory")
    ap.add_argument("--budget", type=float, help="total restock funds (default: 50%% of full request)")
    ap.add_argument("--horizon", type=int, default=30, help="planning days (default 30)")
    ap.add_argument("--lots", type=int, default=4, help="lots per item (default 4)")
    ap.add_argument("--unit", type=float, default=0.5, help="Knapsack fund granularity in $ (default 0.5)")
    ap.add_argument("--stock-age", type=float, default=0.5,
                    help="assumed fraction of shelf life already used by stock on hand (default 0.5)")
    ap.add_argument("--search", help="linear-search items by name/category and exit")
    ap.add_argument("--out", default="restock_plan.csv")
    a = ap.parse_args()

    shops = load_shops(a.paths)

    if a.search:
        for shop, items in shops.items():
            for it in linear_search(items, a.search):
                print(f"{shop:12} {it.id} {it.name:24} stock={it.stock:<4} cover={it.cover_days:5.1f}d "
                      f"lead={it.lead}d")
        return

    lots = [l for items in shops.values() for it in items
            for l in build_lots(it, a.horizon, a.lots, a.stock_age)]
    full_cost = sum(l.cost for l in lots)
    budget = a.budget if a.budget is not None else round(full_cost * 0.5, 2)

    g = greedy_allocate(lots, budget)
    d = knapsack_allocate(lots, budget, a.unit)

    print(f"Shops: {len(shops)} | items: {sum(len(v) for v in shops.values())} | horizon: {a.horizon}d")
    print(f"Full restock request: ${full_cost:,.2f} | budget: ${budget:,.2f} "
          f"({budget / full_cost:.0%} of request)\n" if full_cost else "Nothing to restock.\n")
    if not full_cost:
        return

    print(f"{'Method':<8}{'Spent':>10}{'Exp. profit':>13}{'Profit/$':>10}")
    for name, ch in (("Greedy", g), ("Knapsack", d)):
        sp, pf = sum(l.cost for l in ch), sum(l.value for l in ch)
        print(f"{name:<8}{sp:>10,.2f}{pf:>13,.2f}{pf / sp if sp else 0:>10.2f}")

    final = d                                          # Knapsack is the optimised plan
    plan = summarise(final)
    print("\nFund split per shop (Knapsack):")
    by_shop = defaultdict(float)
    for (shop, _), (_, cost, _) in plan.items():
        by_shop[shop] += cost
    for shop, amt in merge_sort(list(by_shop.items()), key=lambda kv: kv[1], reverse=True):
        print(f"  {shop:<16}${amt:>9,.2f}  ({amt / sum(by_shop.values()):.0%})")

    # Expiry risk: oldest batches that demand can't clear before they expire
    risky = [it for items in shops.values() for it in items if it.units_at_risk >= 1]
    if risky:
        print("\nExpiry risk (oldest batch won't fully sell in time):")
        print(f"  {'shop':<10}{'item':<24}{'expiring':>9}{'days':>6}{'at risk':>9}{'$ lost':>9}")
        for it in merge_sort(risky, key=lambda i: i.units_at_risk * i.cost, reverse=True):
            print(f"  {it.shop[:9]:<10}{it.name:<24}{it.expiring_qty:>9}{it.days_to_expiry:>6}"
                  f"{it.units_at_risk:>9.1f}{it.units_at_risk * it.cost:>9.2f}")

    # Items funded in full vs partially vs not at all, ranked by priority
    print("\nTop restock priorities (Knapsack):")
    print(f"  {'shop':<10}{'item':<24}{'stock':>6}{'cover':>7}{'order':>7}{'cost':>9}{'profit':>9}")
    rows = []
    for shops_items in shops.values():
        for it in shops_items:
            q, c, v = plan.get((it.shop, it.id), (0, 0.0, 0.0))
            if q:
                rows.append((it, q, c, v))
    for it, q, c, v in merge_sort(rows, key=lambda r: r[3] / r[2], reverse=True)[:15]:
        print(f"  {it.shop[:9]:<10}{it.name:<24}{it.stock:>6}{it.cover_days:>6.1f}d{q:>7}{c:>9.2f}{v:>9.2f}")

    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shop", "item_id", "item_name", "current_stock", "forecast_daily_demand",
                    "cover_days", "days_to_expiry", "expiring_qty", "units_at_risk", "order_qty", "order_cost", "expected_profit", "regression_used"])
        for shops_items in shops.values():
            for it in shops_items:
                q, c, v = plan.get((it.shop, it.id), (0, 0.0, 0.0))
                w.writerow([it.shop, it.id, it.name, it.stock, round(it.demand, 2),
                            round(it.cover_days, 1), it.days_to_expiry, it.expiring_qty,
                            round(it.units_at_risk, 1), q, round(c, 2), round(v, 2), it.trend_fitted])
    print(f"\nFull plan written to {a.out}")


if __name__ == "__main__":
    main()
