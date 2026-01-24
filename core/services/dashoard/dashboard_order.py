# =================================================
# 🧾 ORDERS (Paginated)
# =================================================
from django.core.paginator import Paginator
from core.models import Order


def get_orders(page=1, page_size=5):
    qs = (
        Order.objects.all()
        .order_by("-order_date")
        .values(
            "id",
            "customer_name",
            "contact_no",
            "vehicle_model",
            "order_date",
            "total_amount",
            "advance",
            "remaining_amount",
        )
    )

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    results = []
    for order in page_obj:
        results.append({
            "id": order["id"],
            "customer_name": order["customer_name"],
            "contact_no": order["contact_no"],
            "vehicle_model": order["vehicle_model"],
            "order_date": order["order_date"],
            "total_amount": float(order["total_amount"] or 0),
            "advance": float(order["advance"] or 0),
            "remaining_amount": float(order["remaining_amount"] or 0),
        })

    return {
        "results": results,
        "pagination": {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        },
    }
