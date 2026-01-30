from datetime import timedelta
from django.utils import timezone
from django.db.models import Func, DateField
from django.db.models.functions import TruncDay, TruncMonth, TruncYear

# ------------------ START DATE ------------------
def get_start_date(period: str):
    """
    Returns the start date for a given period.
    """
    today = timezone.now().date()

    if period == "daily":
        return today
    elif period == "weekly":
        return today - timedelta(days=7)
    elif period == "monthly":
        return today - timedelta(days=30)
    elif period == "3months":
        return today - timedelta(days=90)
    elif period == "6months":
        return today - timedelta(days=180)
    elif period == "yearly":
        return today - timedelta(days=365)
    else:
        return today - timedelta(days=30)  # default monthly


# ------------------ TRUNC FUNCTION ------------------
def get_trunc_func(period: str):
    """
    Returns the appropriate trunc function for aggregating dates.
    """
    if period == "daily":
        return TruncDay
    elif period == "weekly":
        return TruncDay  # custom week Sunday → Friday
    elif period in ["monthly", "3months", "6months"]:
        return TruncMonth
    elif period == "yearly":
        return TruncYear
    else:
        return TruncMonth  # default monthly
