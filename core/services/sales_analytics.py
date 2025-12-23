from django.db.models import Sum
from django.utils import timezone

from ..models import SaleItem


def get_item_sales(year=None, month=None, limit=5):
    """
    Returns high & low selling stock items
    - If month is provided → Monthly
    - If month is None → Yearly
    """

    now = timezone.now()
    year = int(year or now.year)

    filters = {
        "sale__sale_date__year": year,
        "sale__is_servicing": False,   # stock sales only
    }

    if month:
        filters["sale__sale_date__month"] = int(month)

    qs = (
        SaleItem.objects
        .filter(**filters)
        .values(
            "item_id",
            "item__name",
            "item__model",
            "item__category__name"
        )
        .annotate(total_qty=Sum("quantity"))
        .filter(total_qty__gt=0)
    )

    return {
        "year": year,
        "month": month,
        "high_sales": qs.order_by("-total_qty")[:limit],
        "low_sales": qs.order_by("total_qty")[:limit],
    }
