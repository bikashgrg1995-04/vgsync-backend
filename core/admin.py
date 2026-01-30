from django.contrib import admin
from django.db.models import Sum
from .models import (
    Expense, SalaryTracker, SalaryTransaction, Supplier, Category, Stock,
    Purchase, PurchaseItem,
    Sale, SaleItem,
    FollowUpDashboard,
    Order, OrderItem,
    Staff, User, BikeSale, EmiTracker, BikeSaleFollowUp
)
from core.services.utils import generate_emi_schedule


# ================= INLINES =================

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    readonly_fields = ('total_price',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


class SalaryTransactionInline(admin.TabularInline):
    model = SalaryTransaction
    extra = 0
    readonly_fields = ('paid_amount_snapshot',)

    def paid_amount_snapshot(self, obj):
        return obj.amount
    paid_amount_snapshot.short_description = "Transaction Amount"

# ---------------------------
# EMI Tracker Inline
# ---------------------------
class EmiTrackerInline(admin.TabularInline):
    model = EmiTracker
    extra = 0
    readonly_fields = ('status',)
    fields = ('installment_no', 'due_date', 'amount_due', 'paid_amount', 'payment_date', 'payment_method', 'status')


# ================= SUPPLIER =================

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'email')
    search_fields = ('name', 'contact', 'email')


# ================= CATEGORY =================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# ================= STOCK =================
@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        'item_no',
        'name',
        'category',
        'model',
        'block',            # ✅ ADD
        'stock',
        'purchase_price',
        'sale_price',
    )

    search_fields = (
        'name',
        'model',
        'item_no',
        'block',            # ✅ ADD
    )

    list_filter = (
        'category',
        'block',            # ✅ ADD
    )

    # ✅ SAFETY: Prevent deleting stock used in transactions
    def has_delete_permission(self, request, obj=None):
        if obj and (
            obj.purchaseitem_set.exists() or
            obj.saleitem_set.exists() or
            obj.orderitem_set.exists()
        ):
            return False
        return super().has_delete_permission(request, obj)



# ================= PURCHASE =================

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'supplier', 'date',
        'grand_total', 'discount_amount', 'net_total',
        'paid_amount', 'remaining_amount', 'status'
    )
    inlines = [PurchaseItemInline]
    readonly_fields = (
        'grand_total', 'discount_amount', 'net_total',
        'paid_amount', 'remaining_amount', 'status'
    )
    date_hierarchy = 'date'
    list_select_related = ('supplier',)
    autocomplete_fields = ['created_by']


# ================= SALE =================

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'sale_ref',
        'sale_date',
        'customer_name',
        'is_servicing',
        'bill_no',
        'get_net_total',        # ✅ changed
        'get_paid_amount',
        'get_remaining_amount',
        'get_is_paid_status',
        'handled_by',
        'technician_name',
        'km_driven',
        'bike_registration_no',
        'vehicle_type',
        'vehicle_color',
    )
    inlines = [SaleItemInline]
    readonly_fields = (
        'get_net_total',        # ✅ changed
        'get_paid_amount',
        'get_remaining_amount',
        'get_is_paid_status',
        'sale_ref'
    )
    list_select_related = ('handled_by',)
    autocomplete_fields = ['handled_by']

    # ---------------- COMPUTED FIELDS ----------------
    def get_net_total(self, obj):
        return obj.net_total
    get_net_total.short_description = "Net Total"

    def get_paid_amount(self, obj):
        return obj.paid_amount or 0
    get_paid_amount.short_description = "Paid Amount"

    def get_remaining_amount(self, obj):
        return obj.remaining_amount or 0
    get_remaining_amount.short_description = "Remaining Amount"

    def get_is_paid_status(self, obj):
        if obj.paid_amount >= (obj.net_total or 0):
            return True
        elif obj.paid_amount > 0:
            return "Partial"
        return False
    get_is_paid_status.short_description = "Paid?"

# ================= FOLLOW-UP =================

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


