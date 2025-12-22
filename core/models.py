from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.db.models import F
from datetime import timedelta

def upload_to_item(instance, filename):
    return f'items/{instance.name}/{filename}'

# ------------------ User ------------------
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('accountant', 'Accountant'),
        ('staff', 'Staff'),  # fallback / future
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='staff'
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

# ------------------ Staff ------------------
# models.py
class Staff(models.Model):
    DESIGNATION_CHOICES = (
        ('admin', 'Admin'),
        ('accountant', 'Accountant'),
        ('technician', 'Technician'),
        ('helper', 'Helper'),
        ('sales', 'Sales'),
        ('other', 'Other'),
    )

    # Remove this field completely
    # user = models.OneToOneField(User, ...)

    name = models.CharField(max_length=100)
    designation = models.CharField(max_length=30, choices=DESIGNATION_CHOICES)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(blank=True, null=True)



# ------------------ Core Entities ------------------
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Supplier(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.name

# ------------------ Stock ------------------
class Stock(models.Model):
    item_no = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    group = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100)

    stock = models.IntegerField(default=0)

    purchase_price = models.FloatField(default=0)
    sale_price = models.FloatField(default=0)
    vat = models.FloatField(default=0)

    image = models.ImageField(upload_to=upload_to_item, blank=True, null=True)

    class Meta:
        unique_together = ('name', 'model', 'category')

    def __str__(self):
        return f"{self.name} ({self.model})"

    def save(self, *args, **kwargs):
        if not self.group:
            self.group = self.category.name
        super().save(*args, **kwargs)

    def adjust_stock(self, qty):
        self.stock = F('stock') + qty
        self.save(update_fields=['stock'])
        self.refresh_from_db()

# ------------------ Purchase ------------------
class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)

    vat_percentage = models.FloatField(default=13)
    discount_percentage = models.FloatField(default=0)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Purchase #{self.id}"

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(Stock, on_delete=models.CASCADE)

    quantity = models.IntegerField()
    price = models.FloatField()
    vat = models.FloatField(null=True, blank=True)
    sale_price = models.FloatField(default=0)

    def total_price(self):
        return self.quantity * self.price

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_qty = 0

        if not is_new:
            old_qty = PurchaseItem.objects.get(pk=self.pk).quantity

        super().save(*args, **kwargs)

        # Adjust stock
        #qty_change = self.quantity - old_qty
       # self.item.adjust_stock(qty_change)

        # Update item pricing + VAT
        self.item.purchase_price = self.price
        self.item.sale_price = self.sale_price
        if self.vat is not None:
            self.item.vat = self.vat
        self.item.save(update_fields=['purchase_price', 'sale_price', 'vat'])

    def delete(self, *args, **kwargs):
        #self.item.adjust_stock(-self.quantity)
        super().delete(*args, **kwargs)

# ------------------ Sale ------------------
from django.contrib.auth import get_user_model

User = get_user_model()


