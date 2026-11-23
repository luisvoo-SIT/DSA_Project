"""
Restocking budget allocation algorithms: Greedy and Bounded Knapsack.
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

    # Recommendations are expected to be ordered by rank (value-per-cost descending)
    for prod in recommendations:
        if cancel is not None and cancel():
            raise AllocationCancelled()

        if prod.need <= 0 or prod.priority_value <= 0:
            prod.allocated_units = 0
            prod.allocated_cost = 0.0
            continue

        if prod.unit_cost <= 0.0:
            # Free items with positive score: allocate full need
            prod.allocated_units = prod.need
            prod.allocated_cost = 0.0
            continue

        max_affordable = int(math.floor(remaining_budget / prod.unit_cost))
        allocated = min(prod.need, max_affordable)
        cost = round(allocated * prod.unit_cost, 2)

        # Double check remaining budget doesn't go below zero due to floating point
        if cost > remaining_budget:
            allocated = max(0, int(math.floor(remaining_budget / prod.unit_cost)))
            cost = round(allocated * prod.unit_cost, 2)

        prod.allocated_units = allocated
        prod.allocated_cost = cost
        remaining_budget = round(max(0.0, remaining_budget - cost), 2)

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
            "Please use Greedy allocation for larger budgets."
        )

    # Budget in integer cents
    W = int(round(budget * 100))

    # Reset allocations
    for prod in recommendations:
        prod.allocated_units = 0
        prod.allocated_cost = 0.0

    # Separate free items vs paid items
    paid_items: List[Tuple[int, int, int, int]] = []  # (weight_cents, value, piece_size, prod_idx)

    for idx, prod in enumerate(recommendations):
        if cancel is not None and cancel():
            raise AllocationCancelled()

        if prod.need <= 0 or prod.priority_value <= 0:
            continue
        if prod.unit_cost <= 0.0:
            prod.allocated_units = prod.need
            prod.allocated_cost = 0.0
            continue

        unit_cents = int(round(prod.unit_cost * 100))
        if unit_cents <= 0:
            prod.allocated_units = prod.need
            prod.allocated_cost = 0.0
            continue

        # Binary splitting of affordable need into powers of 2
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

    # Traceback to reconstruct allocated items
    curr = best_c
    for i in range(num_items - 1, -1, -1):
        if took[i, curr]:
            weight, _, piece, prod_idx = paid_items[i]
            recommendations[prod_idx].allocated_units += piece
            curr -= weight

    total_spent = 0.0
    for prod in recommendations:
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
    Allocates budget using either 'Greedy' or 'Bounded Knapsack'.
    """
    if method.lower() in ("bounded knapsack", "knapsack"):
        return allocate_knapsack(recommendations, budget, cancel=cancel)
    else:
        return allocate_greedy(recommendations, budget, cancel=cancel)