# ================= ORDER =================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_name',
        'order_date',
        'total_amount',
        'advance',
        'remaining_amount',
        'status',              # ✅ ADD
    )

    list_filter = (
        'status',              # ✅ ADD
        'order_date',
    )

    list_editable = (
        'status',              # 🔥 Quick change from list view
    )

    inlines = [OrderItemInline]

    readonly_fields = (
        'total_amount',
        'remaining_amount',
    )

    date_hierarchy = 'order_date'



# ================= STAFF =================

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'designation', 'salary_mode',
        'phone', 'address', 'email', 'is_active'
    )
    list_filter = ('is_active', 'designation', 'salary_mode')
    search_fields = ('name', 'phone', 'email')


# ================= SALARY TRANSACTION =================

@admin.register(SalaryTransaction)
class SalaryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'staff',
        'transaction_type',
        'amount',
        'payment_date',
        'payment_mode',
        'salary_tracker'
    )
    list_filter = ('transaction_type', 'payment_mode', 'payment_date')
    search_fields = ('staff__name',)
    autocomplete_fields = ['staff', 'salary_tracker']


# ================= EXPENSE =================

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'expense_type',
        'amount',
        'expense_date',
        'payment_mode',
        'spent_by',
        'reference_type',
        'reference_id'
    )
    list_filter = ('expense_type', 'payment_mode', 'expense_date')
    search_fields = ('title', 'spent_by__name')


# ================= USER =================

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'is_active',
        'is_staff',
        'is_superuser'
    )
    search_fields = ('username', 'email')


# ================= SALARY TRACKER =================

@admin.register(SalaryTracker)
class SalaryTrackerAdmin(admin.ModelAdmin):
    list_display = (
        'date',
        'staff',
        'total_salary',
        'paid_amount_display',
        'remaining_amount_display',
        'status',
        'payment_mode'
    )
    list_filter = ('status', 'payment_mode', 'date')
    search_fields = ('staff__name',)
    readonly_fields = ('paid_amount_display', 'remaining_amount_display')
    inlines = [SalaryTransactionInline]

    def paid_amount_display(self, obj):
        return obj.transactions.aggregate(
            total=Sum('amount')
        )['total'] or 0
    paid_amount_display.short_description = "Paid Amount"

    def remaining_amount_display(self, obj):
        return obj.total_salary - self.paid_amount_display(obj)
    remaining_amount_display.short_description = "Remaining Amount"

    
@admin.register(BikeSale)
class BikeSaleAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'vehicle_type', 'vehicle_model', 'sale_type',
                    'total_amount', 'discount', 'net_total', 'paid_amount',
                    'remaining_amount', 'emi_tenure', 'emi_amount', 'status', 'sale_date')
    readonly_fields = ('net_total', 'status', 'remaining_amount', 'emi_amount')
    inlines = [EmiTrackerInline]
    search_fields = ('customer_name', 'registration_no', 'vehicle_model')
    list_filter = ('sale_type', 'status', 'vehicle_type', 'sale_date')

    def save_model(self, request, obj, form, change):
        # If new object or downpayment, store initial_paid_amount
        if not change or (obj.sale_type == 'downpayment' and obj.initial_paid_amount == 0):
            obj.initial_paid_amount = obj.paid_amount

        super().save_model(request, obj, form, change)

        # Generate EMI schedule if sale_type is EMI or downpayment
        if obj.is_emi and obj.emi_tenure:
            generate_emi_schedule(obj)

        # Recalculate totals after any changes
        total_emi_paid = obj.emi_details.aggregate(total=Sum('paid_amount'))['total'] or 0
        obj.paid_amount = obj.initial_paid_amount + total_emi_paid
        obj.remaining_amount = max(obj.net_total - obj.paid_amount, 0)
        obj.status = "Paid" if obj.remaining_amount == 0 else "Partially Paid" if obj.paid_amount > 0 else "Pending"
        obj.save(update_fields=['paid_amount', 'remaining_amount', 'status'])


@admin.register(BikeSaleFollowUp)
class BikeSaleFollowUpAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'bike_sale', 'customer_name', 'contact_no', 'vehicle',
        'delivery_date', 'post_service_feedback_date', 'follow_up_date',
        'status'
    )
    list_filter = ('status', 'follow_up_date')
    search_fields = ('customer_name', 'contact_no', 'vehicle', 'bike_sale__vehicle_model')
    readonly_fields = ('status',)