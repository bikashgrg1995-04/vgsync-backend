from datetime import timedelta
from django.db.models import Sum
from core.models import Sale, BikeSale, EmiTracker, Expense
from .period_utils import get_start_date
from core.services.utils import safe_local_date, safe_sale_date, get_bike_sale_total_paid

from dateutil.relativedelta import relativedelta

# ------------------ WEEK / MONTH KEYS ------------------
def get_week_key(date_obj):
    day = date_obj.day
    week_num = (day - 1) // 7 + 1
    return f"{date_obj.year}-W{week_num}"

def get_month_key(date_obj):
    return date_obj.strftime("%Y-%m")

def get_period_key(date_obj, period):
    if period in ["3months", "6months"]:
        months_span = 3 if period == "3months" else 6
        month_start = ((date_obj.month - 1) // months_span) * months_span + 1
        return f"{date_obj.year}-{month_start:02d}"
    elif period == "yearly":
        return str(date_obj.year)
    else:
        return date_obj.strftime("%Y-%m-%d")

def get_period_label(key, period):
    if period in ["3months", "6months"]:
        year, month_start = key.split("-")
        month_start = int(month_start)
        if period == "3months":
            labels = {1: "Jan-Mar", 4: "Apr-Jun", 7: "Jul-Sep", 10: "Oct-Dec"}
        else:
            labels = {1: "Jan-Jun", 7: "Jul-Dec"}
        return f"{year} {labels.get(month_start, '')}"
    # For daily keys, remove leading zero from day (01 → 1)
    if period == "daily":
        parts = key.split("-")
        return f"{parts[0]}-{parts[1]}-{int(parts[2])}"
    return key

# ------------------ DASHBOARD CHARTS ------------------
def get_dashboard_charts(period="monthly"):
    # Make start_date timezone-aware for DateTimeFields
    start_date = safe_sale_date(get_start_date(period))

    def get_key(date_obj):
        if period == "daily":
            return date_obj.strftime("%Y-%m-%d")
        elif period == "weekly":
            return get_week_key(date_obj)
        elif period == "monthly":
            return get_month_key(date_obj)
        elif period in ["3months", "6months"]:
            return get_period_key(date_obj, period)
        elif period == "yearly":
            return str(date_obj.year)

    # ---------------- FETCH DATA ----------------
    sale_qs = Sale.objects.filter(sale_date__gte=start_date)\
        .values("sale_date")\
        .annotate(amount=Sum("paid_amount"))\
        .order_by("sale_date")

    bike_qs = BikeSale.objects.filter(sale_date__gte=start_date)\
        .values("id", "sale_date", "sale_type", "net_total", "initial_paid_amount")\
        .annotate(paid_amount=Sum("paid_amount"))\
        .order_by("sale_date")


    emi_qs = EmiTracker.objects.filter(payment_date__gte=start_date, paid_amount__gt=0)\
        .values("payment_date")\
        .annotate(amount=Sum("paid_amount"))\
        .order_by("payment_date")

    expense_qs = Expense.objects.filter(expense_date__gte=safe_local_date(start_date))\
        .values("expense_date", "expense_type")\
        .annotate(amount=Sum("amount"))\
        .order_by("expense_date")

    # ---------------- AGGREGATE DATA ----------------
    sale_income = {}
    for row in sale_qs:
        date_obj = safe_local_date(row["sale_date"])
        key = get_key(date_obj)
        sale_income.setdefault(key, 0)
        sale_income[key] += float(row["amount"] or 0)

    bike_income = {}
    for row in bike_qs:
        date_obj = safe_local_date(row["sale_date"])
        key = get_key(date_obj)

        # Fetch the BikeSale instance
        bike_sale = BikeSale.objects.get(id=row["id"])
        amt = get_bike_sale_total_paid(bike_sale)

        bike_income.setdefault(key, 0)
        bike_income[key] += amt


    # Include EMI payments
    for row in emi_qs:
        date_obj = safe_local_date(row["payment_date"])
        key = get_key(date_obj)
        bike_income.setdefault(key, 0)
        bike_income[key] += float(row["amount"] or 0)

    # Expenses
    expenses = {}
    expense_types = {}
    for row in expense_qs:
        date_obj = safe_local_date(row["expense_date"])
        key = get_key(date_obj)
        expenses.setdefault(key, 0)
        expenses[key] += float(row["amount"] or 0)
        expense_types.setdefault(key, [])
        expense_types[key].append({"type": row["expense_type"], "amount": float(row["amount"] or 0)})

    # ---------------- FINAL SERIES ----------------
    daily_sale = []
    daily_bike = []
    daily_expense = []
    daily_profit_loss = []

    all_keys = sorted(set(list(sale_income.keys()) + list(bike_income.keys()) + list(expenses.keys())))

    for key in all_keys:
        sale_amount = sale_income.get(key, 0)
        bike_amount = bike_income.get(key, 0)
        expense_amount = expenses.get(key, 0)
        label = get_period_label(key, period)
        daily_sale.append({"period": label, "amount": sale_amount})
        daily_bike.append({"period": label, "amount": bike_amount})
        daily_expense.append({"period": label, "amount": expense_amount, "types": expense_types.get(key, [])})
        daily_profit_loss.append({"period": label, "amount": sale_amount + bike_amount - expense_amount})

    return {
        "sale_income": daily_sale,
        "bike_income": daily_bike,
        "expense": daily_expense,
        "profit_loss": daily_profit_loss
    }
