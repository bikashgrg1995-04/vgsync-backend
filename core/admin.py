from django.contrib import admin
from .models import (
    Supplier, Category, Stock,
    Purchase, PurchaseItem,
    Sale, SaleItem,
    FollowUpDashboard,
    Order, OrderItem,
    Technician, Staff, User
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
        'get_total_amount'
    )
    ordering = ('-sale_date',)
    inlines = [SaleItemInline]

    def get_total_amount(self, obj):
        return sum(i.total_price() for i in obj.items.all())

    get_total_amount.short_description = "Total Amount"



# ---------------- Follow-Up ----------------
@admin.register(FollowUpDashboard)
class FollowUpDashboardAdmin(admin.ModelAdmin):
    list_display = (
        'customer_name', 'vehicle',
        'follow_up_date', 'expected_km'
    )
    ordering = ('follow_up_date',)


# ---------------- Order ----------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'order_date', 'total_amount', 'advance', 'remaining_amount')
    inlines = [OrderItemInline]


# ---------------- Technician ----------------
@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization')


# ---------------- Staff ----------------
@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'designation')
