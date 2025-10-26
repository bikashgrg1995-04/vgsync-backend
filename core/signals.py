from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Sale, SaleItem, FollowUp, PurchaseItem

FOLLOW_UP_INTERVAL_DAYS = 30

# ------------------ SALE & STOCK ------------------

@receiver(post_save, sender=SaleItem)
def adjust_stock_on_sale_item(sender, instance, created, **kwargs):
    """
    Adjust stock when a SaleItem is created or updated.
    Negative quantity for sold items.
    """
    # For atomic safety
    with transaction.atomic():
        if created:
            instance.item.adjust_stock(-instance.quantity)
        else:
            old = SaleItem.objects.get(pk=instance.pk)
            diff = instance.quantity - old.quantity
            instance.item.adjust_stock(-diff)

@receiver(pre_delete, sender=SaleItem)
def restore_stock_on_sale_item_delete(sender, instance, **kwargs):
    """Restore stock when a SaleItem is deleted."""
    with transaction.atomic():
        instance.item.adjust_stock(instance.quantity)


# ------------------ FOLLOW-UP ------------------
@receiver(post_save, sender=Sale)
def sync_followup_on_sale(sender, instance, created, **kwargs):
    """
    Create, update, or delete follow-up based on Sale changes.
    """
    if instance.is_servicing:
        # Use defaults to ensure NOT NULL fields exist
        followup, created_followup = FollowUp.objects.get_or_create(
            sale=instance,
            defaults={
                'service_date': instance.sale_date or timezone.now().date(),
                'follow_up_date': (instance.sale_date or timezone.now().date()) + timedelta(days=FOLLOW_UP_INTERVAL_DAYS),
                'completed': False,
                'remarks': f"Auto-generated follow-up for Sale #{instance.id}"
            }
        )

        if not created_followup:
            # Update fields if FollowUp already existed
            followup.service_date = instance.sale_date or followup.service_date
            followup.follow_up_date = followup.service_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)
            followup.completed = False
            followup.save()
    else:
        FollowUp.objects.filter(sale=instance).delete()


@receiver(pre_delete, sender=Sale)
def delete_followup_on_sale_delete(sender, instance, **kwargs):
    """Delete follow-up when Sale is deleted."""
    FollowUp.objects.filter(sale=instance).delete()


# ------------------ PURCHASE STOCK ------------------

@receiver(post_save, sender=PurchaseItem)
def adjust_stock_on_purchase(sender, instance, created, **kwargs):
    """Add purchased quantity to stock."""
    with transaction.atomic():
        if created:
            instance.item.adjust_stock(instance.quantity)
        else:
            old = PurchaseItem.objects.get(pk=instance.pk)
            diff = instance.quantity - old.quantity
            instance.item.adjust_stock(diff)

@receiver(pre_delete, sender=PurchaseItem)
def remove_stock_on_purchase_delete(sender, instance, **kwargs):
    """Remove purchased stock when deleted."""
    with transaction.atomic():
        instance.item.adjust_stock(-instance.quantity)
