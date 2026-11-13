"""
Demand forecasting module using linear regression over calendar month indices.
"""
from typing import Dict, List, Tuple


def month_to_calendar_index(year: int, month: int) -> int:
    """Computes calendar month index (year * 12 + month)."""
    return year * 12 + month


def predict_demand(history: List[Tuple[int, int, float]]) -> float:
    """
    Given history as a list of (year, month, purchase_val), predicts demand
    for the month following the latest recorded month.
    
    Rules:
    - If >= 2 months: linear regression on calendar month indices.
    - If 1 month: uses that month's purchase value.
    - Missing months are NOT treated as zero.
    - Prediction is clamped at zero.
    """
    if not history:
        return 0.0

    # Sort history chronologically by (year, month)
    sorted_history = sorted(history, key=lambda item: (item[0], item[1]))

    # Deduplicate by (year, month) keeping the last occurrence if any
    unique_points: Dict[Tuple[int, int], float] = {}
    for y, m, val in sorted_history:
        unique_points[(y, m)] = float(val)

    points = sorted(unique_points.items(), key=lambda item: (item[0][0], item[0][1]))

    if len(points) == 1:
        return max(0.0, points[0][1])

    # Convert to x (calendar month index) and y (purchase count)
    xs = [month_to_calendar_index(y, m) for (y, m), _ in points]
    ys = [val for _, val in points]
    n = len(xs)

    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))

    if ss_xx == 0:
        # All x identical (degenerate case)
        slope = 0.0
        intercept = y_mean
    else:
        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean

    # Target month is the month immediately following the latest month
    latest_x = xs[-1]
    target_x = latest_x + 1

    predicted = slope * target_x + intercept
    return max(0.0, predicted)
