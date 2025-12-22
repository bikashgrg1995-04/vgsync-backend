from datetime import timedelta
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.db.models import F
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import Sale, SaleItem, PurchaseItem, FollowUpDashboard, OrderItem, Stock

FOLLOW_UP_INTERVAL_DAYS = 30
POST_FEEDBACK_DAYS = 3

# ---------------- PURCHASE ITEM → STOCK ----------------
@receiver(pre_save, sender=PurchaseItem)
def store_old_purchase_qty(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_quantity = PurchaseItem.objects.get(pk=instance.pk).quantity
        except ObjectDoesNotExist:
            instance._old_quantity = 0
    else:
        instance._old_quantity = 0

@receiver(post_save, sender=PurchaseItem)
def adjust_stock_on_purchase_save(sender, instance, **kwargs):
    diff = instance.quantity - getattr(instance, '_old_quantity', 0)
    if diff != 0:
        Stock.objects.filter(pk=instance.item.pk).update(stock=F('stock') + diff)

@receiver(pre_delete, sender=PurchaseItem)
def reduce_stock_on_purchase_delete(sender, instance, **kwargs):
    Stock.objects.filter(pk=instance.item.pk).update(stock=F('stock') - instance.quantity)

# ---------------- SALE ITEM → STOCK ----------------
@receiver(pre_save, sender=SaleItem)
def store_old_sale_qty(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_quantity = SaleItem.objects.get(pk=instance.pk).quantity
        except ObjectDoesNotExist:
            instance._old_quantity = 0
    else:
        instance._old_quantity = 0

@receiver(post_save, sender=SaleItem)
def adjust_stock_on_sale_save(sender, instance, **kwargs):
    if not instance.sale_id:
        return  # sale not saved yet
    diff = instance.quantity - getattr(instance, '_old_quantity', 0)
    stock = Stock.objects.get(pk=instance.item.pk)
    stock.stock = max(stock.stock - diff, 0)
    stock.save(update_fields=['stock'])

@receiver(pre_delete, sender=SaleItem)
def restore_stock_on_sale_delete(sender, instance, **kwargs):
    stock = Stock.objects.get(pk=instance.item.pk)
    stock.stock += instance.quantity
    stock.save(update_fields=['stock'])

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
