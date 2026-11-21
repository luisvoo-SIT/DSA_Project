"""
Restocking calculation and evaluation logic.
"""
import calendar
import math
from typing import Dict, List, Optional, Tuple
from core.models import BatchRecord, ProductRecommendation
from core.forecasting import predict_demand
from core.sorting import merge_sort


def calculate_restocking_recommendations(
    all_batches: List[BatchRecord],
    selected_outlets: Optional[List[str]] = None
) -> List[ProductRecommendation]:
    """
    Computes restocking recommendations across the selected outlets.
    
    Steps:
    1. Filter batches by selected outlets (if specified).
    2. Group batches by (outlet, item_id).
    3. For each (outlet, item_id):
       - Find historical monthly purchases for forecasting.
       - Identify latest report snapshot (year, month).
       - In latest snapshot, identify usable stock (> 14 days remaining) and expiring stock (<= 14 days).
       - Extract product-level price (unit_cost, unit_sell), lead_time, shelf_life, supplier_rating
         from the first batch in the latest snapshot.
       - Forecast monthly demand and compute daily demand = monthly_demand / days_in_latest_month.
       - Target stock = daily_demand * (lead_time + 30).
       - Raw need = target_stock - usable_stock.
       - Capped need = min(daily_demand * shelf_life, max(0.0, raw_need)).
       - need_units = int(round(capped_need)).
       - Gross margin = max(0.0, unit_sell - unit_cost).
       - margin_cents = int(round(gross_margin * 100)).
       - priority_value = 100 + margin_cents.
       - value_per_cost = priority_value / unit_cost if unit_cost > 0 else float('inf').
    4. Rank products across all selected outlets using merge sort by value_per_cost descending.
    """
    if selected_outlets is not None:
        selected_set = set(selected_outlets)
        batches = [b for b in all_batches if b.outlet in selected_set]
    else:
        batches = list(all_batches)

    if not batches:
        return []

    # Group batches by (outlet, item_id)
    grouped: Dict[Tuple[str, str], List[BatchRecord]] = {}
    for b in batches:
        key = (b.outlet, b.item_id)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(b)

    recommendations: List[ProductRecommendation] = []

    for (outlet, item_id), prod_batches in grouped.items():
        # Find all report months available for this product and outlet
        months_dict: Dict[Tuple[int, int], List[BatchRecord]] = {}
        for b in prod_batches:
            m_key = (b.report_year, b.report_month)
            if m_key not in months_dict:
                months_dict[m_key] = []
            months_dict[m_key].append(b)

        # Build historical purchases list: (year, month, purchase_val)
        history: List[Tuple[int, int, float]] = []
        for (y, m), m_batches in months_dict.items():
            # Purchases repeat across batches and must agree; count once per month
            history.append((y, m, m_batches[0].mth_purchase))

        # Predict monthly demand
        predicted_monthly = predict_demand(history)

        # Identify latest snapshot
        latest_ym = max(months_dict.keys(), key=lambda ym: (ym[0], ym[1]))
        latest_batches = months_dict[latest_ym]
        latest_year, latest_month = latest_ym

        days_in_month = calendar.monthrange(latest_year, latest_month)[1]
        daily_demand = predicted_monthly / days_in_month if days_in_month > 0 else 0.0

        # For product-level fields, use first batch in the latest snapshot
        first_batch = latest_batches[0]
        item_name = first_batch.item_name
        category = first_batch.category
        unit_cost = first_batch.unit_cost
        unit_sell = first_batch.unit_sell
        lead_time = first_batch.lead_time
        shelf_life = first_batch.shelf_life
        supplier_rating = first_batch.supplier_rating

        # Calculate usable vs expiring stock in latest snapshot
        usable_stock = 0.0
        expiring_stock = 0.0
        for b in latest_batches:
            if b.is_expiring:  # remaining_shelf_life <= 14
                expiring_stock += b.current_total_stock
            else:
                usable_stock += b.current_total_stock

        # Target stock covers lead time + 30 days
        target_stock = daily_demand * (lead_time + 30)

        # Raw order need = target_stock - usable_stock
        raw_need = max(0.0, target_stock - usable_stock)

        # Capped at forecast sales over the product's shelf life
        max_order = daily_demand * shelf_life
        capped_need = min(raw_need, max_order)
        need_units = int(round(capped_need))

        # Priority value calculation
        gross_margin = max(0.0, unit_sell - unit_cost)
        margin_cents = int(round(gross_margin * 100))
        priority_value = 100 + margin_cents

        if unit_cost > 0:
            value_per_cost = priority_value / unit_cost
        else:
            value_per_cost = float('inf')

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
        )
        recommendations.append(rec)

    # Rank products across outlets by value_per_cost descending using Merge Sort
    ranked = merge_sort(recommendations, key=lambda r: r.value_per_cost, reverse=True)
    for idx, r in enumerate(ranked, start=1):
        r.rank = idx

    return ranked



