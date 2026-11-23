"""
CSV exporter module for saving edited monthly data and exporting recommendations.
"""
import csv
from typing import List
from core.models import BatchRecord, ProductRecommendation
from core.csv_importer import REQUIRED_HEADERS


def save_edited_csv(filepath: str, batches: List[BatchRecord]) -> None:
    """
    Saves in-memory batch records for an outlet/month to CSV adhering to the schema.
    """
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_HEADERS)
        writer.writeheader()
        for b in batches:
            row = {
                "item_id": b.item_id,
                "item_name": b.item_name,
                "category": b.category,
                "unit_cost": f"{b.unit_cost:.2f}",
                "unit_sell": f"{b.unit_sell:.2f}",
                "current_total_stock": int(b.current_total_stock) if b.current_total_stock.is_integer() else b.current_total_stock,
                "mth_purchase": int(b.mth_purchase) if b.mth_purchase.is_integer() else b.mth_purchase,
                "lead_time": b.lead_time,
                "shelf_life": b.shelf_life,
                "batch_no": str(b.batch_no).zfill(4),
                "supplier_rating": b.supplier_rating,
            }
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
        "unit_cost",
        "unit_sell",
        "predicted_monthly_demand",
        "daily_demand",
        "usable_stock",
        "expiring_stock",
        "target_stock",
        "need",
        "allocated_units",
        "allocated_cost",
        "priority_value",
        "value_per_cost",
        "supplier_rating",
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
                "unit_cost": f"{r.unit_cost:.2f}",
                "unit_sell": f"{r.unit_sell:.2f}",
                "predicted_monthly_demand": f"{r.predicted_monthly_demand:.2f}",
                "daily_demand": f"{r.daily_demand:.2f}",
                "usable_stock": int(r.usable_stock) if r.usable_stock.is_integer() else f"{r.usable_stock:.1f}",
                "expiring_stock": int(r.expiring_stock) if r.expiring_stock.is_integer() else f"{r.expiring_stock:.1f}",
                "target_stock": f"{r.target_stock:.2f}",
                "need": r.need,
                "allocated_units": r.allocated_units,
                "allocated_cost": f"{r.allocated_cost:.2f}",
                "priority_value": r.priority_value,
                "value_per_cost": "inf" if math.isinf(r.value_per_cost) else f"{r.value_per_cost:.4f}",
                "supplier_rating": r.supplier_rating,
            }
            writer.writerow(row)


import math
