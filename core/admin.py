from django.contrib import admin
from .models import (
    Salary, Supplier, Customer, Category, Item,
    Purchase, PurchaseItem, Sale, SaleItem, FollowUp, User
)
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Inlines
class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1


# Admins
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'email')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'email')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'group', 'model', 'stock', 'purchase_price', 'sale_price')
    search_fields = ('name', 'model')
    list_filter = ('group', 'category')


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'date', 'total_amount')
    inlines = [PurchaseItemInline]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'sale_date', 'total_amount')
    list_filter = ('sale_date',)
    search_fields = ('customer__name',)
    date_hierarchy = 'sale_date'


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_customer', 'service_date', 'follow_up_date', 'completed')
    list_filter = ('completed', 'follow_up_date')
    search_fields = ('sale__customer__name',)
    date_hierarchy = 'follow_up_date'

    def get_customer(self, obj):
        return obj.sale.customer.name if obj.sale and obj.sale.customer else '-'
    get_customer.short_description = 'Customer'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff', 'is_active']

@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'date']