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
        ('staff', 'Staff'),
        ('technician', 'Technician'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')

    def __str__(self):
        return f"{self.username} ({self.role})"

# ------------------ Technician & Staff ------------------
class Technician(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'technician'},
        related_name='technician_profile',
        null=True  # Now non-nullable
    )
    specialization = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username

class Staff(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'staff'},
        related_name='staff_profile',
        null=True  # Now non-nullable
    )
    designation = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username

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
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

User = get_user_model()

class Sale(models.Model):
    sale_date = models.DateTimeField(default=timezone.now)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    contact_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_model = models.CharField(max_length=50, blank=True, null=True)

    is_servicing = models.BooleanField(default=False)
    km_driven = models.IntegerField(default=0)

    total_amount = models.FloatField(default=0)
    handled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Sale #{self.id}"
    
    def delete(self, *args, **kwargs):
        # Restore stock for all SaleItems
        for item in self.items.all():
            item.delete()  # SaleItem.delete() restores stock

        # Delete follow-up if exists
        FollowUpDashboard.objects.filter(sale=self).delete()

        # Delete sale itself
        super().delete(*args, **kwargs)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey('Stock', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.FloatField()

    def total_price(self):
        return self.quantity * self.price

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_qty = 0

        if not is_new:
            old_qty = SaleItem.objects.get(pk=self.pk).quantity

        super().save(*args, **kwargs)

        # Adjust stock
        qty_change = self.quantity - old_qty
        self.item.adjust_stock(-qty_change)

    def delete(self, *args, **kwargs):
        # Restore stock when deleted
        self.item.adjust_stock(self.quantity)
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
    sale = models.OneToOneField(
        Sale,
        on_delete=models.CASCADE,
        related_name='followup'
    )
    customer_name = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle = models.CharField(max_length=50, blank=True, null=True)

    delivery_date = models.DateField(default=timezone.now)
    follow_up_date = models.DateField(default=timezone.now)
    expected_km = models.IntegerField(default=1500, help_text="KM at which follow-up is required")

    remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['follow_up_date']

    def __str__(self):
        return f"Follow-up for {self.customer_name}"
