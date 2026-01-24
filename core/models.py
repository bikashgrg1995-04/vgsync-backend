from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.db.models import F
from datetime import timedelta

def upload_to_item(instance, filename):
    return f'items/{instance.name}/{filename}'


def today_date():
    return timezone.now().date()

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
class Staff(models.Model):
    DESIGNATION_CHOICES = (
        ('admin', 'Admin'),
        ('accountant', 'Accountant'),
        ('technician', 'Technician'),
        ('helper', 'Helper'),
        ('sales', 'Sales'),
        ('other', 'Other'),
    )

    SALARY_MODE_CHOICES = (
        ('daily', 'Daily Based'),   # technician, accountant
        ('monthly', 'Monthly Based'),     # helper, admin, sales
    )

    name = models.CharField(max_length=100)
    designation = models.CharField(max_length=30, choices=DESIGNATION_CHOICES)
    salary_mode = models.CharField(max_length=10, choices=SALARY_MODE_CHOICES, default="monthly")
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


# ------------------ Salary Tracker ------------------

def today_date():
    return timezone.now().date()

class SalaryTracker(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(default=today_date)
    total_salary = models.FloatField(default=0, blank=True)  # monthly staff only
    paid_amount = models.FloatField(default=0)
    note = models.CharField(max_length=100, null = True, blank= True)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_mode = models.CharField(max_length=10, choices=[('cash','Cash'),('online','Online')], blank=True, null=True)

    @property
    def remaining_amount(self):
        if self.staff and self.staff.salary_mode == 'monthly':
            return self.total_salary - self.paid_amount
        return None  # daily staff won't have remaining_amount

    def save(self, *args, **kwargs):
        if self.staff:
            if self.staff.salary_mode == 'monthly':
                if self.paid_amount >= self.total_salary:
                    self.status = 'paid'
                elif self.paid_amount > 0:
                    self.status = 'partial'
                else:
                    self.status = 'pending'
            else:  # daily staff
                self.status = 'paid' if self.paid_amount > 0 else 'pending'
        super().save(*args, **kwargs)


# ------------------ Salary Transaction ------------------
class SalaryTransaction(models.Model):

    TRANSACTION_TYPE_CHOICES = [
       ('payment','Purchase payment'),
       ('advance', 'Advance'),
       ('daily_salary','Daily Salary'),
       ('monthly_salary', 'Monthly Salary'),
       ('operational', 'operational'),
       ('saving', 'Saving'),
       ('others', 'Others')
    ]

    salary_tracker = models.ForeignKey(
        SalaryTracker,
        on_delete=models.CASCADE,
        related_name='transactions',
        null=True, blank=True
    )
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name='salary_transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.FloatField()
    payment_date = models.DateField(default=today_date)
    payment_mode = models.CharField(
        max_length=10,
        choices=[('cash','Cash'),('online','Online')],
        blank=True, null=True
    )
    note = models.TextField(blank=True, null=True)
    created_at = models.DateField(default=today_date)

    def __str__(self):
        return f"{self.staff.name} - {self.transaction_type} - {self.amount}"


# ------------------ Expense ------------------
class Expense(models.Model):
    EXPENSE_TYPE_CHOICES = [
        ('salary', "Salary"),
        ('operational','Operational'),
        ('other','Other')
    ]
    PAYMENT_MODE_CHOICES = [
        ('cash','Cash'),
        ('online','Online')
    ]

    title = models.CharField(max_length=150)
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)
    amount = models.FloatField()
    expense_date = models.DateField(default=today_date, null=True)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES)
    spent_by = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses'
    )
    reference_type = models.CharField(max_length=50, blank=True, null=True)
    reference_id = models.PositiveIntegerField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"


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
class Stock(models.Model):
    item_no = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    group = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100)

    stock = models.IntegerField(default=0)

    purchase_price = models.FloatField(default=0)
    sale_price = models.FloatField(default=0)

    # ✅ NEW FIELD
    block = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Stock location e.g. Block A / Godown 1 / Rack B2"
    )

    image = models.ImageField(upload_to=upload_to_item, blank=True, null=True)

    class Meta:
        unique_together = ('name', 'model', 'category')

    def __str__(self):
        return f"{self.name} ({self.model})"

    def save(self, *args, **kwargs):
        if not self.group:
            self.group = self.category.name
        super().save(*args, **kwargs)

    def adjust_stock(self, qty: int):
        self.stock = F('stock') + qty
        self.save(update_fields=['stock'])
        self.refresh_from_db()


# ------------------ Purchase ------------------
class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)

    # FINANCIAL (UI CALCULATED)
    net_total = models.FloatField(default=0)            # frontend bata pathaune
    discount_percentage = models.FloatField(default=0)
    discount_amount = models.FloatField(default=0)
    grand_total = models.FloatField(default=0)          # frontend bata pathaune
    paid_amount = models.FloatField(default=0)          # frontend bata pathaune
    remaining_amount = models.FloatField(default=0)     # frontend bata pathaune

    STATUS_CHOICES = [('pending','Pending'),('partial','Partial'),('paid','Paid')]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    is_migrated = models.BooleanField(default=False)
    PAID_FROM_CHOICES = (('cash', 'Cash'), ('online', 'Online'), ('both', 'Both'))
    paid_from = models.CharField(max_length=20, choices=PAID_FROM_CHOICES, default='cash')

    def save(self, *args, **kwargs):
        # Backend will NOT calculate totals
        super().save(*args, **kwargs)


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.FloatField()
    sale_price = models.FloatField(default=0)

    def __str__(self):
        return f"{self.item.name} x {self.quantity} @ {self.price}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)


