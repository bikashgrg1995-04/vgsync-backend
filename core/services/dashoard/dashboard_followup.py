from core.models import FollowUpDashboard, BikeSaleFollowUp
from django.core.paginator import Paginator
from datetime import timedelta
from core.signals import safe_local_date

def get_followups(days=15, page=1, page_size=5):
    today = safe_local_date()
    end_date = today + timedelta(days=days)

    sale_qs = FollowUpDashboard.objects.filter(
        status="pending",
        follow_up_date__gte=today,
        follow_up_date__lte=end_date
    )

    bike_qs = BikeSaleFollowUp.objects.filter(
        status="pending",
        follow_up_date__gte=today,
        follow_up_date__lte=end_date
    )

    # Merge and sort by follow_up_date
    combined = list(sale_qs.values(
        "customer_name", "contact_no", "vehicle", "follow_up_date", "remarks", "status"
    )) + list(bike_qs.values(
        "customer_name", "contact_no", "vehicle", "follow_up_date", "remarks", "status"
    ))
    combined.sort(key=lambda x: x["follow_up_date"])

    paginator = Paginator(combined, page_size)
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
