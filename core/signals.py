# core/signals.py
from datetime import timedelta
from django.utils import timezone
from core.services.utils import safe_local_date, safe_sale_date
from django.db.models.signals import (
    post_save, pre_save, pre_delete, post_delete
)
from django.dispatch import receiver
from django.db.models import F, Sum
from django.db import transaction

from .models import (
    Expense, Order, Purchase, SalaryTracker, SalaryTransaction,
    Sale, SaleItem, PurchaseItem, FollowUpDashboard,
    OrderItem, Stock, BikeSale, BikeSaleFollowUp
)
from dateutil.relativedelta import relativedelta

# =====================================================
# CONSTANTS
# =====================================================
FOLLOW_UP_INTERVAL_DAYS = 90
POST_FEEDBACK_DAYS = 3


# =====================================================
# TOTAL HELPERS
# =====================================================
def calculate_purchase_net_total(purchase):
    return (purchase.grand_total or 0) - (purchase.discount_amount or 0)


def calculate_sale_net_total(sale):
    if getattr(sale, 'net_total', None) is not None:
        return sale.net_total
    return (
        sale.items.aggregate(
            total=Sum(F('quantity') * F('price'))
        )['total'] or 0
    )


# =====================================================
# PURCHASE ITEM → STOCK + NET TOTAL
# =====================================================
@receiver(pre_save, sender=PurchaseItem)
def store_old_purchase_qty(sender, instance, **kwargs):
    instance._old_quantity = 0
    if instance.pk:
        instance._old_quantity = (
            PurchaseItem.objects
            .filter(pk=instance.pk)
            .values_list('quantity', flat=True)
            .first()
        ) or 0


@receiver(post_save, sender=PurchaseItem)
@transaction.atomic
def adjust_stock_on_purchase_save(sender, instance, **kwargs):
    purchase = instance.purchase

      # 1️⃣ Update Stock quantity
    diff = instance.quantity - getattr(instance, "_old_quantity", 0)
    if diff:
            Stock.objects.select_for_update().filter(
                pk=instance.item_id
            ).update(stock=F('stock') + diff)

        # 2️⃣ Update purchase price in stock
    stock = Stock.objects.filter(pk=instance.item_id).first()
    if stock:
            stock.purchase_price = instance.price
            # 3️⃣ Auto-calculate sale price = purchase + 13%
            stock.sale_price = round(instance.price * 1.13, 2)
            stock.save(update_fields=['purchase_price', 'sale_price'])

    # 4️⃣ Update Purchase net total
    purchase.net_total = calculate_purchase_net_total(purchase)
    purchase.save(update_fields=['net_total'])


@receiver(pre_delete, sender=PurchaseItem)
@transaction.atomic
def restore_stock_on_purchase_delete(sender, instance, **kwargs):
    purchase = instance.purchase

    Stock.objects.select_for_update().filter(
            pk=instance.item_id
        ).update(stock=F('stock') - instance.quantity)

    latest = (
            PurchaseItem.objects
            .filter(item_id=instance.item_id)
            .exclude(pk=instance.pk)
            .order_by('-id')
            .first()
        )

    Stock.objects.filter(pk=instance.item_id).update(
            purchase_price=latest.price if latest else 0
        )

    purchase.net_total = calculate_purchase_net_total(purchase)
    purchase.save(update_fields=['net_total'])


# =====================================================
# PURCHASE → EXPENSE
# =====================================================
@receiver(post_save, sender=Purchase)
def sync_purchase_expense(sender, instance: Purchase, created, **kwargs):
    """
    Creates or updates an Expense whenever a Purchase is created or updated.
    The Expense amount will reflect the actual paid_amount of the Purchase.
    """
    if instance.paid_amount <= 0:
        # No payment yet, skip creating expense
        return

    expense_data = {
        "title": f"Purchase Payment - {instance.id}",
        "expense_type": "operational",
        "amount": instance.paid_amount,  # actual paid amount
        "expense_date": instance.date,
        "payment_mode": instance.paid_from if instance.paid_from in ['cash', 'online'] else 'cash',
        "spent_by": instance.created_by,
        "reference_type": "Purchase",
        "reference_id": instance.id,
        "note": f"Purchase from {instance.supplier.name}, total: {instance.grand_total}, paid: {instance.paid_amount}"
    }

    # Check if Expense already exists for this purchase
    expense, _ = Expense.objects.update_or_create(
        reference_type="Purchase",
        reference_id=instance.id,
        defaults=expense_data
    )


