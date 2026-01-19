from django.utils import timezone
from django.db.models import Sum, F, ExpressionWrapper, FloatField
from core.models import Stock, Sale, SaleItem, Order, FollowUpDashboard, Staff, Expense, SalaryTracker


def full_dashboard_service(period="monthly"):
    """
    period: 'daily', 'monthly', 'yearly'
    """
    today = timezone.now().date()

    if period == "daily":
        start_date = today
    elif period == "monthly":
        start_date = today.replace(day=1)
    elif period == "yearly":
        start_date = today.replace(month=1, day=1)
    else:
        raise ValueError("Invalid period. Use 'daily', 'monthly', or 'yearly'.")

    stock_threshold = 5

    # ---------------- STOCK ----------------
    all_stock = Stock.objects.all()
    low_stock_items = all_stock.filter(stock__lt=stock_threshold).values('id', 'name', 'model', 'stock', 'category__name')

    # ---------------- SALES (INCOME) ----------------
    sales_qs = Sale.objects.filter(sale_date__date__gte=start_date)
    total_sales_amount = sales_qs.aggregate(total=Sum('net_total'))['total'] or 0
    total_sales_count = sales_qs.count()
    today_sales_amount = Sale.objects.filter(sale_date__date=today).aggregate(total=Sum('net_total'))['total'] or 0

    top_sales = SaleItem.objects.values('item__name').annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5]
    low_sales = SaleItem.objects.values('item__name').annotate(total_qty=Sum('quantity')).order_by('total_qty')[:5]

    # ---------------- ORDERS ----------------
    orders_qs = Order.objects.all()
    total_orders = orders_qs.count()
    pending_amount_expr = ExpressionWrapper(F('total_amount') - F('advance'), output_field=FloatField())
    pending_amount = orders_qs.aggregate(total_pending=Sum(pending_amount_expr))['total_pending'] or 0

    orders_list = []
    for order in orders_qs:
        orders_list.append({
            "id": order.id,
            "customer_name": order.customer_name,
            "vehicle_model": order.vehicle_model,
            "date": order.order_date.isoformat(),
            "total_amount": float(order.total_amount),
            "advance": float(order.advance),
            "pending_amount": float(order.remaining_amount),
        })

    # ---------------- FOLLOWUPS ----------------
    followups_qs = FollowUpDashboard.objects.filter(
        status='pending',
        follow_up_date__gte=today
    ).exclude(status='terminated').order_by('follow_up_date')

    pending_followups_count = followups_qs.count()
    nearest_followup = followups_qs.first()
    followup_records = []
    for f in followups_qs:
        followup_records.append({
            "id": f.id,
            "customer_name": f.customer_name,
            "vehicle": f.vehicle,
            "follow_up_date": f.follow_up_date.isoformat(),
            "status": f.status,
            "status_color": "orange" if f.status.lower() == "pending" else "green",
            "remarks": f.remarks or "",
            "is_nearest": f.id == nearest_followup.id if nearest_followup else False
        })

    # ---------------- STAFF & SALARY ----------------
    total_staff = Staff.objects.count()
    salary_qs = SalaryTracker.objects.all()
    total_paid_salary = salary_qs.aggregate(total_paid=Sum('paid_amount'))['total_paid'] or 0
    pending_expr = ExpressionWrapper(F('total_salary') - F('paid_amount'), output_field=FloatField())
    total_pending_salary = salary_qs.aggregate(total_pending=Sum(pending_expr))['total_pending'] or 0

    staff_salary_details = []
    for staff in Staff.objects.all():
        trackers = salary_qs.filter(staff=staff)
        paid = trackers.aggregate(total_paid=Sum('paid_amount'))['total_paid'] or 0
        pending = trackers.aggregate(total_pending=Sum(pending_expr))['total_pending'] or 0
        staff_salary_details.append({
            "staff_id": staff.id,
            "staff_name": staff.name,
            "paid": float(paid),
            "pending": float(pending),
            "payment_status": "Pending" if pending > 0 else "Paid"
        })

    # ---------------- EXPENSE ----------------
    expense_qs = Expense.objects.filter(created_at__date__gte=start_date)


    def category_total(qs, category):
        if category in ["salary", "operational"]:
            return float(qs.filter(expense_type=category).aggregate(total=Sum('amount'))['total'] or 0)
        return float(qs.exclude(expense_type__in=["salary", "operational"]).aggregate(total=Sum('amount'))['total'] or 0)

    expense_categories = [
        {"category": "Salary", "amount": category_total(expense_qs, "salary")},
        {"category": "Operational", "amount": category_total(expense_qs, "operational")},
        {"category": "Others", "amount": category_total(expense_qs, "others")},
    ]
    total_expense = sum(c["amount"] for c in expense_categories)

    # ---------------- PROFIT & LOSS ----------------
    profit_loss = {
        "income": float(total_sales_amount),
        "expense": float(total_expense),
        "profit": float(max(total_sales_amount - total_expense, 0)),
        "loss": float(max(total_expense - total_sales_amount, 0)),
    }

    # ---------------- FINAL RESPONSE ----------------
    return {
        "period": period,
        "year": today.year,
        "month": today.month,
        "stock": {
            "total_items": all_stock.count(),
            "total_stock": sum(s.stock for s in all_stock),
            "low_stock_count": low_stock_items.count(),
            "low_stock_items": list(low_stock_items),
            "stock_threshold": stock_threshold,
            "high_sale_stock": list(top_sales),
            "low_sale_stock": list(low_sales),
        },
        "sale": {
            "count": total_sales_count,
            "total_amount": float(total_sales_amount),
            "today_amount": float(today_sales_amount),
        },
        "expense": {
            "total_amount": float(total_expense),
            "categories": expense_categories,
        },
        "profit_loss": profit_loss,
        "orders": {
            "total_orders": total_orders,
            "pending_amount": float(pending_amount),
            "records": orders_list,
        },
        "followups": {
            "pending_count": pending_followups_count,
            "records": followup_records,
        },
        "staff_salary": {
            "total_staff": total_staff,
            "paid": float(total_paid_salary),
            "pending": float(total_pending_salary),
            "details": staff_salary_details,
        }
    }
