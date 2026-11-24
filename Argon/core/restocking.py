"""
Restocking calculation and evaluation logic with partial expiry replacement.
"""
import calendar
import datetime
from typing import Dict, List, Optional, Tuple
from core.models import BatchRecord, ProductRecommendation
from core.forecasting import predict_demand
from core.sorting import merge_sort

EXPIRED_REPLACEMENT_PERCENT = 75
OBJECTIVES = ("Availability + margin", "Popularity", "Profit")


def calculate_monthly_expired_units(current_batches: List[BatchRecord]) -> Tuple[int, str]:
    """
    Returns (expired_units_this_month, loss_source) for a product's latest snapshot.

    Uses explicit mth_expired when provided (counted once per product/month);
    otherwise estimates from batches in the latest snapshot whose expiry date
    falls within that reporting month so older retained expired stock is not
    counted again.
    """
    explicit_vals = {b.mth_expired for b in current_batches if b.mth_expired is not None}
    if len(explicit_vals) > 1:
        raise ValueError("Conflicting mth_expired for the same product/month")
    if explicit_vals:
        return int(next(iter(explicit_vals))), "Reported monthly losses"

    report_date = current_batches[0].report_date
    if report_date is None:
        report_last_day = calendar.monthrange(current_batches[0].report_year, current_batches[0].report_month)[1]
        report_date = datetime.date(current_batches[0].report_year, current_batches[0].report_month, report_last_day)

    month_start = report_date.replace(day=1)
    units = sum(
        b.current_total_stock
        for b in current_batches
        if b.expiry_date is not None and month_start <= b.expiry_date <= report_date
    )
    return int(round(units)), "Estimated from current-month expiry dates"


def calculate_restocking_recommendations(
    all_batches: List[BatchRecord],
    selected_outlets: Optional[List[str]] = None,
    objective: str = OBJECTIVES[0],
    as_of_ym: Optional[Tuple[int, int]] = None,
) -> List[ProductRecommendation]:
    """
    Computes restocking recommendations across the selected outlets using the
    75% partial expiry replacement rule:
      expired_replacement = floor(expired_this_month * 75%)
      need = latest_month_sales + expired_replacement
      available (usable) stock = current_stock - expired_on_hand (remaining <= 0)
      new_total_target = usable_stock + need
    """
    if objective not in OBJECTIVES:
        raise ValueError(f"Unknown restocking objective: {objective}")

    batches = list(all_batches)
    if selected_outlets is not None:
        selected_set = set(selected_outlets)
        batches = [b for b in batches if b.outlet in selected_set]

    if as_of_ym is not None:
        batches = [b for b in batches if (b.report_year, b.report_month) <= as_of_ym]

    if not batches:
        return []

    grouped: Dict[Tuple[str, str], List[BatchRecord]] = {}
    for b in batches:
        key = (b.outlet, b.item_id)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(b)

    recommendations: List[ProductRecommendation] = []

    for (outlet, item_id), prod_batches in grouped.items():
        months_dict: Dict[Tuple[int, int], List[BatchRecord]] = {}
        for b in prod_batches:
            m_key = (b.report_year, b.report_month)
            if m_key not in months_dict:
                months_dict[m_key] = []
            months_dict[m_key].append(b)

        history: List[Tuple[int, int, float]] = []
        for (y, m), m_batches in months_dict.items():
            history.append((y, m, m_batches[0].mth_purchase))

        predicted_monthly = predict_demand(history)

        latest_ym = max(months_dict.keys(), key=lambda ym: (ym[0], ym[1]))
        latest_batches = months_dict[latest_ym]
        latest_year, latest_month = latest_ym

        days_in_month = calendar.monthrange(latest_year, latest_month)[1]
        daily_demand = predicted_monthly / days_in_month if days_in_month > 0 else 0.0

        first_batch = latest_batches[0]
        item_name = first_batch.item_name
        category = first_batch.category
        unit_cost = first_batch.unit_cost
        unit_sell = first_batch.unit_sell
        supplier_rating = first_batch.supplier_rating
        latest_sales = int(round(first_batch.mth_purchase))

        current_stock = sum(b.current_total_stock for b in latest_batches)
        expired_stock = sum(b.current_total_stock for b in latest_batches if b.remaining_shelf_life <= 0)
        usable_stock = current_stock - expired_stock
        near_expiry_stock = sum(b.current_total_stock for b in latest_batches if 0 < b.remaining_shelf_life <= 14)
        expiring_stock = expired_stock + near_expiry_stock

        expired_this_month, loss_source = calculate_monthly_expired_units(latest_batches)
        expired_replacement = (expired_this_month * EXPIRED_REPLACEMENT_PERCENT) // 100
        need_units = latest_sales + expired_replacement
        target_stock = usable_stock + need_units

        gross_margin = max(0.0, unit_sell - unit_cost)
        margin_cents = int(round(gross_margin * 100))
        if objective == "Popularity":
            priority_value = int(round(predicted_monthly * 100))
        elif objective == "Profit":
            priority_value = margin_cents
        else:
            priority_value = 100 + margin_cents

        if unit_cost > 0:
            value_per_cost = priority_value / unit_cost
        else:
            value_per_cost = float("inf")

        notes: List[str] = []
        if near_expiry_stock > 0:
            notes.append(f"{int(round(near_expiry_stock))} near-expiry units remain available; review before buying")
        if loss_source.startswith("Estimated"):
            notes.append("Supply mth_expired to include losses already disposed of")
        if need_units > 0 and priority_value <= 0:
            notes.append("Zero objective score: no budget allocated")

        rec = ProductRecommendation(
            outlet=outlet,
            item_id=item_id,
            item_name=item_name,
            category=category,
            unit_cost=unit_cost,
            unit_sell=unit_sell,
            predicted_monthly_demand=predicted_monthly,
            daily_demand=daily_demand,
            usable_stock=usable_stock,
            expiring_stock=expiring_stock,
            target_stock=target_stock,
            need=need_units,
            priority_value=priority_value,
            value_per_cost=value_per_cost,
            supplier_rating=supplier_rating,
            objective=objective,
            report_month_str=f"{latest_year:04d}-{latest_month:02d}",
            latest_sales=latest_sales,
            current_stock=current_stock,
            expired_stock=expired_stock,
            near_expiry_stock=near_expiry_stock,
            expired_this_month=expired_this_month,
            expired_replacement=expired_replacement,
            loss_source=loss_source,
            projected_stock=int(round(usable_stock)),
            review_notes="; ".join(notes),
        )
        recommendations.append(rec)

    ranked = merge_sort(recommendations, key=lambda r: (r.value_per_cost, -int(r.item_id == "")), reverse=True)
    for idx, r in enumerate(ranked, start=1):
        r.rank = idx

    return ranked
