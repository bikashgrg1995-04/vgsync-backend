from datetime import timedelta
from django.utils import timezone
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.db.models import F, Sum
from django.db import transaction

from .models import (
    Expense, Order, Purchase, SalaryTracker, SalaryTransaction,
    Sale, SaleItem, PurchaseItem, FollowUpDashboard,
    OrderItem, Stock
)

FOLLOW_UP_INTERVAL_DAYS = 30
POST_FEEDBACK_DAYS = 3

# =====================================================
# HELPERS
# =====================================================
def get_purchase_total(purchase):
    return purchase.items.aggregate(
        total=Sum(F('quantity') * F('price'))
    )['total'] or 0

# =====================================================
# PURCHASE ITEM → STOCK
# =====================================================
@receiver(pre_save, sender=PurchaseItem)
def store_old_purchase_qty(sender, instance, **kwargs):
    if instance.pk:
        instance._old_quantity = (
            PurchaseItem.objects
            .filter(pk=instance.pk)
            .values_list('quantity', flat=True)
            .first()
        ) or 0
    else:
        instance._old_quantity = 0

@receiver(post_save, sender=PurchaseItem)
@transaction.atomic
def adjust_stock_on_purchase_save(sender, instance, **kwargs):
    # Stock adjust only if NOT migrated
    if not instance.purchase.is_migrated:
        diff = instance.quantity - getattr(instance, '_old_quantity', 0)
        if diff != 0:
            Stock.objects.select_for_update().filter(pk=instance.item_id).update(
                stock=F('stock') + diff
            )
        Stock.objects.filter(pk=instance.item_id).update(purchase_price=instance.price)

@receiver(pre_delete, sender=PurchaseItem)
@transaction.atomic
def restore_stock_on_purchase_delete(sender, instance, **kwargs):
    # Stock adjust only if NOT migrated
    if not instance.purchase.is_migrated:
        Stock.objects.select_for_update().filter(pk=instance.item_id).update(
            stock=F('stock') - instance.quantity
        )
        latest_purchase_item = PurchaseItem.objects.filter(item_id=instance.item_id).exclude(pk=instance.pk).order_by('-id').first()
        new_price = latest_purchase_item.price if latest_purchase_item else 0
        Stock.objects.filter(pk=instance.item_id).update(purchase_price=new_price)

# =====================================================
# PURCHASE → EXPENSE
# =====================================================
@receiver(post_save, sender=PurchaseItem)
@receiver(post_delete, sender=PurchaseItem)
@transaction.atomic
def sync_purchase_expense(sender, instance, **kwargs):
    purchase = instance.purchase

    # Use net_total if available
    total_amount = getattr(purchase, '_expense_amount_override', None)
    if total_amount is None:
        total_amount = purchase.net_total or get_purchase_total(purchase)

    expense = Expense.objects.filter(
        reference_type='purchase',
        reference_id=purchase.id
    ).first()

    # No items → delete expense
    if total_amount <= 0:
        if expense:
            expense.delete()
        return

    # Create or update expense (even if migrated)
    if not expense:
        Expense.objects.create(
            reference_type='purchase',
            reference_id=purchase.id,
            title=f"Purchase - {purchase.supplier.name}",
            expense_type='operational',
            amount=total_amount,
            expense_date=purchase.date.date() if purchase.date else timezone.now().date(),
            payment_mode='cash',
            spent_by=None,
            note=f"Auto expense for Purchase #{purchase.id}"
        )
    else:
        expense.amount = total_amount
        expense.title = f"Purchase - {purchase.supplier.name}"
        expense.save(update_fields=['amount', 'title'])


@receiver(post_delete, sender=PurchaseItem)
def delete_purchase_expense(sender, instance, **kwargs):
    Expense.objects.filter(reference_type='purchase', reference_id=instance.purchase.id).delete()


@receiver(post_delete, sender=Purchase)
def delete_purchase_expense_on_purchase_delete(sender, instance, **kwargs):
    Expense.objects.filter(reference_type='purchase', reference_id=instance.id).delete()


