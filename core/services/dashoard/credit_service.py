# core/services/dashoard/dashboard_credit.py
from django.db.models import Sum
from django.core.paginator import Paginator
from django.utils import timezone
from core.models import Sale, Purchase
from core.services.utils import get_credit_days
from .period_utils import get_start_date


def paginate_queryset(qs, page, page_size):
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    return {
        "items": list(page_obj),
        "pagination": {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_items": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        },
    }


def get_credit_summary(period="monthly", page=1, page_size=5):
    start_date = get_start_date(period)

    # ---------------- SALE ----------------
    sale_qs = Sale.objects.filter(
        sale_date__date__gte=start_date,
        is_paid__in=["not_paid", "partial"],
    )

    sale_data = []
    for s in sale_qs:
        sale_data.append({
            "id": s.id,
            "sale_date": s.sale_date.date().isoformat() if s.sale_date else None,
            "credit_days": get_credit_days(s.sale_date),
            "customer_name": s.customer_name,
            "contact_no": s.contact_no,
            "net_total": float(s.net_total or 0),
            "paid_amount": float(s.paid_amount or 0),
            "remaining_amount": float(s.remaining_amount or 0),
            "status": s.is_paid,
        })

    sale_data.sort(key=lambda x: x["credit_days"], reverse=True)
    sale_paginator = Paginator(sale_data, page_size)
    sale_page = sale_paginator.get_page(page)

    sale_totals = {
        "total_net_amount": float(sale_qs.aggregate(Sum("net_total"))["net_total__sum"] or 0),
        "total_paid_amount": float(sale_qs.aggregate(Sum("paid_amount"))["paid_amount__sum"] or 0),
        "total_credit_amount": float(sale_qs.aggregate(Sum("remaining_amount"))["remaining_amount__sum"] or 0),
        "count": sale_qs.count(),
    }

    # ---------------- PURCHASE ----------------
    purchase_qs = Purchase.objects.filter(
        date__date__gte=start_date,
        status__in=["pending", "partial"],
    )

    purchase_data = []
    for p in purchase_qs:
        purchase_data.append({
            "id": p.id,
            "purchase_date": p.date.date().isoformat() if p.date else None,
            "credit_days": get_credit_days(p.date),
            "supplier_name": p.supplier.name if p.supplier else None,
            "net_total": float(p.net_total or 0),
            "paid_amount": float(p.paid_amount or 0),
            "remaining_amount": float(p.remaining_amount or 0),
            "status": p.status,
        })

    purchase_data.sort(key=lambda x: x["credit_days"], reverse=True)
    purchase_paginator = Paginator(purchase_data, page_size)
    purchase_page = purchase_paginator.get_page(page)

    purchase_totals = {
        "total_net_amount": float(purchase_qs.aggregate(Sum("net_total"))["net_total__sum"] or 0),
        "total_paid_amount": float(purchase_qs.aggregate(Sum("paid_amount"))["paid_amount__sum"] or 0),
        "total_credit_amount": float(purchase_qs.aggregate(Sum("remaining_amount"))["remaining_amount__sum"] or 0),
        "count": purchase_qs.count(),
    }

    return {
        "sale": {
            "summary": list(sale_page),
            "totals": sale_totals,
            "pagination": {
                "page": sale_page.number,
                "page_size": page_size,
                "total_pages": sale_paginator.num_pages,
                "total_items": sale_paginator.count,
                "has_next": sale_page.has_next(),
                "has_previous": sale_page.has_previous(),
            },
        },
        "purchase": {
            "summary": list(purchase_page),
            "totals": purchase_totals,
            "pagination": {
                "page": purchase_page.number,
                "page_size": page_size,
                "total_pages": purchase_paginator.num_pages,
                "total_items": purchase_paginator.count,
                "has_next": purchase_page.has_next(),
                "has_previous": purchase_page.has_previous(),
            },
        },
    }