@receiver(pre_delete, sender=Purchase)
def delete_purchase_expense(sender, instance, **kwargs):
    Expense.objects.filter(
        reference_type='Purchase',
        reference_id=instance.id
    ).delete()


# =====================================================
# SALE ITEM → STOCK
# =====================================================
@receiver(pre_save, sender=SaleItem)
def store_old_sale_qty(sender, instance, **kwargs):
    instance._old_quantity = 0
    if instance.pk:
        instance._old_quantity = (
            SaleItem.objects
            .filter(pk=instance.pk)
            .values_list('quantity', flat=True)
            .first()
        ) or 0


@receiver(post_save, sender=SaleItem)
@transaction.atomic
def adjust_stock_on_sale_save(sender, instance, **kwargs):
    if not instance.sale.is_migrated:
        diff = instance.quantity - instance._old_quantity
        if diff:
            Stock.objects.select_for_update().filter(
                pk=instance.item_id
            ).update(stock=F('stock') - diff)


@receiver(pre_delete, sender=SaleItem)
@transaction.atomic
def restore_stock_on_sale_delete(sender, instance, **kwargs):
    if not instance.sale.is_migrated:
        Stock.objects.select_for_update().filter(
            pk=instance.item_id
        ).update(stock=F('stock') + instance.quantity)


# =====================================================
# SALE → FOLLOW UP DASHBOARD
# =====================================================
@receiver(post_save, sender=Sale)
@transaction.atomic
def manage_followup_dashboard(sender, instance, **kwargs):
    if not instance.is_servicing or not instance.delivery_date:
        FollowUpDashboard.objects.filter(
            sale=instance
        ).exclude(status="terminated").delete()
        return

    follow_up_date = instance.delivery_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)
    post_feedback_date = instance.delivery_date + timedelta(days=POST_FEEDBACK_DAYS)

    followup, _ = FollowUpDashboard.objects.get_or_create(
        sale=instance,
        defaults={
            "customer_name": instance.customer_name or "Unknown",
            "contact_no": instance.contact_no,
            "vehicle": instance.vehicle_model or instance.bike_registration_no,
            "delivery_date": instance.delivery_date,
            "post_service_feedback_date": post_feedback_date,
            "follow_up_date": follow_up_date,
            "assigned_to": instance.handled_by,
            "remarks": "Auto-created servicing follow-up",
        },
    )

    if followup.status != "terminated":
        followup.customer_name = instance.customer_name or "Unknown"
        followup.contact_no = instance.contact_no
        followup.vehicle = instance.vehicle_model or instance.bike_registration_no
        followup.delivery_date = instance.delivery_date
        followup.post_service_feedback_date = post_feedback_date
        followup.follow_up_date = follow_up_date
        followup.assigned_to = instance.handled_by
        followup.save()


@receiver(pre_delete, sender=Sale)
def delete_followup_on_sale_delete(sender, instance, **kwargs):
    FollowUpDashboard.objects.filter(sale=instance).delete()


# =====================================================
# ORDER ITEM → ORDER TOTALS
# =====================================================
@receiver(post_save, sender=OrderItem)
@receiver(post_delete, sender=OrderItem)
def update_order_totals(sender, instance, **kwargs):
    if hasattr(instance.order, 'update_totals'):
        instance.order.update_totals()


