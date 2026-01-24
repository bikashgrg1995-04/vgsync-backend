# =================================================
# 👨‍🔧 STAFF SALARIES (Paginated)
# =================================================
from django.core.paginator import Paginator
from core.models import SalaryTracker, Staff


def get_staff_salaries(page=1, page_size=5):
    staff_qs = (
        Staff.objects.filter(is_active=True)
        .order_by("name")
    )

    paginator = Paginator(staff_qs, page_size)
    page_obj = paginator.get_page(page)

    results = []

    for staff in page_obj:
        last_salary = (
            SalaryTracker.objects.filter(staff=staff)
            .order_by("-date")
            .first()
        )

        results.append({
            "staff_id": staff.id,
            "name": staff.name,
            "designation": staff.designation,
            "salary_mode": staff.salary_mode,
            "last_paid_amount": float(last_salary.paid_amount) if last_salary else 0,
            "total_salary": float(last_salary.total_salary) if last_salary else 0,
            "remaining_amount": (
                float(last_salary.remaining_amount)
                if last_salary and last_salary.remaining_amount is not None
                else 0
            ),
            "last_paid_date": last_salary.date if last_salary else None,
            "status": last_salary.status if last_salary else "pending",
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
