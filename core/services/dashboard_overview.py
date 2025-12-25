from django.utils import timezone
from django.db.models import Sum, F, FloatField
from core.models import (
    Stock, Sale, SaleItem, PurchaseItem, Order, FollowUpDashboard,
    Staff, Expense, SalaryTracker
)

def full_dashboard_service():
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)
    stock_threshold = 5

    # ---------------- STOCK ----------------
    all_stock = Stock.objects.all()
    low_stock_items = all_stock.filter(stock__lt=stock_threshold).values('id','name','model','stock','category__name')

    # ---------------- SALES ----------------
    sales_qs = Sale.objects.all()
    total_sales_amount = sales_qs.aggregate(total=Sum('total_amount'))['total'] or 0
    today_sales_amount = sales_qs.filter(sale_date__date=today).aggregate(total=Sum('total_amount'))['total'] or 0
    monthly_sales_amount = sales_qs.filter(sale_date__date__gte=start_of_month).aggregate(total=Sum('total_amount'))['total'] or 0
    yearly_sales_amount = sales_qs.filter(sale_date__date__gte=start_of_year).aggregate(total=Sum('total_amount'))['total'] or 0
    total_sales_count = sales_qs.count()
    top_sales = SaleItem.objects.values('item__name').annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5]
    low_sales = SaleItem.objects.values('item__name').annotate(total_qty=Sum('quantity')).order_by('total_qty')[:5]

    # ---------------- PURCHASES ----------------
    purchase_qs = PurchaseItem.objects.all()
    total_purchases_amount = purchase_qs.aggregate(total=Sum(F('quantity')*F('price'), output_field=FloatField()))['total'] or 0
    today_purchases_amount = purchase_qs.filter(purchase__date__date=today).aggregate(total=Sum(F('quantity')*F('price'), output_field=FloatField()))['total'] or 0
    monthly_purchases_amount = purchase_qs.filter(purchase__date__date__gte=start_of_month).aggregate(total=Sum(F('quantity')*F('price'), output_field=FloatField()))['total'] or 0
    yearly_purchases_amount = purchase_qs.filter(purchase__date__date__gte=start_of_year).aggregate(total=Sum(F('quantity')*F('price'), output_field=FloatField()))['total'] or 0
    total_purchase_count = purchase_qs.values('purchase').distinct().count()

    # ---------------- ORDERS ----------------
    orders_qs = Order.objects.all()
    total_orders = orders_qs.count()
    pending_amount = sum([o.remaining_amount for o in orders_qs])

    # ---------------- FOLLOWUPS ----------------
    followups_qs = FollowUpDashboard.objects.filter(status='pending').order_by('follow_up_date')
    pending_followups_count = followups_qs.count()
    followup_records = followups_qs.values('id','customer_name','vehicle','follow_up_date','remarks')

    # ---------------- STAFF & SALARY ----------------
    total_staff = Staff.objects.count()
    salary_qs = SalaryTracker.objects.all()
    total_paid_salary = sum([s.paid_amount for s in salary_qs])
    total_salary_amount = sum([s.total_salary for s in salary_qs])
    total_pending_salary = sum([s.remaining_amount for s in salary_qs])

    # Staff salary breakdown
    staff_salary_details = []
    for s in Staff.objects.all():
        trackers = salary_qs.filter(staff=s)
        paid = sum([t.paid_amount for t in trackers])
        pending = sum([t.remaining_amount for t in trackers])
        staff_salary_details.append({
            "staff_id": s.id,
            "staff_name": s.name,
            "paid": paid,
            "pending": pending,
            "trackers": [
                {
                    "date": str(t.date),
                    "total_salary": t.total_salary,
                    "paid_amount": t.paid_amount,
                    "remaining_amount": t.remaining_amount,
                    "status": t.status,
                    "payment_mode": t.payment_mode,
                    "note": t.note
                }
                for t in trackers
            ]
        })

    # ---------------- OTHER EXPENSES ----------------
    other_expenses = Expense.objects.exclude(expense_type='salary')
    total_other_expenses = other_expenses.aggregate(total=Sum('amount'))['total'] or 0

    # ---------------- TOTAL EXPENSE ----------------
    total_expense = total_purchases_amount + total_paid_salary + total_other_expenses

    # ---------------- PROFIT & LOSS ----------------
    def aggregate_income_expense(qs, date_attr, start_date=None):
        """Aggregate list of dicts with date and total amount"""
        result = []
        for obj in qs:
            date_val = getattr(obj, date_attr)
            if isinstance(date_val, timezone.datetime):
                date_val = date_val.date()  # convert to date
            amount = getattr(obj, 'total_amount', None) or getattr(obj, 'amount', 0)
            if not start_date or date_val >= start_date:
                result.append({"date": str(date_val), "amount": amount})
        return result


    def calculate_totals(income_list, expense_list):
        total_income = sum([i['amount'] for i in income_list])
        total_expense = sum([e['amount'] for e in expense_list])
        profit = max(total_income - total_expense, 0)
        loss = max(total_expense - total_income, 0)
        return total_income, total_expense, profit, loss

    # DAILY
    daily_income = aggregate_income_expense(sales_qs, 'sale_date', start_of_month)
    daily_expense = aggregate_income_expense(Expense.objects.all(), 'expense_date', start_of_month)
    daily_total_income, daily_total_expense, daily_profit, daily_loss = calculate_totals(daily_income, daily_expense)
    daily = {
        "income": daily_income,
        "expense": daily_expense,
        "total_income": daily_total_income,
        "total_expense": daily_total_expense,
        "profit": daily_profit,
        "loss": daily_loss
    }

    # MONTHLY
    monthly_income_list = [{"month": start_of_month.month, "amount": monthly_sales_amount}]
    monthly_expense_list = [{"month": start_of_month.month, "amount": total_expense}]
    monthly_total_income, monthly_total_expense, monthly_profit, monthly_loss = calculate_totals(monthly_income_list, monthly_expense_list)
    monthly = {
        "income": monthly_income_list,
        "expense": monthly_expense_list,
        "total_income": monthly_total_income,
        "total_expense": monthly_total_expense,
        "profit": monthly_profit,
        "loss": monthly_loss
    }

    # YEARLY
    yearly_income_list = [{"year": start_of_year.year, "amount": yearly_sales_amount}]
    yearly_expense_list = [{"year": start_of_year.year, "amount": total_expense}]
    yearly_total_income, yearly_total_expense, yearly_profit, yearly_loss = calculate_totals(yearly_income_list, yearly_expense_list)
    yearly = {
        "income": yearly_income_list,
        "expense": yearly_expense_list,
        "total_income": yearly_total_income,
        "total_expense": yearly_total_expense,
        "profit": yearly_profit,
        "loss": yearly_loss
    }

    charts = {
        "profit_loss": {
            "daily": daily,
            "monthly": monthly,
            "yearly": yearly,
        }
    }

    return {
        "period": "monthly",
        "year": today.year,
        "month": today.month,
        "stock": {
            "total_items": all_stock.count(),
            "total_stock": sum([s.stock for s in all_stock]),
            "low_stock_count": low_stock_items.count(),
            "low_stock_items": list(low_stock_items),
            "stock_threshold": stock_threshold,
            "high_sale_stock": list(top_sales),
            "low_sale_stock": list(low_sales)
        },
        "sales": {
            "count": total_sales_count,
            "total_amount": total_sales_amount,
            "today_amount": today_sales_amount,
            "monthly_amount": monthly_sales_amount,
            "yearly_amount": yearly_sales_amount,
            "top_sales": list(top_sales),
            "low_sales": list(low_sales)
        },
        "purchases": {
            "count": total_purchase_count,
            "total_amount": total_purchases_amount,
            "today_amount": today_purchases_amount,
            "monthly_amount": monthly_purchases_amount,
            "yearly_amount": yearly_purchases_amount
        },
        "orders": {
            "total_orders": total_orders,
            "pending_amount": pending_amount
        },
        "followups": {
            "pending_count": pending_followups_count,
            "records": list(followup_records)
        },
        "staff_salary": {
            "total_staff": total_staff,
            "paid": total_paid_salary,
            "pending": total_pending_salary,
            "details": staff_salary_details
        },
        "charts": charts
    }
