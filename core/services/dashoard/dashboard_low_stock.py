# =================================================
# 📦 LOW / OUT OF STOCK (Paginated)
# =================================================
from django.core.paginator import Paginator
from core.models import Stock


def get_low_stock(threshold=5, page=1, page_size=5):
    """
    - Only items with stock <= threshold
    - Ordered by lowest stock first
    - Paginated response
    """

    qs = (
        Stock.objects.filter(stock__lte=threshold)
        .order_by("stock")  # 🔥 minimum stock first
        .values(
            "id",
            "item_no",
            "name",
            "model",
            "category_id",
            "stock",
            "sale_price",
        )
    )

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    return {
        "results": list(page_obj),
        "pagination": {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        },
    }
