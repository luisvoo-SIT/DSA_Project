"""
Matplotlib canvas wrapper for PySide6 with dark/clean modern theme styling.
"""
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PySide6.QtWidgets import QWidget, QVBoxLayout
import pandas as pd
from typing import List
from core.models import ProductRecommendation


class MatplotlibCanvas(QWidget):
    """Embeddable Matplotlib Figure Canvas."""

    def __init__(self, parent=None, width=6, height=4, dpi=100):
        super().__init__(parent)
        self.figure = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)


def plot_expiry_distribution(canvas: MatplotlibCanvas, df_batches: pd.DataFrame) -> None:
    """
    Plots batch stock quantities grouped by remaining shelf life intervals,
    including expired units and historical snapshots.
    """
    canvas.figure.clear()
    ax = canvas.figure.add_subplot(111)

    if df_batches.empty:
        ax.text(0.5, 0.5, "No inventory data loaded", ha="center", va="center", color="#7f8c8d", fontsize=12)
        ax.axis("off")
        canvas.canvas.draw()
        return

    # Define bins and labels for remaining shelf life
    # Expired: <= 0 days
    # Expiring Soon: 1 - 14 days
    # Near Expiry: 15 - 30 days
    # Short Shelf: 31 - 60 days
    # Medium Shelf: 61 - 90 days
    # Long Shelf: > 90 days
    bins = [-float("inf"), 0, 14, 30, 60, 90, float("inf")]
    labels = [
        "Expired\n(<= 0d)",
        "Expiring Soon\n(1-14d)",
        "Near Expiry\n(15-30d)",
        "Short Term\n(31-60d)",
        "Medium Term\n(61-90d)",
        "Fresh\n(> 90d)",
    ]
    colors = ["#e74c3c", "#e67e22", "#f39c12", "#3498db", "#2980b9", "#2ecc71"]

    df_copy = df_batches.copy()
    df_copy["shelf_life_group"] = pd.cut(
        df_copy["remaining_shelf_life"],
        bins=bins,
        labels=labels,
        right=True
    )

    # Group by shelf life group and sum current_total_stock
    grouped = df_copy.groupby("shelf_life_group", observed=False)["current_total_stock"].sum()

    bars = ax.bar(labels, grouped.values, color=colors, edgecolor="#2c3e50", linewidth=0.8, width=0.55)
    ax.set_title("Batch Stock Quantities by Remaining Shelf Life (Snapshot Aggregation)", fontsize=11, fontweight="bold", pad=10)
    ax.set_ylabel("Total Units in Batches", fontsize=10)
    ax.set_xlabel("Remaining Shelf Life Category", fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Add count labels on top of bars
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.annotate(
                f"{int(height):,}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold"
            )

    ax.set_ylim(0, max(grouped.values, default=10) * 1.15)
    canvas.figure.tight_layout()
    canvas.canvas.draw()


def plot_recommendations_chart(
    canvas: MatplotlibCanvas,
    recommendations: List[ProductRecommendation],
    top_n: int = 20,
    remaining_budget: float = None,
    total_budget: float = None,
) -> None:
    """
    Plots Need vs Allocated units for the first 20 ranked, displayed products,
    and displays the remaining budget badge at the bottom right of the chart.
    """
    canvas.figure.clear()
    ax = canvas.figure.add_subplot(111)

    items = recommendations[:top_n]
    if not items:
        ax.text(0.5, 0.5, "No recommendations to display", ha="center", va="center", color="#7f8c8d", fontsize=12)
        ax.axis("off")
        canvas.canvas.draw()
        return

    # Invert so rank 1 is at the top
    items_rev = list(reversed(items))
    names = [f"#{p.rank} {p.item_name} ({p.outlet})" for p in items_rev]
    needs = [p.need for p in items_rev]
    allocs = [p.allocated_units for p in items_rev]

    y = range(len(names))
    height = 0.38

    bar1 = ax.barh([pos + height / 2 for pos in y], needs, height=height, label="Calculated Need", color="#3498db", alpha=0.9)
    bar2 = ax.barh([pos - height / 2 for pos in y], allocs, height=height, label="Budget Allocated", color="#2ecc71", alpha=0.9)

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Units", fontsize=10)
    ax.set_title(f"Restocking Need vs Allocated Restock Units (First {len(items)} Displayed Products)", fontsize=11, fontweight="bold", pad=10)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    # Display remaining budget badge on the bottom right of the graph
    if remaining_budget is not None:
        if total_budget is not None:
            spent = max(0.0, total_budget - remaining_budget)
            badge_text = f"Allocated: ${spent:,.2f} / ${total_budget:,.2f}\nRemaining Budget: ${remaining_budget:,.2f}"
        else:
            badge_text = f"Remaining Budget: ${remaining_budget:,.2f}"
        ax.text(
            0.985,
            0.03,
            badge_text,
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#1e293b",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="#f8fafc", edgecolor="#94a3b8", alpha=0.94),
        )

    # Max x limit
    max_val = max(max(needs, default=0), max(allocs, default=0))
    ax.set_xlim(0, max(10, max_val * 1.15))

    canvas.figure.tight_layout()
    canvas.canvas.draw()
