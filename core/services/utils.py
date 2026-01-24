# core/utils.py
import re

from django.utils import timezone
from datetime import date, datetime, timedelta


import math
import numpy as np


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