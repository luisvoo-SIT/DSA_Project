"""
CSV importer module with strict schema and business rule validation.
"""
import calendar
import csv
import datetime
import os
import re
from typing import Dict, List, Set, Tuple
from core.models import BatchRecord, parse_batch_dates

REQUIRED_HEADERS = [
    "item_id",
    "item_name",
    "category",
    "unit_cost",
    "unit_sell",
    "current_total_stock",
    "mth_purchase",
    "lead_time",
    "shelf_life",
    "batch_no",
    "supplier_rating",
]

FILENAME_REGEX = re.compile(r"^(?P<outlet>.+)_(?P<year>\d{4})_(?P<month>\d{2})\.csv$", re.IGNORECASE)


def parse_filename(filepath: str) -> Tuple[str, int, int]:
    """
    Parses filename like 'Outlet_A_2026_06.csv' into (outlet_name, year, month).
    """
    filename = os.path.basename(filepath).strip()
    match = FILENAME_REGEX.match(filename)
    if not match:
        raise ValueError(
            f"Invalid filename '{filename}'. Filename must follow the format 'Outlet_Name_YYYY_MM.csv' (e.g. 'Outlet_A_2026_06.csv')."
        )
    
    outlet = match.group("outlet")
    year = int(match.group("year"))
    month = int(match.group("month"))
    
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month '{month}' in filename '{filename}'. Month must be between 01 and 12.")
        
    return outlet, year, month


def validate_price_precision(val_str: str) -> float:
    """Checks that price has at most two decimal places and returns float."""
    clean_str = val_str.strip()
    if "." in clean_str:
        decimals = clean_str.split(".")[1]
        if len(decimals) > 2:
            raise ValueError(f"Price '{clean_str}' has more than 2 decimal places.")
    val = float(clean_str)
    return val


