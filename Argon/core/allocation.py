"""
Restocking budget allocation algorithms: Greedy, Bounded Knapsack, and Even Distribution (Variety).
"""
import math
from typing import Callable, List, Optional, Tuple
import numpy as np
from core.models import ProductRecommendation


class AllocationCancelled(Exception):
    """Raised when an in-progress allocation is superseded by a newer request."""


def allocate_greedy(
    recommendations: List[ProductRecommendation],
    budget: float,
    cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Greedy allocation: buys in rank order (highest value-per-cost first).
    Returns (updated_recommendations, remaining_budget).
    """
    remaining_budget = max(0.0, float(budget))

    for prod in recommendations:
        if cancel is not None and cancel():
            raise AllocationCancelled()

        if prod.need <= 0 or prod.priority_value <= 0:
            prod.allocated_units = 0
            prod.projected_stock = int(round(prod.usable_stock))
            prod.allocated_cost = 0.0
            continue

        if prod.unit_cost <= 0.0:
            prod.allocated_units = prod.need
            prod.projected_stock = int(round(prod.usable_stock)) + prod.need
            prod.allocated_cost = 0.0
            continue

        max_affordable = int(math.floor(remaining_budget / prod.unit_cost))
        allocated = min(prod.need, max_affordable)
        cost = round(allocated * prod.unit_cost, 2)

        if cost > remaining_budget:
            allocated = max(0, int(math.floor(remaining_budget / prod.unit_cost)))
            cost = round(allocated * prod.unit_cost, 2)

        prod.allocated_units = allocated
        prod.projected_stock = int(round(prod.usable_stock)) + allocated
        prod.allocated_cost = cost
        remaining_budget = round(max(0.0, remaining_budget - cost), 2)

    return recommendations, remaining_budget


def allocate_even(
    recommendations: List[ProductRecommendation],
    budget: float,
    cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Even Distribution (Variety) allocation:
    Distributes the shared budget evenly across eligible products to restock
    a wide variety of items rather than concentrating spend on a few top items.

    Algorithm:
    1. Reset allocations; free items with positive score receive full need.
    2. Equal-Share Water-Filling Pass: while the equal dollar share across
       active products (rem_budget // num_active) can buy at least 1 unit
       of some active product, allocate up to floor(equal_share / unit_cost)
       units per product (capped at each product's remaining need).
    3. Round-Robin Remainder Pass: distribute any remaining budget 1 unit at
       a time in rank order across active products that still have unmet need
       and unit_cost <= remaining_budget.
    """
    if budget < 0:
        budget = 0.0

    rem_cents = int(round(budget * 100))

    for prod in recommendations:
        prod.allocated_units = 0
        prod.projected_stock = int(round(prod.usable_stock))
        prod.allocated_cost = 0.0

    active_indices: List[int] = []
    unit_costs_cents: List[int] = [0] * len(recommendations)

    for idx, prod in enumerate(recommendations):
        if cancel is not None and cancel():
            raise AllocationCancelled()

        if prod.need <= 0 or prod.priority_value <= 0:
            continue

        cost_cents = int(round(prod.unit_cost * 100))
        unit_costs_cents[idx] = cost_cents
        if cost_cents <= 0:
            prod.allocated_units = prod.need
            prod.projected_stock = int(round(prod.usable_stock)) + prod.need
            prod.allocated_cost = 0.0
            continue

        active_indices.append(idx)

    # Phase 1: Equal-dollar water-filling across active products
    while active_indices and rem_cents > 0:
        if cancel is not None and cancel():
            raise AllocationCancelled()

        # Keep only products that still need units and can afford at least 1 unit
        active_indices = [
            idx for idx in active_indices
            if recommendations[idx].allocated_units < recommendations[idx].need
            and unit_costs_cents[idx] <= rem_cents
        ]
        if not active_indices:
            break

        equal_share_cents = rem_cents // len(active_indices)
        if equal_share_cents < max(unit_costs_cents[idx] for idx in active_indices):
            break
        bought_in_pass = 0

        for idx in active_indices:
            prod = recommendations[idx]
            c_cents = unit_costs_cents[idx]
            rem_need = prod.need - prod.allocated_units
            if rem_need <= 0 or c_cents > rem_cents:
                continue

            share_for_item = min(equal_share_cents, rem_cents)
            qty = min(rem_need, share_for_item // c_cents)
            if qty > 0:
                prod.allocated_units += qty
                rem_cents -= qty * c_cents
                bought_in_pass += qty

        # If equal_share_cents is smaller than every active product's unit cost,
        # exit Phase 1 and switch to Phase 2 (Round-Robin 1 unit at a time).
        if bought_in_pass == 0:
            break

    # Phase 2: Round-Robin 1 unit at a time in rank order for remaining budget
    while active_indices and rem_cents > 0:
        if cancel is not None and cancel():
            raise AllocationCancelled()

        bought_in_round = 0
        next_active: List[int] = []

        for idx in active_indices:
            prod = recommendations[idx]
            c_cents = unit_costs_cents[idx]
            if prod.allocated_units < prod.need and c_cents <= rem_cents:
                prod.allocated_units += 1
                rem_cents -= c_cents
                bought_in_round += 1
                if prod.allocated_units < prod.need and c_cents <= rem_cents:
                    next_active.append(idx)

        if bought_in_round == 0:
            break
        active_indices = next_active

    total_spent = 0.0
    for prod in recommendations:
        prod.projected_stock = int(round(prod.usable_stock)) + prod.allocated_units
        prod.allocated_cost = round(prod.allocated_units * prod.unit_cost, 2)
        total_spent += prod.allocated_cost

    remaining_budget = round(max(0.0, budget - total_spent), 2)
    return recommendations, remaining_budget


def allocate_knapsack(
    recommendations: List[ProductRecommendation],
    budget: float,
    cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Bounded knapsack allocation:
    Maximizes additive priority score using integer cents and unit quantities,
    subject to each product's need and the budget.

    Limited to budgets up to 1,000.00 for responsiveness.
    Returns (updated_recommendations, remaining_budget).
    """
    if budget < 0:
        budget = 0.0

    if budget > 1000.00:
        raise ValueError(
            f"Budget (${budget:,.2f}) exceeds $1,000.00 limit for Bounded Knapsack. "
            "Please use Greedy or Even Distribution for larger budgets."
        )

    W = int(round(budget * 100))

    for prod in recommendations:
        prod.allocated_units = 0
        prod.projected_stock = int(round(prod.usable_stock))
        prod.allocated_cost = 0.0

    paid_items: List[Tuple[int, int, int, int]] = []

    for idx, prod in enumerate(recommendations):
        if cancel is not None and cancel():
            raise AllocationCancelled()

        if prod.need <= 0 or prod.priority_value <= 0:
            continue
        if prod.unit_cost <= 0.0:
            prod.allocated_units = prod.need
            prod.projected_stock = int(round(prod.usable_stock)) + prod.need
            prod.allocated_cost = 0.0
            continue

        unit_cents = int(round(prod.unit_cost * 100))
        if unit_cents <= 0:
            prod.allocated_units = prod.need
            prod.projected_stock = int(round(prod.usable_stock)) + prod.need
            prod.allocated_cost = 0.0
            continue

        remaining_qty = min(prod.need, W // unit_cents)
        power = 1
        while remaining_qty > 0:
            piece = min(power, remaining_qty)
            weight = piece * unit_cents
            val = piece * prod.priority_value
            paid_items.append((weight, val, piece, idx))
            remaining_qty -= piece
            power *= 2

    if not paid_items or W <= 0:
        return recommendations, round(budget, 2)

    num_items = len(paid_items)
    dp = np.zeros(W + 1, dtype=np.int64)
    took = np.zeros((num_items, W + 1), dtype=np.uint8)

    for i, (weight, val, _, _) in enumerate(paid_items):
        if cancel is not None and cancel():
            raise AllocationCancelled()
        if weight > W:
            continue
        cand = dp[: W + 1 - weight] + val
        target = dp[weight:]
        mask = cand > target
        target[mask] = cand[mask]
        took[i, weight:][mask] = 1

    best_c = int(np.argmax(dp))

    curr = best_c
    for i in range(num_items - 1, -1, -1):
        if took[i, curr]:
            weight, _, piece, prod_idx = paid_items[i]
            recommendations[prod_idx].allocated_units += piece
            curr -= weight

    total_spent = 0.0
    for prod in recommendations:
        prod.projected_stock = int(round(prod.usable_stock)) + prod.allocated_units
        prod.allocated_cost = round(prod.allocated_units * prod.unit_cost, 2)
        total_spent += prod.allocated_cost

    remaining_budget = round(max(0.0, budget - total_spent), 2)
    return recommendations, remaining_budget


def allocate_budget(
    recommendations: List[ProductRecommendation],
    budget: float,
    method: str = "Greedy",
    cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Allocates budget using 'Greedy', 'Bounded Knapsack', or 'Even Distribution'.
    """
    m_lower = method.lower()
    if m_lower in ("bounded knapsack", "knapsack"):
        return allocate_knapsack(recommendations, budget, cancel=cancel)
    elif m_lower in ("even", "even distribution", "even distribution (variety)", "variety"):
        return allocate_even(recommendations, budget, cancel=cancel)
    else:
        return allocate_greedy(recommendations, budget, cancel=cancel)
