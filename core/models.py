from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import AbstractUser, Group, Permission

CATEGORY_CHOICES = [('Spare', 'Spare'), ('Lube', 'Lube')]


# ------------------ Upload Paths ------------------

def upload_to_supplier(instance, filename):
    return f'suppliers/{instance.name}/{filename}'


def upload_to_customer(instance, filename):
    return f'customers/{instance.name}/{filename}'


def upload_to_item(instance, filename):
    return f'items/{instance.name}/{filename}'


# ------------------ User with Role ------------------
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    )
    is_admin = models.BooleanField(default=False)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='staff')

    def __str__(self):
        return f"{self.username} ({self.role})"


# ------------------ Core Entities ------------------

class Supplier(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    image = models.ImageField(upload_to=upload_to_supplier, blank=True, null=True)

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    image = models.ImageField(upload_to=upload_to_customer, blank=True, null=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Item(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    group = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    model = models.CharField(max_length=100)
    stock = models.IntegerField(default=0)
    purchase_price = models.FloatField(default=0)
    sale_price = models.FloatField(default=0)
    image = models.ImageField(upload_to=upload_to_item, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'model', 'group', 'category'],
                name='unique_item_per_category'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.model})"

    def adjust_stock(self, quantity_change: int):
        """Safely update item stock (positive or negative)."""
        self.stock = models.F('stock') + quantity_change
        self.save(update_fields=['stock'])
        self.refresh_from_db()  # Refresh to get actual updated value


# ------------------ Purchase & Sales ------------------

class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)

    def total_amount(self):
        return sum(item.total_price() for item in self.items.all())

    def __str__(self):
        return f"Purchase #{self.id} from {self.supplier.name}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.FloatField()

    def total_price(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"


class Sale(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='sales')
    sale_date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_servicing = models.BooleanField(default=False)
    distance_covered = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)

    def total(self):
        return sum(item.total_price() for item in self.items.all())

    def __str__(self):
        return f"Sale ({'Servicing' if self.is_servicing else 'Normal'}) - {self.customer.name}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.FloatField()

    def total_price(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"


# ------------------ Follow-Up ------------------

class FollowUp(models.Model):
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name='followup')
    service_date = models.DateField()  # Date of servicing
    follow_up_date = models.DateField()  # Next follow-up date
    remarks = models.TextField(blank=True, null=True)
    completed = models.BooleanField(default=False)

    def __str__(self):
        customer_name = self.sale.customer.name if self.sale and self.sale.customer else "Unknown"
        return f"Follow-up for {customer_name} on {self.follow_up_date}"


# ------------------ Salary (Optional) ------------------

class Salary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.FloatField()
    date = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.date})"