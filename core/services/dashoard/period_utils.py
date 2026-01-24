from datetime import timedelta
from django.utils import timezone
from django.db.models.functions import (
    TruncDay, TruncWeek, TruncMonth, TruncYear
)

def get_start_date(period: str):
    today = timezone.now().date()
    return {
        "daily": today,
        "weekly": today - timedelta(days=7),
        "monthly": today - timedelta(days=30),
        "3months": today - timedelta(days=90),
        "6months": today - timedelta(days=180),
        "yearly": today - timedelta(days=365),
    }.get(period, today - timedelta(days=30))


def get_trunc_func(period: str):
    return {
        "daily": TruncDay,
        "weekly": TruncWeek,
        "monthly": TruncMonth,
        "3months": TruncMonth,
        "6months": TruncMonth,
        "yearly": TruncYear,
    }.get(period, TruncMonth)