class Sale(models.Model):
    sale_date = models.DateTimeField(default=timezone.now)

    # Basic fields (for both stock and service sales)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    contact_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_model = models.CharField(max_length=50, blank=True, null=True)
    is_servicing = models.BooleanField(default=False)
    km_driven = models.IntegerField(default=0, blank=True, null=True)

    # Service-specific fields
    job_card_no = models.CharField(max_length=50, blank=True, null=True)
    bike_registration_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_color = models.CharField(max_length=30, blank=True, null=True)
    received_date = models.DateField(blank=True, null=True)
    delivery_date = models.DateField(blank=True, null=True)
    bill_no = models.CharField(max_length=50, blank=True, null=True)
    technician_name = models.CharField(max_length=100, blank=True, null=True)
    is_free_servicing = models.BooleanField(default=False)
    is_repair_job = models.BooleanField(default=False)
    is_accident = models.BooleanField(default=False)
    is_warranty_job = models.BooleanField(default=False)
    post_service_feedback_date = models.DateField(blank=True, null=True)
    follow_up_date = models.DateField(blank=True, null=True)
    post_service_feedback_date = models.DateField(blank=True, null=True)
    job_done_on_vehicle = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    # Financial fields
    total_amount = models.FloatField(default=0, blank=True, null=True)
    labour_charge = models.FloatField(default=0, blank=True, null=True)
    paid_amount = models.FloatField(default=0, blank=True, null=True)
    remaining_amount = models.FloatField(default=0, blank=True, null=True)

    PAID_STATUS_CHOICES = [
        ('not_paid', 'Not Paid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid')
    ]
    is_paid = models.TextField(blank=True, null=True)  # <- add default

    PAID_FROM_CHOICES = [
        ('cash', 'Cash'),
        ('esewa', 'eSewa'),
        ('both', 'Both')
    ]
    paid_from = models.CharField(max_length=20, choices=PAID_FROM_CHOICES, blank=True, null=True)

    handled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Sale #{self.id} - {'Service' if self.is_servicing else 'Stock'}"
    
    def update_payment_status(self):
        """Update remaining_amount and is_paid based on paid_amount and total_amount"""
        self.remaining_amount = max(self.total_amount - self.paid_amount, 0)
        if self.paid_amount >= self.total_amount:
            self.is_paid = 'paid'
        elif self.paid_amount > 0:
            self.is_paid = 'partial'
        else:
            self.is_paid = 'not_paid'


    def calculate_totals(self, new_paid_amount=None):
        """
        Calculate totals from related SaleItems
        - total_amount = sum(items) + labour_charge
        - remaining_amount = total_amount - paid_amount
        - is_paid status
        """
        items_total = sum([item.quantity * item.price for item in self.items.all()])
        total_amount = items_total + (self.labour_charge or 0)
        paid_amount = new_paid_amount if new_paid_amount is not None else self.paid_amount or 0
        remaining_amount = max(total_amount - paid_amount, 0)

        
        is_paid = self.update_payment_status()
        

        return total_amount, remaining_amount, is_paid

    def save(self, *args, **kwargs):
        # First save to get PK if new
        super().save(*args, **kwargs)

        # Auto-calc service dates
        if self.is_servicing and self.delivery_date:
            if not self.post_service_feedback_date:
                self.post_service_feedback_date = self.delivery_date + timedelta(days=3)
            if not self.follow_up_date:
                self.follow_up_date = self.delivery_date + timedelta(days=30)

        # Recalculate totals using actual items
        total_amount, remaining_amount, is_paid = self.calculate_totals()
        self.total_amount = total_amount
        self.remaining_amount = remaining_amount
        self.is_paid = is_paid

        super().save(update_fields=[
            'total_amount',
            'remaining_amount',
            'is_paid',
            'post_service_feedback_date',
            'follow_up_date'
        ])


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey('Stock', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.FloatField()

    def total_price(self):
        return self.quantity * self.price

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)



# ------------------ Order ------------------
class Order(models.Model):
    customer_name = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_model = models.CharField(max_length=50, blank=True, null=True)
    order_date = models.DateTimeField(default=timezone.now)
    advance = models.FloatField(default=0)

    total_amount = models.FloatField(default=0)
    remaining_amount = models.FloatField(default=0)

    def update_totals(self):
        self.total_amount = sum(item.total_price() for item in self.items.all())
        self.remaining_amount = self.total_amount - self.advance
        self.save(update_fields=['total_amount', 'remaining_amount'])

    def save(self, *args, **kwargs):
        # If object already exists, recalc remaining amount
        if self.pk:
            self.remaining_amount = self.total_amount - self.advance
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    rate = models.FloatField()

    def total_price(self):
        return self.quantity * self.rate

# ------------------ Follow-Up Dashboard ------------------
class FollowUpDashboard(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("terminated", "Terminated"),
    )
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    customer_name = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle = models.CharField(max_length=50, blank=True, null=True)

    delivery_date = models.DateField(null=True, blank=True)

    post_service_feedback_date = models.DateField(null=True, blank=True)  # ✅ ADD
    follow_up_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    terminated_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)  # ✅ add this

    remarks = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def terminate(self, reason=None):
        self.status = "terminated"
        self.terminated_at = timezone.now()
        if reason:
            self.reason = reason
        self.save(update_fields=["status", "terminated_at", "reason"])

    class Meta:
        ordering = ['follow_up_date']
