from datetime import timedelta
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.db.models import F
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import Sale, SaleItem, PurchaseItem, FollowUpDashboard, OrderItem, Stock

FOLLOW_UP_INTERVAL_DAYS = 30
FOLLOW_UP_KM_THRESHOLD = 1500

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
def manage_followup(sender, instance, **kwargs):
    if instance.is_servicing and instance.delivery_date:
        follow_up_date = instance.delivery_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)
        post_feedback_date = instance.delivery_date + timedelta(days=3)
        expected_km = (instance.km_driven or 0) + FOLLOW_UP_KM_THRESHOLD

        FollowUpDashboard.objects.update_or_create(
            sale=instance,
            defaults={
                'customer_name': instance.customer_name or "Unknown",
                'contact_no': instance.contact_no,
                'vehicle': instance.vehicle_model,
                'delivery_date': instance.delivery_date,
                'post_service_feedback_date': post_feedback_date,
                'follow_up_date': follow_up_date,
                'expected_km': expected_km,
                'remarks': "Auto-created servicing follow-up"
            }
        )
    else:
        FollowUpDashboard.objects.filter(sale=instance).delete()


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