def import_monthly_csv(filepath: str) -> Tuple[str, int, int, List[BatchRecord]]:
    """
    Imports and validates a monthly inventory CSV file.
    
    Returns:
        (outlet_name, report_year, report_month, list_of_batch_records)
    """
    outlet, report_year, report_month = parse_filename(filepath)

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    batches: List[BatchRecord] = []
    seen_product_batches: Set[Tuple[str, str]] = set()
    product_purchases: Dict[str, float] = {}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        
        # Check required headers
        if not reader.fieldnames:
            raise ValueError(f"File '{os.path.basename(filepath)}' is empty.")
            
        fieldnames_clean = [h.strip() for h in reader.fieldnames if h]
        missing = [h for h in REQUIRED_HEADERS if h not in fieldnames_clean]
        if missing:
            raise ValueError(
                f"File '{os.path.basename(filepath)}' is missing required headers: {', '.join(missing)}."
            )

        row_num = 1
        for row in reader:
            row_num += 1
            # Strip whitespace
            clean_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}

            item_id = clean_row.get("item_id", "")
            item_name = clean_row.get("item_name", "")
            category = clean_row.get("category", "")
            raw_cost = clean_row.get("unit_cost", "")
            raw_sell = clean_row.get("unit_sell", "")
            raw_stock = clean_row.get("current_total_stock", "")
            raw_purchase = clean_row.get("mth_purchase", "")
            raw_lead = clean_row.get("lead_time", "")
            raw_shelf = clean_row.get("shelf_life", "")
            batch_no = clean_row.get("batch_no", "")
            raw_rating = clean_row.get("supplier_rating", "")

            if not item_id:
                raise ValueError(f"Row {row_num}: Missing item_id.")

            # Validate batch_no (4-character MMYY text with leading zeroes preserved)
            if len(batch_no) != 4 or not batch_no.isdigit():
                raise ValueError(
                    f"Row {row_num}: Invalid batch_no '{batch_no}'. Must be 4-character MMYY text (e.g. '0526')."
                )

            # Reject duplicate product/batch pairs
            pair = (item_id, batch_no)
            if pair in seen_product_batches:
                raise ValueError(
                    f"Row {row_num}: Duplicate product/batch pair detected: item_id '{item_id}', batch_no '{batch_no}'."
                )
            seen_product_batches.add(pair)

            # Validate prices (at most 2 decimal places, non-negative)
            try:
                unit_cost = validate_price_precision(raw_cost)
            except ValueError as e:
                raise ValueError(f"Row {row_num} (item '{item_id}'): Invalid unit_cost: {e}")
            if unit_cost < 0:
                raise ValueError(f"Row {row_num} (item '{item_id}'): unit_cost cannot be negative ({unit_cost}).")

            try:
                unit_sell = validate_price_precision(raw_sell)
            except ValueError as e:
                raise ValueError(f"Row {row_num} (item '{item_id}'): Invalid unit_sell: {e}")
            if unit_sell < 0:
                raise ValueError(f"Row {row_num} (item '{item_id}'): unit_sell cannot be negative ({unit_sell}).")

            # Validate stock (non-negative)
            try:
                current_total_stock = float(raw_stock)
            except ValueError:
                raise ValueError(f"Row {row_num} (item '{item_id}'): Invalid current_total_stock '{raw_stock}'.")
            if current_total_stock < 0:
                raise ValueError(f"Row {row_num} (item '{item_id}'): current_total_stock cannot be negative ({current_total_stock}).")

            # Validate mth_purchase (non-negative, must agree across batches for the same product)
            try:
                mth_purchase = float(raw_purchase)
            except ValueError:
                raise ValueError(f"Row {row_num} (item '{item_id}'): Invalid mth_purchase '{raw_purchase}'.")
            if mth_purchase < 0:
                raise ValueError(f"Row {row_num} (item '{item_id}'): mth_purchase cannot be negative ({mth_purchase}).")

            if item_id in product_purchases:
                if abs(product_purchases[item_id] - mth_purchase) > 1e-4:
                    raise ValueError(
                        f"Row {row_num}: Inconsistent mth_purchase for product '{item_id}'. "
                        f"Previous batch has {product_purchases[item_id]}, but this batch has {mth_purchase}. "
                        "Monthly customer purchases must agree across batches for the same product."
                    )
            else:
                product_purchases[item_id] = mth_purchase

            # Validate lead_time and shelf_life (non-negative integers)
            try:
                lead_time = int(raw_lead)
            except ValueError:
                raise ValueError(f"Row {row_num} (item '{item_id}'): Invalid lead_time '{raw_lead}'.")
            if lead_time < 0:
                raise ValueError(f"Row {row_num} (item '{item_id}'): lead_time cannot be negative ({lead_time}).")

            try:
                shelf_life = int(raw_shelf)
            except ValueError:
                raise ValueError(f"Row {row_num} (item '{item_id}'): Invalid shelf_life '{raw_shelf}'.")
            if shelf_life < 0:
                raise ValueError(f"Row {row_num} (item '{item_id}'): shelf_life cannot be negative ({shelf_life}).")

            # Validate supplier_rating (0-5)
            try:
                supplier_rating = float(raw_rating)
            except ValueError:
                raise ValueError(f"Row {row_num} (item '{item_id}'): Invalid supplier_rating '{raw_rating}'.")
            if supplier_rating < 0.0 or supplier_rating > 5.0:
                raise ValueError(
                    f"Row {row_num} (item '{item_id}'): supplier_rating must be between 0 and 5 ({supplier_rating})."
                )

            # Validate dates and assumed delivery vs report date
            try:
                parse_batch_dates(batch_no, lead_time, shelf_life, report_year, report_month)
            except ValueError as e:
                raise ValueError(f"Row {row_num} (item '{item_id}', batch '{batch_no}'): {e}")

            record = BatchRecord(
                outlet=outlet,
                report_year=report_year,
                report_month=report_month,
                item_id=item_id,
                item_name=item_name,
                category=category,
                unit_cost=unit_cost,
                unit_sell=unit_sell,
                current_total_stock=current_total_stock,
                mth_purchase=mth_purchase,
                lead_time=lead_time,
                shelf_life=shelf_life,
                batch_no=batch_no,
                supplier_rating=supplier_rating,
            )
            batches.append(record)

    return outlet, report_year, report_month, batches
