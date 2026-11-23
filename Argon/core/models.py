import calendar
import datetime
from dataclasses import dataclass, field
from typing import Optional


def parse_batch_dates(batch_no: str, lead_time: int, shelf_life: int, report_year: int, report_month: int):
    """
    Parses MMYY batch number, calculates delivery date, expiry date,
    report date (last day of report month), and remaining shelf life.
    """
    if not isinstance(batch_no, str) or len(batch_no) != 4 or not batch_no.isdigit():
        raise ValueError(f"Invalid batch_no '{batch_no}': must be 4-digit MMYY text.")
    
    batch_mm = int(batch_no[:2])
    batch_yy = int(batch_no[2:])
    if batch_mm < 1 or batch_mm > 12:
        raise ValueError(f"Invalid month in batch_no '{batch_no}': month must be 01-12.")
    
    order_year = 2000 + batch_yy
    order_last_day = calendar.monthrange(order_year, batch_mm)[1]
    order_date = datetime.date(order_year, batch_mm, order_last_day)
    
    delivery_date = order_date + datetime.timedelta(days=int(lead_time))
    
    report_last_day = calendar.monthrange(report_year, report_month)[1]
    report_date = datetime.date(report_year, report_month, report_last_day)
    
    if delivery_date > report_date:
        raise ValueError(
            f"Batch {batch_no} assumed delivery date ({delivery_date}) is after report date ({report_date})."
        )
    
    expiry_date = delivery_date + datetime.timedelta(days=int(shelf_life))
    remaining_shelf_life = (expiry_date - report_date).days
    is_expiring = remaining_shelf_life <= 14
    
    return {
        "order_date": order_date,
        "delivery_date": delivery_date,
        "expiry_date": expiry_date,
        "report_date": report_date,
        "remaining_shelf_life": remaining_shelf_life,
        "is_expiring": is_expiring,
    }


@dataclass
class BatchRecord:
    outlet: str
    report_year: int
    report_month: int
    item_id: str
    item_name: str
    category: str
    unit_cost: float
    unit_sell: float
    current_total_stock: float
    mth_purchase: float
    lead_time: int
    shelf_life: int
    batch_no: str
    supplier_rating: float
    
    # Computed fields
    order_date: Optional[datetime.date] = None
    delivery_date: Optional[datetime.date] = None
    expiry_date: Optional[datetime.date] = None
    report_date: Optional[datetime.date] = None
    remaining_shelf_life: int = 0
    is_expiring: bool = False
    
    def __post_init__(self):
        # Normalize batch_no to 4 digits with leading zeroes
        if isinstance(self.batch_no, (int, float)):
            self.batch_no = f"{int(self.batch_no):04d}"
        else:
            self.batch_no = str(self.batch_no).strip().zfill(4)
            
        dates = parse_batch_dates(
            self.batch_no, self.lead_time, self.shelf_life, self.report_year, self.report_month
        )
        self.order_date = dates["order_date"]
        self.delivery_date = dates["delivery_date"]
        self.expiry_date = dates["expiry_date"]
        self.report_date = dates["report_date"]
        self.remaining_shelf_life = dates["remaining_shelf_life"]
        self.is_expiring = dates["is_expiring"]

    @property
    def report_month_str(self) -> str:
        return f"{self.report_year:04d}-{self.report_month:02d}"


@dataclass
class ProductRecommendation:
    outlet: str
    item_id: str
    item_name: str
    category: str
    unit_cost: float
    unit_sell: float
    predicted_monthly_demand: float
    daily_demand: float
    usable_stock: float
    expiring_stock: float
    target_stock: float
    need: int
    priority_value: int
    value_per_cost: float
    rank: int = 0
    allocated_units: int = 0
    allocated_cost: float = 0.0
    supplier_rating: float = 0.0
    objective: str = "Profit"
