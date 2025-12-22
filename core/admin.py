from django.contrib import admin
from .models import (
    Supplier, Category, Stock,
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
    def get_total_amount(self, obj):
        return obj.total_amount
    get_total_amount.short_description = "Total Amount"

    def get_paid_amount(self, obj):
        return getattr(obj, 'paid_amount', 0)
    get_paid_amount.short_description = "Paid Amount"

    def get_is_paid_status(self, obj):
        return getattr(obj, 'is_paid_status', False)
    get_is_paid_status.boolean = True
    get_is_paid_status.short_description = "Paid?"


# ---------------- Follow-Up ----------------
@admin.register(FollowUpDashboard)
class FollowUpDashboardAdmin(admin.ModelAdmin):
    list_display = (
        'customer_name',
        'vehicle',
        'post_service_feedback_date',
        'follow_up_date',        
        'expected_km',
        'assigned_to'
    )
    ordering = ('follow_up_date',)
    list_filter = ('follow_up_date', 'assigned_to')
    search_fields = ('customer_name', 'contact_no')
    list_select_related = ('assigned_to',)

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
    list_display = ('name', 'designation', 'phone', 'address', 'email', 'is_active')
    list_filter = ('is_active', 'designation')
    search_fields = ('name', 'phone', 'email')

# ---------------- User (LOGIN ONLY) ----------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email')
