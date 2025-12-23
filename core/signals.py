from datetime import timedelta, timezone
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.db.models import F
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum
from .models import Category, Expense, Order, Purchase, SalaryTracker, SalaryTransaction, Sale, SaleItem, PurchaseItem, FollowUpDashboard, OrderItem, Stock, Supplier

FOLLOW_UP_INTERVAL_DAYS = 30
POST_FEEDBACK_DAYS = 3

# ---------------- PURCHASE ITEM → STOCK ----------------
@receiver(pre_save, sender=PurchaseItem)
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
    diff = instance.quantity - getattr(instance, '_old_quantity', 0)

    if diff == 0:
        return

    Stock.objects.select_for_update().filter(
        pk=instance.item_id
    ).update(stock=F('stock') + diff)


@receiver(pre_delete, sender=PurchaseItem)
@transaction.atomic
def reduce_stock_on_purchase_delete(sender, instance, **kwargs):
    Stock.objects.select_for_update().filter(
        pk=instance.item_id
    ).update(stock=F('stock') - instance.quantity)


# ---------------- SALE ITEM → STOCK ----------------
@receiver(pre_save, sender=SaleItem)
def store_old_sale_qty(sender, instance, **kwargs):
    if instance.pk:
        instance._old_quantity = (
            SaleItem.objects
            .filter(pk=instance.pk)
            .values_list('quantity', flat=True)
            .first()
        ) or 0
    else:
        instance._old_quantity = 0

@receiver(post_save, sender=SaleItem)
@transaction.atomic
def adjust_stock_on_sale_save(sender, instance, created, **kwargs):
        diff = instance.quantity - getattr(instance, '_old_quantity', 0)

        if diff == 0:
            return

        Stock.objects.select_for_update().filter(
            pk=instance.item_id
        ).update(stock=F('stock') - diff)

@receiver(pre_delete, sender=SaleItem)
@transaction.atomic
def restore_stock_on_sale_delete(sender, instance, **kwargs):
    Stock.objects.select_for_update().filter(
        pk=instance.item_id
    ).update(stock=F('stock') + instance.quantity)

# ---------------- SALE → FOLLOW-UP DASHBOARD ----------------
@receiver(post_save, sender=Sale)
@transaction.atomic
def manage_followup_dashboard(sender, instance, **kwargs):
    """
    CREATE or UPDATE follow-up for servicing sales.
    Do not update terminated follow-ups.
    Delete follow-up if sale is not servicing (excluding terminated).
    """
    if not instance.is_servicing or not instance.delivery_date:
        FollowUpDashboard.objects.filter(sale=instance).exclude(status="terminated").delete()
        return

    follow_up_date = instance.delivery_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)
    post_feedback_date = instance.delivery_date + timedelta(days=POST_FEEDBACK_DAYS)

    followup, created = FollowUpDashboard.objects.get_or_create(
        sale=instance,
        defaults={
            "customer_name": instance.customer_name or "Unknown",
            "contact_no": instance.contact_no,
            "vehicle": instance.bike_registration_no,
            "delivery_date": instance.delivery_date,
            "post_service_feedback_date": post_feedback_date,
            "follow_up_date": follow_up_date,
            "assigned_to": instance.handled_by,
            "remarks": "Auto-created servicing follow-up",
        },
    )

    if followup.status == "terminated":
        return

    # update fields for non-terminated follow-ups
    followup.customer_name = instance.customer_name or "Unknown"
    followup.contact_no = instance.contact_no
    followup.vehicle = instance.bike_registration_no
    followup.delivery_date = instance.delivery_date
    followup.post_service_feedback_date = post_feedback_date
    followup.follow_up_date = follow_up_date
    followup.assigned_to = instance.handled_by
    followup.save()


@receiver(pre_delete, sender=Sale)
def delete_followup_on_sale_delete(sender, instance, **kwargs):
    FollowUpDashboard.objects.filter(sale=instance).delete()

# ---------------- ORDER ITEM → UPDATE ORDER TOTALS ----------------
@receiver(post_save, sender=OrderItem)
def update_order_totals_on_save(sender, instance, **kwargs):
    if hasattr(instance.order, 'update_totals'):
        instance.order.update_totals()

@receiver(post_delete, sender=OrderItem)
def update_order_totals_on_delete(sender, instance, **kwargs):
    if hasattr(instance.order, 'update_totals'):
        instance.order.update_totals()


# ---------------- SalaryTransaction → Expense ----------------
@receiver(post_save, sender=SalaryTransaction)
@transaction.atomic
def handle_salary_transaction_save(sender, instance, created, **kwargs):
    # ensure expense_date is a date
    expense_date = instance.payment_date if isinstance(instance.payment_date, timezone.datetime) else instance.payment_date
    if isinstance(expense_date, timezone.datetime):
        expense_date = expense_date.date()

    if created and instance.transaction_type != 'adjustment':
        Expense.objects.create(
            title=f"{instance.transaction_type.title()} - {instance.staff.name}",
            expense_type='operational',
            amount=instance.amount,
            expense_date=expense_date,
            payment_mode=instance.payment_mode,
            reference_type='salary_transaction',
            reference_id=instance.id,
            spent_by=None
        )

    tracker = instance.staff.salarytracker_set.filter(date=expense_date).first()
    if tracker:
        total_paid = SalaryTransaction.objects.filter(
            staff=instance.staff,
            salary_tracker=tracker
        ).aggregate(total=Sum('amount'))['total'] or 0
        tracker.paid_amount = total_paid
        tracker.status = 'paid' if tracker.paid_amount >= tracker.total_salary else 'partial' if tracker.paid_amount > 0 else 'pending'
        tracker.save(update_fields=['paid_amount', 'status'])

@receiver(pre_delete, sender=SalaryTransaction)
@transaction.atomic
def handle_salary_transaction_delete(sender, instance, **kwargs):
    """
    When a SalaryTransaction is deleted:
    - Update SalaryTracker
    - Delete related Expense
    """
    expense_date = instance.payment_date.date() if hasattr(instance.payment_date, 'date') else instance.payment_date

    # Delete corresponding Expense
    Expense.objects.filter(
        reference_type='salary_transaction',
        reference_id=instance.id
    ).delete()

    # Update SalaryTracker
    tracker = instance.staff.salarytracker_set.filter(date=expense_date).first()
    if tracker:
        total_paid = SalaryTransaction.objects.filter(
            staff=instance.staff,
            salary_tracker=tracker
        ).exclude(pk=instance.pk).aggregate(total=Sum('amount'))['total'] or 0

        tracker.paid_amount = total_paid

        if tracker.paid_amount >= tracker.total_salary:
            tracker.status = 'paid'
        elif tracker.paid_amount > 0:
            tracker.status = 'partial'
        else:
            tracker.status = 'pending'

        tracker.save(update_fields=['paid_amount', 'status'])
