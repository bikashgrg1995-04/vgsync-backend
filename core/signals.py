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
      # 🚫 skip migrated purchases
    if instance.purchase.is_migrated:
        return
    
    diff = instance.quantity - getattr(instance, '_old_quantity', 0)

    if diff == 0:
        return

    Stock.objects.select_for_update().filter(
        pk=instance.item_id
    ).update(stock=F('stock') + diff)


@receiver(pre_delete, sender=PurchaseItem)
@transaction.atomic
def reduce_stock_on_purchase_delete(sender, instance, **kwargs):
      # 🚫 skip migrated purchases
    if instance.purchase.is_migrated:
        return
    
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
        
        # 🚫 skip migrated sales
        if instance.sale.is_migrated:
            return

        diff = instance.quantity - getattr(instance, '_old_quantity', 0)

        if diff == 0:
            return

        Stock.objects.select_for_update().filter(
            pk=instance.item_id
        ).update(stock=F('stock') - diff)

@receiver(pre_delete, sender=SaleItem)
@transaction.atomic
def restore_stock_on_sale_delete(sender, instance, **kwargs):
    # 🚫 skip migrated sales
    if instance.sale.is_migrated:
        return

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
    followup.vehicle = instance.vehicle_model or instance.bike_registration_no
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

# ---------------- SalaryTransaction → SalaryTracker & Expense ----------------
# ---------------- SalaryTransaction → SalaryTracker & Expense ----------------
@receiver(post_save, sender=SalaryTransaction)
@transaction.atomic
def handle_salary_transaction_save(sender, instance, created, **kwargs):
    """
    When a SalaryTransaction is created or updated:
    - Create Expense if not adjustment
    - Update the linked SalaryTracker
    """
    # 1️⃣ Create Expense
    if created and instance.transaction_type != 'adjustment':
        Expense.objects.create(
            title=f"{instance.transaction_type.title()} - {instance.staff.name}",
            expense_type='salary',
            amount=instance.amount,
            expense_date=instance.payment_date,
            payment_mode=instance.payment_mode,
            reference_type='salary_transaction',
            reference_id=instance.id,
            spent_by=None
        )

    # 2️⃣ Determine tracker
    tracker = instance.salary_tracker
    if not tracker:
        # Check existing tracker for same staff + date
        tracker = SalaryTracker.objects.filter(
            staff=instance.staff
        ).first()

        if not tracker:
            # Create new if none exists
            tracker = SalaryTracker.objects.create(
                staff=instance.staff,
                date=instance.payment_date,
                total_salary=0 if instance.staff.salary_mode == 'daily' else 0,
                paid_amount=0,
                note=''
            )

        # Link transaction to tracker
        instance.salary_tracker = tracker
        instance.save(update_fields=['salary_tracker'])

    # 3️⃣ Update total paid
    total_paid = SalaryTransaction.objects.filter(
        salary_tracker=tracker
    ).aggregate(total=Sum('amount'))['total'] or 0
    tracker.paid_amount = total_paid

    # 4️⃣ Combine notes
    notes = SalaryTransaction.objects.filter(
        salary_tracker=tracker
    ).values_list('note', flat=True)
    tracker.note = "\n".join(filter(None, notes))

    # 5️⃣ Update status
    if instance.staff.salary_mode == 'monthly':
        if tracker.total_salary == 0 or tracker.paid_amount >= tracker.total_salary:
            tracker.status = 'paid'
        elif tracker.paid_amount > 0:
            tracker.status = 'partial'
        else:
            tracker.status = 'pending'
    else:
        # daily staff
        tracker.status = 'paid' if tracker.paid_amount > 0 else 'pending'

    tracker.save(update_fields=['paid_amount', 'note', 'status'])

@receiver(pre_delete, sender=SalaryTransaction)
@transaction.atomic
def handle_salary_transaction_delete(sender, instance, **kwargs):
    """
    When a SalaryTransaction is deleted:
    - Delete related Expense
    - Update linked SalaryTracker paid_amount, note, and status
    """
    # 1️⃣ Delete corresponding Expense
    Expense.objects.filter(
        reference_type='salary_transaction',
        reference_id=instance.id
    ).delete()

    # 2️⃣ Update tracker if exists
    tracker = instance.salary_tracker
    if tracker:
        # Recalculate total paid excluding this transaction
        total_paid = SalaryTransaction.objects.filter(
            salary_tracker=tracker
        ).exclude(pk=instance.pk).aggregate(total=Sum('amount'))['total'] or 0
        tracker.paid_amount = total_paid

        # Recombine notes
        notes = SalaryTransaction.objects.filter(
            salary_tracker=tracker
        ).exclude(pk=instance.pk).values_list('note', flat=True)
        combined_note = "\n".join(filter(None, notes))
        tracker.note = combined_note

        # Update status
        if tracker.staff.salary_mode == 'monthly':
            if tracker.total_salary == 0 or tracker.paid_amount >= tracker.total_salary:
                tracker.status = 'paid'
            elif tracker.paid_amount > 0:
                tracker.status = 'partial'
            else:
                tracker.status = 'pending'
        else:
            tracker.status = 'paid' if tracker.paid_amount > 0 else 'pending'

        tracker.save(update_fields=['paid_amount', 'note', 'status'])