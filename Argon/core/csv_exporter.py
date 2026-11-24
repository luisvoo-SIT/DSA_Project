"""
CSV exporter module for saving edited monthly data and exporting recommendations.
"""
import csv
import math
from typing import List
from core.models import BatchRecord, ProductRecommendation
from core.csv_importer import REQUIRED_HEADERS


def save_edited_csv(filepath: str, batches: List[BatchRecord]) -> None:
    """
    Saves in-memory batch records for an outlet/month to CSV adhering to the schema.
    Preserves optional initial_stock_target and mth_expired columns when present.
    """
    fieldnames = list(REQUIRED_HEADERS)
    has_initial_target = any(b.initial_stock_target is not None for b in batches)
    has_mth_expired = any(b.mth_expired is not None for b in batches)
    if has_initial_target:
        fieldnames.append("initial_stock_target")
    if has_mth_expired:
        fieldnames.append("mth_expired")

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for b in batches:
            row = {
                "item_id": b.item_id,
                "item_name": b.item_name,
                "category": b.category,
                "unit_cost": f"{b.unit_cost:.2f}",
                "unit_sell": f"{b.unit_sell:.2f}",
                "current_total_stock": int(b.current_total_stock) if float(b.current_total_stock).is_integer() else b.current_total_stock,
                "mth_purchase": int(b.mth_purchase) if float(b.mth_purchase).is_integer() else b.mth_purchase,
                "lead_time": b.lead_time,
                "shelf_life": b.shelf_life,
                "batch_no": str(b.batch_no).zfill(4),
                "supplier_rating": b.supplier_rating,
            }
            if has_initial_target:
                row["initial_stock_target"] = "" if b.initial_stock_target is None else b.initial_stock_target
            if has_mth_expired:
                row["mth_expired"] = "" if b.mth_expired is None else b.mth_expired
            writer.writerow(row)


def export_recommendations_csv(filepath: str, recommendations: List[ProductRecommendation]) -> None:
    """
    Exports calculated restocking recommendations to a CSV file.
    """
    headers = [
        "rank",
        "objective",
        "outlet",
        "item_id",
        "item_name",
        "category",
        "report_month",
        "latest_sales",
        "unit_cost",
        "unit_sell",
        "predicted_monthly_demand",
        "daily_demand",
        "current_stock",
        "expired_stock",
        "usable_stock",
        "near_expiry_stock",
        "expiring_stock",
        "expired_this_month",
        "loss_source",
        "expired_replacement",
        "target_stock",
        "need",
        "allocated_units",
        "projected_stock",
        "allocated_cost",
        "priority_value",
        "value_per_cost",
        "supplier_rating",
        "review_notes",
    ]

    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in recommendations:
            row = {
                "rank": r.rank,
                "objective": r.objective,
                "outlet": r.outlet,
                "item_id": r.item_id,
                "item_name": r.item_name,
                "category": r.category,
                "report_month": r.report_month_str,
                "latest_sales": r.latest_sales,
                "unit_cost": f"{r.unit_cost:.2f}",
                "unit_sell": f"{r.unit_sell:.2f}",
                "predicted_monthly_demand": f"{r.predicted_monthly_demand:.2f}",
                "daily_demand": f"{r.daily_demand:.2f}",
                "current_stock": int(r.current_stock) if float(r.current_stock).is_integer() else f"{r.current_stock:.1f}",
                "expired_stock": int(r.expired_stock) if float(r.expired_stock).is_integer() else f"{r.expired_stock:.1f}",
                "usable_stock": int(r.usable_stock) if float(r.usable_stock).is_integer() else f"{r.usable_stock:.1f}",
                "near_expiry_stock": int(r.near_expiry_stock) if float(r.near_expiry_stock).is_integer() else f"{r.near_expiry_stock:.1f}",
                "expiring_stock": int(r.expiring_stock) if float(r.expiring_stock).is_integer() else f"{r.expiring_stock:.1f}",
                "expired_this_month": r.expired_this_month,
                "loss_source": r.loss_source,
                "expired_replacement": r.expired_replacement,
                "target_stock": int(r.target_stock) if float(r.target_stock).is_integer() else f"{r.target_stock:.2f}",
                "need": r.need,
                "allocated_units": r.allocated_units,
                "projected_stock": r.projected_stock,
                "allocated_cost": f"{r.allocated_cost:.2f}",
                "priority_value": r.priority_value,
                "value_per_cost": "inf" if math.isinf(r.value_per_cost) else f"{r.value_per_cost:.4f}",
                "supplier_rating": r.supplier_rating,
                "review_notes": r.review_notes,
            }
            writer.writerow(row)
