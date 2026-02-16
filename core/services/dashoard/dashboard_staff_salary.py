from django.db.models import Prefetch
from django.core.paginator import Paginator
from core.models import Staff, SalaryTracker

def get_staff_salaries(page=1, page_size=5):
    salary_tracker_prefetch = Prefetch(
        "salarytracker_set",
        queryset=SalaryTracker.objects.order_by("-date"),
        to_attr="all_trackers"
    )

    staff_qs = Staff.objects.filter(is_active=True).order_by("name").prefetch_related(salary_tracker_prefetch)
    paginator = Paginator(staff_qs, page_size)
    page_obj = paginator.get_page(page)

    results = []

    for staff in page_obj:
        # 1️⃣ Get partial payments first (latest)
        partial_trackers = [t for t in staff.all_trackers if t.status == "partial"]

        if partial_trackers:
            last_salary = partial_trackers[0]
        else:
            # 2️⃣ Otherwise get pending/unpaid tracker (latest)
            pending_trackers = [t for t in staff.all_trackers if t.status == "pending"]
            last_salary = pending_trackers[0] if pending_trackers else None

        results.append({
            "staff_id": staff.id,
            "name": staff.name,
            "designation": staff.designation,
            "salary_mode": staff.salary_mode,
            "last_paid_amount": float(last_salary.paid_amount) if last_salary else 0,
            "total_salary": float(last_salary.total_salary) if last_salary else 0,
            "remaining_amount": float(last_salary.remaining_amount) if last_salary else 0,
            "last_paid_date": last_salary.date if last_salary else None,
            "status": last_salary.status if last_salary else "paid",
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
