from django.db.models import Sum
from core.models import Sale, Expense
from .period_utils import get_start_date, get_trunc_func


def get_dashboard_charts(period="monthly"):
    start_date = get_start_date(period)
    trunc_func = get_trunc_func(period)

    # ================= INCOME =================
    income_qs = (
        Sale.objects.filter(sale_date__date__gte=start_date)
        .annotate(date=trunc_func("sale_date"))
        .values("date")
        .annotate(amount=Sum("net_total"))
        .order_by("date")
    )

    income_chart = [
        {
            "date": row["date"],
            "amount": float(row["amount"] or 0),
        }
        for row in income_qs
    ]

    # ================= EXPENSE =================
    expense_qs = (
        Expense.objects.filter(expense_date__gte=start_date)
        .annotate(date=trunc_func("expense_date"))
        .values("date", "expense_type")
        .annotate(amount=Sum("amount"))
        .order_by("date")
    )

    expense_chart = [
        {
            "date": row["date"],
            "type": row["expense_type"],
            "amount": float(row["amount"] or 0),
        }
        for row in expense_qs
    ]

    # ================= PROFIT / LOSS =================
    expense_by_date = {}
    for e in expense_chart:
        expense_by_date[e["date"]] = (
            expense_by_date.get(e["date"], 0) + e["amount"]
        )

    profit_loss_chart = [
        {
            "date": inc["date"],
            "amount": inc["amount"] - expense_by_date.get(inc["date"], 0),
        }
        for inc in income_chart
    ]

    return {
        "income": income_chart,
        "expense": expense_chart,
        "profit_loss": profit_loss_chart,
    }
