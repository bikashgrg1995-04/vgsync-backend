# core/utils.py
import re

from django.utils import timezone
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


import math

import numpy as np
from core.models import EmiTracker


def extract_item_no(value):
    """
    Extract actual item_no from Excel cell.
    Handles:
    - BP-123
    - Brake Pad (BP-123)
    - extra spaces
    """
    if not value:
        return ""
    value = str(value).strip()
    match = re.search(r"\((.*?)\)", value)
    if match:
        return match.group(1).strip()
    return value


def make_aware_if_needed(dt):
    if isinstance(dt, datetime) and timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def clean_excel_value(value):
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    if isinstance(value, np.floating) and np.isnan(value):
        return None

    return value

def excel_bool(val):
    if val in [True, 1, "1", "TRUE", "true", "Yes", "yes"]:
        return True
    return False

def recalc_sale_totals(sale):
    total = sum(i.quantity * i.sale_price for i in sale.items.all())
    sale.total_amount = total + (sale.labour_charge or 0)
    sale.remaining_amount = max(
        sale.total_amount - (sale.paid_amount or 0), 0
    )
    sale.save(update_fields=['total_amount', 'remaining_amount'])


def get_credit_days(dt):
    if not dt:
        return 0
    if hasattr(dt, "date"):
        dt = dt.date()
    return (timezone.now().date() - dt).days

def safe_local_date(dt=None):
    """
    Safely return a local DATE from:
    - None
    - datetime.date
    - datetime.datetime
    """

    if dt is None:
        return timezone.localdate()

    # If datetime → convert to local date
    if isinstance(dt, datetime):
        return timezone.localdate(dt)

    # If already a date → return as-is
    if isinstance(dt, date):
        return dt

    raise ValueError(f"Unsupported type for date: {type(dt)}")


# ---------------------------
# BikeSale
# ---------------------------

def safe_sale_date(dt=None):
    """
    Returns a timezone-aware datetime for sale_date or payment_date.
    """
    dt = dt or timezone.now()
    if isinstance(dt, datetime) and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def safe_emi_due_date(dt=None):
    """
    Returns a safe date for EMI due_date
    """
    return safe_local_date(dt)


# ---------------------------
# BikeSale Helpers
# ---------------------------

def get_bike_sale_status(total_amount, paid_amount):
    """
    Determine the sale status for bike sales
    """
    if paid_amount >= total_amount:
        return "Paid"
    elif paid_amount > 0:
        return "Partially Paid"
    return "Pending"


def update_bike_sale_status(sale):
    """
    Updates sale.status based on frontend-calculated paid_amount and net_total
    """
    sale.status = get_bike_sale_status(getattr(sale, 'net_total', 0), getattr(sale, 'paid_amount', 0))
    sale.save(update_fields=['status'])


# ---------------------------
# EMI Helpers
# ---------------------------

def update_emi_status(emi):
    """
    Update EMI tracker status based on due_date and paid_amount
    """
    today = timezone.localdate()
    if getattr(emi, 'paid_amount', 0) >= getattr(emi, 'amount_due', 0):
        emi.status = "Paid"
    elif 0 < getattr(emi, 'paid_amount', 0) < getattr(emi, 'amount_due', 0) and emi.due_date < today:
        emi.status = "Overdue (Partial)"
    else:
        emi.status = "Pending"
    emi.save(update_fields=['status'])


def generate_emi_schedule(sale):
    """
    Create EMI schedule for a BikeSale if sale_type is 'emi' or 'downpayment'.
    EMI due dates are based on sale_date.
    """

    if sale.sale_type not in ['emi', 'downpayment'] or not sale.emi_tenure:
        return

    # Delete existing EMIs
    sale.emi_details.all().delete()

    initial_paid = getattr(sale, 'initial_paid_amount', 0) or 0
    remaining = max(getattr(sale, 'net_total', 0) - initial_paid, 0)
    tenure = sale.emi_tenure

    if tenure <= 0 or remaining <= 0:
        sale.emi_amount = 0
        sale.remaining_amount = remaining
        sale.save(update_fields=['emi_amount', 'remaining_amount'])
        return

    emi_per_month = round(remaining / tenure, 2)

    sale.emi_amount = emi_per_month
    sale.remaining_amount = remaining
    sale.status = get_bike_sale_status(sale.net_total, initial_paid)
    sale.save(update_fields=['emi_amount', 'remaining_amount', 'status'])

    # 🔑 Use sale_date instead of today
    sale_date = sale.sale_date
    if hasattr(sale_date, "date"):
        sale_date = sale_date.date()

    # Create EMI schedule
    for i in range(1, tenure + 1):
        EmiTracker.objects.create(
            sale=sale,
            installment_no=i,
            due_date=sale_date + relativedelta(months=i),
            amount_due=emi_per_month,
            paid_amount=0,
            status="Pending"
        )

        
def update_bike_sale_payment_from_emi(sale):
    """
    Update total paid, remaining, and status based on EMI payments + downpayment
    """
    # Sum of all EMI paid
    total_emi_paid = sale.emi_details.aggregate(total=models.Sum('paid_amount'))['total'] or 0

    # Use initial_paid_amount for downpayment
    initial_paid = getattr(sale, 'initial_paid_amount', 0) or 0

    # Total paid = downpayment + EMI payments
    total_paid = initial_paid + total_emi_paid
    sale.paid_amount = total_paid

    # Correct remaining calculation
    sale.remaining_amount = max(getattr(sale, 'net_total', 0) - total_paid, 0)

    # Update status
    sale.status = get_bike_sale_status(getattr(sale, 'net_total', 0), total_paid)
    sale.save(update_fields=['paid_amount', 'remaining_amount', 'status'])




def get_bike_sale_total_paid(bike_sale):
    if bike_sale.sale_type == "full":
        return float(bike_sale.net_total or 0)
    elif bike_sale.sale_type == "downpayment":
        return float(bike_sale.initial_paid_amount or 0)
    elif bike_sale.sale_type == "emi":
        # get related_name correctly
        rel_name = getattr(bike_sale, "emis", None) or getattr(bike_sale, "emi_tracker_set", None)
        if rel_name:
            emi_sum = rel_name.filter(paid_amount__gt=0).aggregate(total=Sum("paid_amount"))["total"] or 0
            return float(emi_sum)
        return 0
    return 0
