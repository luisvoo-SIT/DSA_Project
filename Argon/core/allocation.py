"""
Restocking budget allocation algorithms:
- Balanced Budget / Even Distribution (allocate_even)
- Greedy with integrated Balanced Base (allocate_greedy)
- Bounded Knapsack DP with integrated Balanced Base (allocate_knapsack)
"""
import math
from typing import Callable, List, Optional, Tuple
import numpy as np
from core.models import ProductRecommendation


class AllocationCancelled(Exception):
    """Raised when an in-progress allocation is superseded by a newer request."""


def _normalize_share(balanced_share: float) -> float:
    return max(0.0, min(100.0, float(balanced_share)))


def allocate_even(
    recommendations: List[ProductRecommendation],
    budget: float,
    cancel: Optional[Callable[[], bool]] = None,
    reset: bool = True,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Balanced Budget / Even Distribution (Variety) allocation:
    Distributes the budget evenly across eligible products to restock a wide
    variety of items rather than concentrating spend on a few top items.

    When reset=True, initializes allocated_units=0 before allocating.
    When reset=False, adds onto any existing allocated_units up to each product's need.
    """
    if budget < 0:
        budget = 0.0

    rem_cents = int(round(budget * 100))

    if reset:
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

        if prod.allocated_units < prod.need:
            active_indices.append(idx)

    # Phase 1: Equal-dollar water-filling across active products
    while active_indices and rem_cents > 0:
        if cancel is not None and cancel():
            raise AllocationCancelled()

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

    for prod in recommendations:
        prod.projected_stock = int(round(prod.usable_stock)) + prod.allocated_units
        prod.allocated_cost = round(prod.allocated_units * prod.unit_cost, 2)

    remaining_budget = round(max(0.0, rem_cents / 100.0), 2)
    return recommendations, remaining_budget


def allocate_greedy(
    recommendations: List[ProductRecommendation],
    budget: float,
    cancel: Optional[Callable[[], bool]] = None,
    balanced_share: float = 0.0,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Greedy allocation with optional integrated Balanced Base share (0-100%):
    1. If balanced_share > 0, first distributes budget * (balanced_share / 100)
       evenly across eligible products using allocate_even().
    2. Then allocates the remaining budget in rank order (highest value-per-cost first)
       across each product's remaining unfulfilled need.
    """
    total_budget = max(0.0, float(budget))
    share_pct = _normalize_share(balanced_share)

    if share_pct >= 100.0:
        return allocate_even(recommendations, total_budget, cancel=cancel, reset=True)

    if share_pct > 0.0:
        base_budget = round(total_budget * (share_pct / 100.0), 2)
        allocate_even(recommendations, base_budget, cancel=cancel, reset=True)
        base_spent = round(sum(p.allocated_cost for p in recommendations), 2)
        remaining_budget = round(max(0.0, total_budget - base_spent), 2)
    else:
        for prod in recommendations:
            prod.allocated_units = 0
            prod.projected_stock = int(round(prod.usable_stock))
            prod.allocated_cost = 0.0
        remaining_budget = total_budget

    # Stage 2: Greedy pass over remaining unfulfilled need
    for prod in recommendations:
        if cancel is not None and cancel():
            raise AllocationCancelled()

        if prod.need <= 0 or prod.priority_value <= 0:
            continue

        rem_need = prod.need - prod.allocated_units
        if rem_need <= 0:
            continue

        if prod.unit_cost <= 0.0:
            prod.allocated_units = prod.need
            prod.projected_stock = int(round(prod.usable_stock)) + prod.need
            prod.allocated_cost = 0.0
            continue

        max_affordable = int(math.floor(remaining_budget / prod.unit_cost))
        add_units = min(rem_need, max_affordable)
        add_cost = round(add_units * prod.unit_cost, 2)

        if add_cost > remaining_budget:
            add_units = max(0, int(math.floor(remaining_budget / prod.unit_cost)))
            add_cost = round(add_units * prod.unit_cost, 2)

        prod.allocated_units += add_units
        prod.projected_stock = int(round(prod.usable_stock)) + prod.allocated_units
        prod.allocated_cost = round(prod.allocated_units * prod.unit_cost, 2)
        remaining_budget = round(max(0.0, remaining_budget - add_cost), 2)

    total_spent = round(sum(p.allocated_cost for p in recommendations), 2)
    remaining_budget = round(max(0.0, total_budget - total_spent), 2)
    return recommendations, remaining_budget


def allocate_knapsack(
    recommendations: List[ProductRecommendation],
    budget: float,
    cancel: Optional[Callable[[], bool]] = None,
    balanced_share: float = 0.0,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Bounded knapsack allocation with optional integrated Balanced Base share (0-100%):
    1. If balanced_share > 0, first distributes budget * (balanced_share / 100)
       evenly across eligible products using allocate_even().
    2. Then solves Bounded Knapsack DP in integer cents over the remaining budget
       and each product's remaining unfulfilled need.

    Limited to budgets up to 1,000.00 for responsiveness.
    """
    if budget < 0:
        budget = 0.0

    if budget > 1000.00:
        raise ValueError(
            f"Budget (${budget:,.2f}) exceeds $1,000.00 limit for Bounded Knapsack. "
            "Please use Greedy or Balanced Budget for larger budgets."
        )

    total_budget = float(budget)
    share_pct = _normalize_share(balanced_share)

    if share_pct >= 100.0:
        return allocate_even(recommendations, total_budget, cancel=cancel, reset=True)

    if share_pct > 0.0:
        base_budget = round(total_budget * (share_pct / 100.0), 2)
        allocate_even(recommendations, base_budget, cancel=cancel, reset=True)
        base_spent_cents = sum(int(round(p.allocated_units * round(p.unit_cost * 100))) for p in recommendations)
    else:
        for prod in recommendations:
            prod.allocated_units = 0
            prod.projected_stock = int(round(prod.usable_stock))
            prod.allocated_cost = 0.0
        base_spent_cents = 0

    total_W = int(round(total_budget * 100))
    W = max(0, total_W - base_spent_cents)

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

        rem_need = max(0, prod.need - prod.allocated_units)
        remaining_qty = min(rem_need, W // unit_cents)
        power = 1
        while remaining_qty > 0:
            piece = min(power, remaining_qty)
            weight = piece * unit_cents
            val = piece * prod.priority_value
            paid_items.append((weight, val, piece, idx))
            remaining_qty -= piece
            power *= 2

    if paid_items and W > 0:
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

    remaining_budget = round(max(0.0, total_budget - total_spent), 2)
    return recommendations, remaining_budget


def allocate_budget(
    recommendations: List[ProductRecommendation],
    budget: float,
    method: str = "Greedy",
    cancel: Optional[Callable[[], bool]] = None,
    balanced_share: float = 0.0,
) -> Tuple[List[ProductRecommendation], float]:
    """
    Allocates budget using:
    - 'Greedy' (with optional balanced_share % allocated via Balanced Base first)
    - 'Bounded Knapsack' (with optional balanced_share % allocated via Balanced Base first)
    - 'Balanced Budget' / 'Even Distribution' (100% balanced budget distribution)
    """
    m_lower = method.lower()
    if m_lower in ("bounded knapsack", "knapsack"):
        return allocate_knapsack(recommendations, budget, cancel=cancel, balanced_share=balanced_share)
    elif m_lower in ("even", "even distribution", "even distribution (variety)", "variety", "balanced", "balanced budget"):
        return allocate_even(recommendations, budget, cancel=cancel, reset=True)
    else:
        return allocate_greedy(recommendations, budget, cancel=cancel, balanced_share=balanced_share)
