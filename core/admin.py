from django.contrib import admin
from django.db.models import Sum
from .models import (
    Expense, SalaryTracker, SalaryTransaction, Supplier, Category, Stock,
    Purchase, PurchaseItem,
    Sale, SaleItem,
    FollowUpDashboard,
    Order, OrderItem,
    Staff, User
)

# ---------------- Inlines ----------------
class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

class SalaryTransactionInline(admin.TabularInline):
    model = SalaryTransaction
    extra = 0
    readonly_fields = ('paid_amount_snapshot',)
    
    # Optional: show snapshot of tracker paid_amount at time of transaction
    def paid_amount_snapshot(self, obj):
        return obj.amount
    paid_amount_snapshot.short_description = "Transaction Amount"

# ---------------- Supplier ----------------
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'email')

# ---------------- Category ----------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

# ---------------- Stock ----------------
@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        'item_no', 'name', 'category',
        'model', 'stock',
        'purchase_price', 'sale_price', 'vat'
    )
    search_fields = ('name', 'model', 'item_no')
    list_filter = ('category',)

# ---------------- Purchase ----------------
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'date', 'get_total_amount')
    inlines = [PurchaseItemInline]
    readonly_fields = ('get_total_amount',)
    date_hierarchy = 'date'
    list_select_related = ('supplier',)
    autocomplete_fields = ['created_by']

    def get_total_amount(self, obj):
        return sum(i.total_price() for i in obj.items.all())
    get_total_amount.short_description = "Total Amount"

# ---------------- Sale ----------------
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sale_date',
        'customer_name',
        'is_servicing',
        'bill_no',
        'get_total_amount',
        'get_paid_amount',
        'get_is_paid_status',
        'handled_by',
    )
    readonly_fields = ('get_total_amount', 'get_paid_amount', 'get_is_paid_status')
    list_select_related = ('handled_by',)
    autocomplete_fields = ['handled_by']

    def get_total_amount(self, obj):
        return obj.total_amount
    get_total_amount.short_description = "Total Amount"

    def get_paid_amount(self, obj):
        return getattr(obj, 'paid_amount', 0)
    get_paid_amount.short_description = "Paid Amount"

    def get_is_paid_status(self, obj):
        return obj.is_paid == 'paid'
    get_is_paid_status.boolean = True
    get_is_paid_status.short_description = "Fully Paid?"

# ---------------- Follow-Up ----------------
@admin.register(FollowUpDashboard)
class FollowUpDashboardAdmin(admin.ModelAdmin):
    list_display = (
        'customer_name',
        'vehicle',
        'follow_up_date',
        'post_service_feedback_date',
        'assigned_to',
        'status',
        'reason',
    )
    ordering = ('follow_up_date',)
    list_filter = ('follow_up_date', 'assigned_to', 'status')
    search_fields = ('customer_name', 'contact_no')
    list_select_related = ('assigned_to',)
    autocomplete_fields = ['assigned_to']

# ---------------- Order ----------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_name',
        'order_date',
        'total_amount',
        'advance',
        'remaining_amount'
    )
    inlines = [OrderItemInline]
    readonly_fields = ('total_amount', 'remaining_amount')
    date_hierarchy = 'order_date'

# ---------------- Staff ----------------
@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'designation', 'salary_mode', 'phone', 'address', 'email', 'is_active')
    list_filter = ('is_active', 'designation', 'salary_mode')
    search_fields = ('name', 'phone', 'email')

# ---------------- SalaryTransaction ----------------
@admin.register(SalaryTransaction)
class SalaryTransactionAdmin(admin.ModelAdmin):
    list_display = ('staff', 'transaction_type', 'amount', 'payment_date', 'payment_mode', 'salary_tracker')
    list_filter = ('transaction_type', 'payment_mode', 'payment_date')
    search_fields = ('staff__name',)
    autocomplete_fields = ['staff', 'salary_tracker']

# ---------------- Expense ----------------
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'expense_type', 'amount', 'expense_date', 'payment_mode', 'spent_by', 'reference_type', 'reference_id')
    list_filter = ('expense_type', 'payment_mode', 'expense_date')
    search_fields = ('title', 'spent_by__name')

# ---------------- User ----------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email')

# ---------------- SalaryTracker ----------------
@admin.register(SalaryTracker)
class SalaryTrackerAdmin(admin.ModelAdmin):
    list_display = ('date', 'staff', 'total_salary', 'paid_amount', 'remaining_amount', 'status', 'payment_mode')
    list_filter = ('status', 'payment_mode', 'date')
    search_fields = ('staff__name',)
    readonly_fields = ('paid_amount', 'remaining_amount')
    inlines = [SalaryTransactionInline]

    def paid_amount(self, obj):
        return sum(t.amount for t in obj.transactions.all())

    def remaining_amount(self, obj):
        return obj.total_salary - self.paid_amount(obj)
