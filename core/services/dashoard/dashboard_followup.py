# core/services/dashoard/dashboard_followup.py
from datetime import timedelta
from django.core.paginator import Paginator
from core.models import FollowUpDashboard
from core.signals import safe_local_date


def get_followups(days=15, page=1, page_size=5):
    """
    Returns pending follow-ups from today up to next `days`.
    Past follow-ups are hidden.
    """
    today = safe_local_date()  # Nepal-safe today
    end_date = today + timedelta(days=days)

    qs = FollowUpDashboard.objects.filter(
        status="pending",
        follow_up_date__gte=today,
        follow_up_date__lte=end_date,
    ).order_by("follow_up_date")  # nearest first

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    results = []
    for f in page_obj:
        results.append({
            "id": f.id,
            "customer_name": f.customer_name,
            "contact_no": f.contact_no,
            "vehicle": f.vehicle,
            "follow_up_date": f.follow_up_date,
            "remarks": f.remarks,
            "status": f.status,
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
