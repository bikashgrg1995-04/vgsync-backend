# core/services/dashboard/dashboard_credit.py

from datetime import timedelta
from django.db.models import Sum, F
from django.core.paginator import Paginator
from core.models import Sale, Purchase, EmiTracker
from core.services.utils import get_credit_days, safe_local_date
from .period_utils import get_start_date


# ---------------- PAGINATION HELPER ----------------
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


# ---------------- MAIN CREDIT DASHBOARD ----------------
def get_credit_summary(period="monthly", page=1, page_size=5):
    today = safe_local_date()
    upcoming_15_days = today + timedelta(days=15)
    start_date = get_start_date(period)

    # =====================================================
    # SALE CREDIT
    # =====================================================
    sale_qs = Sale.objects.filter(
        sale_date__gte=start_date,
        is_paid__in=["not_paid", "partial"],
    )

    sale_data = [{
        "id": s.id,
        "sale_date": safe_local_date(s.sale_date).isoformat() if s.sale_date else None,
        "credit_days": get_credit_days(s.sale_date),
        "customer_name": s.customer_name,
        "contact_no": s.contact_no,
        "net_total": float(s.net_total or 0),
        "paid_amount": float(s.paid_amount or 0),
        "remaining_amount": float(s.remaining_amount or 0),
        "status": s.is_paid,
    } for s in sale_qs]

    sale_data.sort(key=lambda x: x["credit_days"], reverse=True)
    sale_page = Paginator(sale_data, page_size).get_page(page)

    sale_totals = {
        "total_net_amount": float(sale_qs.aggregate(Sum("net_total"))["net_total__sum"] or 0),
        "total_paid_amount": float(sale_qs.aggregate(Sum("paid_amount"))["paid_amount__sum"] or 0),
        "total_credit_amount": float(sale_qs.aggregate(Sum("remaining_amount"))["remaining_amount__sum"] or 0),
        "count": sale_qs.count(),
    }

    # =====================================================
    # PURCHASE CREDIT
    # =====================================================
    purchase_qs = Purchase.objects.filter(
        date__gte=start_date,
        status__in=["pending", "partial"],
    )

    purchase_data = [{
        "id": p.id,
        "purchase_date": safe_local_date(p.date).isoformat() if p.date else None,
        "credit_days": get_credit_days(p.date),
        "supplier_name": p.supplier.name if p.supplier else None,
        "net_total": float(p.net_total or 0),
        "paid_amount": float(p.paid_amount or 0),
        "remaining_amount": float(p.remaining_amount or 0),
        "status": p.status,
    } for p in purchase_qs]

    purchase_data.sort(key=lambda x: x["credit_days"], reverse=True)
    purchase_page = Paginator(purchase_data, page_size).get_page(page)

    purchase_totals = {
        "total_net_amount": float(purchase_qs.aggregate(Sum("net_total"))["net_total__sum"] or 0),
        "total_paid_amount": float(purchase_qs.aggregate(Sum("paid_amount"))["paid_amount__sum"] or 0),
        "total_credit_amount": float(purchase_qs.aggregate(Sum("remaining_amount"))["remaining_amount__sum"] or 0),
        "count": purchase_qs.count(),
    }

    # =====================================================
    # EMI CREDIT (UPCOMING 15 DAYS ONLY)
    # =====================================================
    emi_qs = EmiTracker.objects.filter(
        due_date__gte=today,
        due_date__lte=upcoming_15_days,
        paid_amount__lt=F("amount_due")
    ).select_related("sale").order_by("due_date")

    emi_data = [{
        "id": e.id,
        "sale_id": e.sale.id if e.sale else None,
        "customer_name": e.sale.customer_name if e.sale else None,
        "contact_no": e.sale.contact_no if e.sale else None,
        "installment_no": e.installment_no,
        "due_date": safe_local_date(e.due_date).isoformat(),
        "credit_days": get_credit_days(e.due_date),
        "amount_due": float(e.amount_due or 0),
        "paid_amount": float(e.paid_amount or 0),
        "remaining_amount": float((e.amount_due or 0) - (e.paid_amount or 0)),
        "status": e.status,
    } for e in emi_qs]

    emi_data.sort(key=lambda x: x["credit_days"], reverse=True)
    emi_page = Paginator(emi_data, page_size).get_page(page)

    emi_totals = {
        "total_due_amount": float(emi_qs.aggregate(Sum("amount_due"))["amount_due__sum"] or 0),
        "total_paid_amount": float(emi_qs.aggregate(Sum("paid_amount"))["paid_amount__sum"] or 0),
        "total_remaining_amount": float(
            (emi_qs.aggregate(Sum("amount_due"))["amount_due__sum"] or 0)
            - (emi_qs.aggregate(Sum("paid_amount"))["paid_amount__sum"] or 0)
        ),
        "count": emi_qs.count(),
    }

    # =====================================================
    # FINAL RESPONSE
    # =====================================================
    return {
        "sale": {
            "summary": list(sale_page),
            "totals": sale_totals,
            "pagination": {
                "page": sale_page.number,
                "page_size": page_size,
                "total_pages": sale_page.paginator.num_pages,
                "total_items": sale_page.paginator.count,
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
                "total_pages": purchase_page.paginator.num_pages,
                "total_items": purchase_page.paginator.count,
                "has_next": purchase_page.has_next(),
                "has_previous": purchase_page.has_previous(),
            },
        },
        "emi": {
            "summary": list(emi_page),
            "totals": emi_totals,
            "pagination": {
                "page": emi_page.number,
                "page_size": page_size,
                "total_pages": emi_page.paginator.num_pages,
                "total_items": emi_page.paginator.count,
                "has_next": emi_page.has_next(),
                "has_previous": emi_page.has_previous(),
            },
        },
    }