# =====================================================
# SALE ITEM → STOCK
# =====================================================
@receiver(pre_save, sender=SaleItem)
def store_old_sale_qty(sender, instance, **kwargs):
    if instance.pk:
        instance._old_quantity = (
            SaleItem.objects.filter(pk=instance.pk).values_list('quantity', flat=True).first()
        ) or 0
    else:
        instance._old_quantity = 0

@receiver(post_save, sender=SaleItem)
@transaction.atomic
def adjust_stock_on_sale_save(sender, instance, **kwargs):
    # Stock adjust only if NOT migrated
    if not instance.sale.is_migrated:
        diff = instance.quantity - getattr(instance, '_old_quantity', 0)
        if diff != 0:
            Stock.objects.select_for_update().filter(pk=instance.item_id).update(stock=F('stock') - diff)

@receiver(pre_delete, sender=SaleItem)
@transaction.atomic
def restore_stock_on_sale_delete(sender, instance, **kwargs):
    if not instance.sale.is_migrated:
        Stock.objects.select_for_update().filter(pk=instance.item_id).update(stock=F('stock') + instance.quantity)

# =====================================================
# SALE → FOLLOW UP DASHBOARD
# =====================================================
@receiver(post_save, sender=Sale)
@transaction.atomic
def manage_followup_dashboard(sender, instance, **kwargs):
    if not instance.is_servicing or not instance.delivery_date:
        FollowUpDashboard.objects.filter(sale=instance).exclude(status="terminated").delete()
        return

    follow_up_date = instance.delivery_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)
    post_feedback_date = instance.delivery_date + timedelta(days=POST_FEEDBACK_DAYS)

    # Create/update followup even if migrated
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
def handle_salary_transaction_save(sender, instance, **kwargs):
    # ---------------- EXPENSE ----------------
    expense, created = Expense.objects.get_or_create(
        reference_type='salary_transaction',
        reference_id=instance.id,
        defaults={
            "title": f"{instance.transaction_type.title()} - {instance.staff.name}",
            "expense_type": "salary",
            "amount": instance.amount,
            "expense_date": instance.payment_date,
            "payment_mode": instance.payment_mode,
            "spent_by": None,
        }
    )

    if not created:
        expense.amount = instance.amount
        expense.expense_date = instance.payment_date
        expense.payment_mode = instance.payment_mode
        expense.title = f"{instance.transaction_type.title()} - {instance.staff.name}"
        expense.save(update_fields=['amount', 'expense_date', 'payment_mode', 'title'])

    # ---------------- SALARY TRACKER ----------------
    tracker = instance.salary_tracker
    if not tracker:
        tracker, _ = SalaryTracker.objects.get_or_create(
            staff=instance.staff,
            defaults={'date': instance.payment_date}
        )
        instance.salary_tracker = tracker
        instance.save(update_fields=['salary_tracker'])

    total_paid = SalaryTransaction.objects.filter(salary_tracker=tracker).aggregate(total=Sum('amount'))['total'] or 0
    tracker.paid_amount = total_paid
    if tracker.staff.salary_mode == 'monthly':
        if tracker.total_salary == 0 or tracker.paid_amount >= tracker.total_salary:
            tracker.status = 'paid'
        elif tracker.paid_amount > 0:
            tracker.status = 'partial'
        else:
            tracker.status = 'pending'
    else:
        tracker.status = 'paid' if tracker.paid_amount > 0 else 'pending'

    tracker.save(update_fields=['paid_amount', 'status'])

@receiver(pre_delete, sender=SalaryTransaction)
@transaction.atomic
def handle_salary_transaction_delete(sender, instance, **kwargs):
    Expense.objects.filter(reference_type='salary_transaction', reference_id=instance.id).delete()
    tracker = instance.salary_tracker
    if not tracker:
        return
    total_paid = SalaryTransaction.objects.filter(salary_tracker=tracker).exclude(pk=instance.pk).aggregate(total=Sum('amount'))['total'] or 0
    tracker.paid_amount = total_paid
    tracker.status = 'paid' if total_paid > 0 else 'pending'
    tracker.save(update_fields=['paid_amount', 'status'])
