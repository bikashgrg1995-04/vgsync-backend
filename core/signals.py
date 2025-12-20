from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from datetime import timedelta
from .models import OrderItem

from .models import Sale, FollowUpDashboard

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from datetime import timedelta
from .models import Sale, FollowUpDashboard

FOLLOW_UP_INTERVAL_DAYS = 30
FOLLOW_UP_KM_THRESHOLD = 1500

# ------------------ Create or Update Follow-up ------------------
@receiver(post_save, sender=Sale)
def manage_followup(sender, instance, created, **kwargs):
    """
    Create or update a follow-up for servicing sales.
    Delete follow-up if sale is not servicing.
    """
    if instance.is_servicing:
        follow_up_date = (instance.sale_date + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)).date()
        expected_km = instance.km_driven + FOLLOW_UP_KM_THRESHOLD

        # Update or create follow-up
        FollowUpDashboard.objects.update_or_create(
            sale=instance,
            defaults={
                'customer_name': instance.customer_name or "Unknown",
                'contact_no': instance.contact_no,
                'vehicle': instance.vehicle_model,
                'delivery_date': instance.sale_date.date(),
                'follow_up_date': follow_up_date,
                'expected_km': expected_km,
                'remarks': "Auto-created servicing follow-up"
            }
        )
    else:
        # Delete follow-up if sale is not servicing
        FollowUpDashboard.objects.filter(sale=instance).delete()


# ------------------ Delete Follow-up on Sale deletion ------------------
@receiver(pre_delete, sender=Sale)
def delete_followup_on_sale_delete(sender, instance, **kwargs):
    """
    Ensure follow-up is deleted when sale is deleted.
    """
    FollowUpDashboard.objects.filter(sale=instance).delete()



@receiver(post_save, sender=OrderItem)
def update_order_totals_on_save(sender, instance, **kwargs):
    instance.order.update_totals()

@receiver(post_delete, sender=OrderItem)
def update_order_totals_on_delete(sender, instance, **kwargs):
    instance.order.update_totals()