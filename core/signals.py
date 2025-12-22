from datetime import timedelta
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.db.models import F
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import Category, Order, Purchase, Sale, SaleItem, PurchaseItem, FollowUpDashboard, OrderItem, Stock, Supplier

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


def first_time_mass_upload(data_list, current_user=None):
    with transaction.atomic():
        for row in data_list:

            # 1️⃣ Category
            category, _ = Category.objects.get_or_create(
                name=row['category']
            )

            # 2️⃣ Supplier
            supplier, _ = Supplier.objects.get_or_create(
                name=row['supplier']
            )

            # 3️⃣ Stock (NO stock quantity touched here)
            stock, _ = Stock.objects.get_or_create(
                item_no=row['item_no'],
                defaults={
                    'name': row['name'],
                    'category': category,
                    'model': row.get('model', 'N/A'),
                    'purchase_price': row.get('purchase_price', 0),
                    'sale_price': row.get('sale_price', 0),
                }
            )

            # Update prices only
            stock.purchase_price = row.get('purchase_price', stock.purchase_price)
            stock.sale_price = row.get('sale_price', stock.sale_price)
            stock.save(update_fields=['purchase_price', 'sale_price'])

            # 4️⃣ Purchase (signals add stock)
            if row.get('purchase_qty', 0) > 0:
                purchase = Purchase.objects.create(
                    supplier=supplier,
                    created_by=current_user
                )
                PurchaseItem.objects.create(
                    purchase=purchase,
                    item=stock,
                    quantity=row['purchase_qty'],
                    price=row['purchase_price'],
                    sale_price=row.get('sale_price', stock.sale_price),
                    vat=row.get('vat')
                )

            # 5️⃣ Sale (signals deduct stock)
            if row.get('sale_qty', 0) > 0:
                sale = Sale.objects.create(
                    customer_name=row.get('customer_name'),
                    contact_no=row.get('contact_no'),
                    vehicle_model=row.get('vehicle_model'),
                    handled_by=current_user,
                    is_servicing=False
                )
                SaleItem.objects.create(
                    sale=sale,
                    item=stock,
                    quantity=row['sale_qty'],
                    price=row['sale_price']
                )

                FollowUpDashboard.objects.get_or_create(
                    sale=sale,
                    customer_name=row.get('customer_name', ''),
                    contact_no=row.get('contact_no', ''),
                    vehicle=row.get('vehicle_model', '')
                )

            # 6️⃣ Order (NO stock change here)
            if row.get('order_qty', 0) > 0:
                order = Order.objects.create(
                    customer_name=row.get('customer_name', ''),
                    contact_no=row.get('contact_no', ''),
                    advance=row.get('advance', 0)
                )
                OrderItem.objects.create(
                    order=order,
                    item=stock,
                    quantity=row['order_qty'],
                    rate=row.get('order_rate', stock.sale_price)
                )
                order.update_totals()