# =====================================================
# SALARY TRANSACTION → SALARY TRACKER + EXPENSE
# =====================================================
@receiver(post_save, sender=SalaryTransaction)
@transaction.atomic
def handle_salary_transaction_save(sender, instance, created, **kwargs):
    expense_date = safe_local_date(instance.payment_date)

    # ---- Expense ----
    expense, created_expense = Expense.objects.get_or_create(
        reference_type='salary_transaction',
        reference_id=instance.id,
        defaults={
            "title": f"{instance.transaction_type.title()} - {instance.staff.name}",
            "expense_type": "salary",
            "amount": instance.amount,
            "expense_date": expense_date,
            "payment_mode": instance.payment_mode,
            "spent_by": None,
        }
    )
    if not created_expense:
        Expense.objects.filter(pk=expense.pk).update(
            amount=instance.amount,
            expense_date=expense_date,
            payment_mode=instance.payment_mode,
            title=f"{instance.transaction_type.title()} - {instance.staff.name}"
        )

    # ---- Salary Tracker ----
    tracker = instance.salary_tracker
    if not tracker:
        tracker, _ = SalaryTracker.objects.get_or_create(
            staff=instance.staff,
            defaults={'date': expense_date}
        )
        # Update instance without triggering post_save again
        SalaryTransaction.objects.filter(pk=instance.pk).update(salary_tracker=tracker)

    # At this point, tracker is guaranteed to exist
    if tracker:
        total_paid = SalaryTransaction.objects.filter(salary_tracker=tracker).aggregate(total=Sum('amount'))['total'] or 0
        tracker.paid_amount = total_paid

        if tracker.staff.salary_mode == 'monthly':
            if total_paid >= tracker.total_salary:
                tracker.status = 'paid'
            elif total_paid > 0:
                tracker.status = 'partial'
            else:
                tracker.status = 'pending'
        else:
            tracker.status = 'paid' if total_paid > 0 else 'pending'

        tracker.save(update_fields=['paid_amount', 'status'])

        # ---------------- Create next month tracker if fully paid ----------------
        if tracker.staff.salary_mode == 'monthly' and tracker.status == 'paid':
            next_month_date = (tracker.date or timezone.now()) + relativedelta(months=1)

            # Check if next month tracker already exists
            next_tracker, created_next = SalaryTracker.objects.get_or_create(
                staff=tracker.staff,
                date__year=next_month_date.year,
                date__month=next_month_date.month,
                defaults={
                    "date": next_month_date,
                    "total_salary": tracker.total_salary,
                    "paid_amount": 0,
                    "status": "pending"
                }
            )

@receiver(pre_delete, sender=SalaryTransaction)
@transaction.atomic
def handle_salary_transaction_delete(sender, instance, **kwargs):
    Expense.objects.filter(
        reference_type='salary_transaction',
        reference_id=instance.id
    ).delete()

    tracker = instance.salary_tracker
    if not tracker:
        return

    total_paid = (
        SalaryTransaction.objects
        .filter(salary_tracker=tracker)
        .exclude(pk=instance.pk)
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    tracker.paid_amount = total_paid
    tracker.status = 'paid' if total_paid > 0 else 'pending'
    tracker.save(update_fields=['paid_amount', 'status'])

@receiver(post_save, sender=BikeSale)
def bike_sale_followup(sender, instance, created, **kwargs):

    base_date = instance.sale_date or timezone.now()

    if created:
        # 🔹 Create followup only once
        BikeSaleFollowUp.objects.create(
            bike_sale=instance,
            customer_name=instance.customer_name or "Unknown",
            contact_no=instance.contact_no,
            vehicle=instance.vehicle_model or instance.bike_registration_no,
            delivery_date=base_date,
            post_service_feedback_date=base_date + timedelta(days=POST_FEEDBACK_DAYS),
            follow_up_date=base_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS),
            remarks="Auto-created bike sale follow-up",
            status="pending"
        )
    else:
        # 🔹 Update existing followup (but NOT status)
        BikeSaleFollowUp.objects.filter(bike_sale=instance).update(
            customer_name=instance.customer_name or "Unknown",
            contact_no=instance.contact_no,
            vehicle=instance.vehicle_model or instance.bike_registration_no,
            delivery_date=base_date,
            post_service_feedback_date=base_date + timedelta(days=POST_FEEDBACK_DAYS),
            follow_up_date=base_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS),
        )


@receiver(pre_delete, sender=BikeSale)
def delete_bike_sale_followup(sender, instance, **kwargs):
    BikeSaleFollowUp.objects.filter(bike_sale=instance).delete()