# ------------------ Sale ------------------
from django.contrib.auth import get_user_model

User = get_user_model()

# ------------------ Sale ------------------from django.db import models
class Sale(models.Model):
    
    VEHICLE_TYPE_CHOICES = (
        ('bike', 'Bike'),
        ('scooty', 'Scooty')
    )


    sale_ref = models.CharField(max_length=50, unique=True)
    sale_date = models.DateTimeField(default=timezone.now)

    # ---------------- BASIC INFO ----------------
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    contact_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_model = models.CharField(max_length=50, blank=True, null=True)

    handled_by = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, blank=True, null=True
    )

    # ---------------- SALE TYPE ----------------
    is_servicing = models.BooleanField(default=False)

    # ---------------- SERVICE INFO ----------------
    km_driven = models.IntegerField(blank=True, null=True)
    job_card_no = models.CharField(max_length=50, blank=True, null=True)
    bike_registration_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_type = models.CharField(
        max_length=10,
        choices=VEHICLE_TYPE_CHOICES,
        blank=True,
        null=True
    )
    vehicle_color = models.CharField(max_length=30, blank=True, null=True)

    received_date = models.DateField(blank=True, null=True)
    delivery_date = models.DateField(blank=True, null=True)

    bill_no = models.CharField(max_length=50, blank=True, null=True)
    technician_name = models.CharField(max_length=100, blank=True, null=True)

    is_free_servicing = models.BooleanField(default=False)
    is_repair_job = models.BooleanField(default=False)
    is_accident = models.BooleanField(default=False)
    is_warranty_job = models.BooleanField(default=False)

    job_done_on_vehicle = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    labour_charge = models.FloatField(default=0)

    follow_up_date = models.DateField(blank=True, null=True)
    post_service_feedback_date = models.DateField(blank=True, null=True)

    # ---------------- FINANCIAL (UI CALCULATED) ----------------
    grand_total = models.FloatField(default=0)
    discount_percentage = models.FloatField(default=0)
    discount_amount = models.FloatField(default=0)

    net_total = models.FloatField(default=0)
    paid_amount = models.FloatField(default=0)
    remaining_amount = models.FloatField(default=0)

    PAID_STATUS_CHOICES = (
        ('not_paid', 'Not Paid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    )
    is_paid = models.CharField(
        max_length=20, choices=PAID_STATUS_CHOICES, default='not_paid'
    )

    PAID_FROM_CHOICES = (
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('both', 'Both'),
    )
    paid_from = models.CharField(max_length=20, blank=True, null=True)

    is_migrated = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        🔒 Backend responsibility:
        - Clear service-only fields if not servicing
        - Do NOT calculate money here
        """

        if not self.is_servicing:
            self.labour_charge = 0
            self.km_driven = None
            self.job_card_no = None
            self.bike_registration_no = None
            self.vehicle_type = None
            self.vehicle_color = None
            self.received_date = None
            self.delivery_date = None
            self.follow_up_date = None
            self.post_service_feedback_date = None
            self.is_free_servicing = False
            self.is_repair_job = False
            self.is_accident = False
            self.is_warranty_job = False
            self.technician_name = None
            self.job_done_on_vehicle = None

        # auto follow-up (business rule OK here)
        if self.is_servicing and self.delivery_date:
            if not self.post_service_feedback_date:
                self.post_service_feedback_date = self.delivery_date + timedelta(days=3)
            if not self.follow_up_date:
                self.follow_up_date = self.delivery_date + timedelta(days=30)

        if not self.sale_ref:
            with transaction.atomic():
                last_sale = (
                    Sale.objects.select_for_update()
                    .order_by('-id')
                    .first()
                )
                next_id = (last_sale.id + 1) if last_sale else 1
                self.sale_ref = f"SALE-{next_id:06d}"

        super().save(*args, **kwargs)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(Stock, on_delete=models.CASCADE)

    quantity = models.IntegerField()
    sale_price = models.FloatField(default=0)
    total_price = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.sale_price
        super().save(*args, **kwargs)



# ------------------ Order ------------------
class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RECEIVED = 'received'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_RECEIVED, 'Received'),
        (STATUS_COMPLETED, 'Completed'),
    )

    customer_name = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_model = models.CharField(max_length=50, blank=True, null=True)
    order_date = models.DateTimeField(default=timezone.now)
    advance = models.FloatField(default=0)

    total_amount = models.FloatField(default=0)
    remaining_amount = models.FloatField(default=0)
    status = models.CharField(               
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

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
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, null=True, blank=True)
    assigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)

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

        fields = ["status", "terminated_at"]

        if reason:
            self.reason = reason
            fields.append("reason")

        self.save(update_fields=fields)


    class Meta:
        ordering = ['follow_up_date']

