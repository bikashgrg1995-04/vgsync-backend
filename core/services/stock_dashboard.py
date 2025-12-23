from django.db.models import Sum
from django.utils import timezone

from core.models import Stock
from core.services.sales_analytics import get_item_sales  # ✅ CORRECT

LOW_STOCK_THRESHOLD = 5


def get_stock_dashboard(year=None, month=None):
    now = timezone.now()
    year = int(year or now.year)

    period = "monthly" if month else "yearly"

    # Sales analytics
    sales_data = get_item_sales(year=year, month=month, limit=5)

    # Stock summary
    total_items = Stock.objects.count()
    total_stock = Stock.objects.aggregate(
        total=Sum("stock")
    )["total"] or 0

    low_stock_items = Stock.objects.filter(
        stock__lte=LOW_STOCK_THRESHOLD
    ).values(
        "id", "name", "model", "stock", "category__name"
    ).order_by("stock")

    return {
        "period": period,
        "year": year,
        "month": month,
        "summary": {
            "total_items": total_items,
            "total_stock": total_stock,
            "low_stock_count": low_stock_items.count(),
        },
        "top_sales": sales_data["high_sales"],
        "low_sales": sales_data["low_sales"],
        "low_stock_items": list(low_stock_items),
        "stock_threshold": LOW_STOCK_THRESHOLD,
    }
