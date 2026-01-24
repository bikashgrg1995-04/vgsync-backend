from rest_framework import serializers
from django.db import transaction
from datetime import date, timedelta

from core.services.utils import extract_item_no, recalc_sale_totals


from .models import (
    Expense, SalaryTracker, SalaryTransaction, Stock, Purchase, PurchaseItem, Sale, SaleItem, FollowUpDashboard,
    Supplier, Staff, Category, Order, OrderItem, User
)


# ---------------- USER ----------------
class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'is_superuser', 'is_admin']

    def get_is_admin(self, obj):
        return obj.is_superuser


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff', 'is_superuser']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


# ---------------- SUPPLIER ----------------
class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'contact', 'address', 'email']


# ---------------- CATEGORY ----------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']
class StaffSerializer(serializers.ModelSerializer):
    designation_display = serializers.CharField(source='get_designation_display', read_only=True)
    salary_mode_display = serializers.CharField(source='get_salary_mode_display', read_only=True)

    class Meta:
        model = Staff
        fields = [
            'id',
            'name',
            'phone',          # model field
            'email',
            'address',
            'designation',
            'designation_display',
            'salary_mode',
            'salary_mode_display',
            'joined_date',
            'is_active',
        ]
        read_only_fields = []

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Staff name cannot be empty")
        return value

    def validate_phone(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("Phone must be numeric")
        return value




# ---------------- STOCK ----------------
class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = '__all__'


# ---------------- PURCHASE ITEM ----------------
class PurchaseItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    class Meta:
        model = PurchaseItem
        fields = ('id', 'item', 'item_name', 'quantity', 'price')


# ---------------- PURCHASE ----------------
class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)

    class Meta:
        model = Purchase
        fields = (
            'id', 'supplier', 'date', 'created_by',
            'grand_total', 'discount_amount', 'net_total',
            'paid_amount', 'remaining_amount', 'status',
            'is_migrated',  # migration flag
            'items',
        )

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        purchase = Purchase.objects.create(**validated_data)

        for item_data in items_data:
            PurchaseItem.objects.create(purchase=purchase, **item_data)

        # ✅ NO need to call sync_purchase_expense manually
        # Signal will handle expense creation automatically

        return purchase

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        # Update main purchase fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()  # ✅ Signal will trigger automatically

        # Update items only if provided (PATCH safe)
        if items_data is not None:
            # Delete old items
            instance.items.all().delete()
            # Create new items
            for item_data in items_data:
                PurchaseItem.objects.create(purchase=instance, **item_data)

        # ✅ NO need to call sync_purchase_expense manually

        return instance


# ---------------- SALE ITEM ----------------
class SaleItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    category_name = serializers.CharField(source='item.category.name', read_only=True)
    sale_price = serializers.FloatField(required=False, default=0)

    class Meta:
        model = SaleItem
        fields = ['id', 'item', 'item_name', 'category_name', 'quantity', 'sale_price', 'total_price']
        read_only_fields = ['total_price']

    def to_internal_value(self, data):
        if 'price' in data:
            data['sale_price'] = data.pop('price')
        return super().to_internal_value(data)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def create(self, validated_data):
        validated_data['total_price'] = validated_data['quantity'] * validated_data['sale_price']
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.sale_price = validated_data.get('sale_price', instance.sale_price)
        instance.total_price = instance.quantity * instance.sale_price
        instance.save()
        return instance
    
class SaleItemReadSerializer(SaleItemSerializer):
    class Meta(SaleItemSerializer.Meta):
        read_only_fields = SaleItemSerializer.Meta.fields

# ---------------- SALE ----------------
class SaleReadSerializer(serializers.ModelSerializer):
    items = SaleItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'sale_date', 'customer_name', 'contact_no',  'bill_no',
            'handled_by', 'is_servicing',

            # totals
            'grand_total', 'discount_percentage', 'discount_amount', 'net_total',
            'paid_amount', 'remaining_amount', 'is_paid',

            'items'
        ]


# ---------------- SALE ITEM ----------------
class SaleItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    category_name = serializers.CharField(source='item.category.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'item', 'item_name', 'category_name', 'quantity', 'sale_price', 'total_price']

    def create(self, validated_data):
        # frontend already calculates total_price
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.sale_price = validated_data.get('sale_price', instance.sale_price)
        instance.total_price = validated_data.get('total_price', instance.total_price)
        instance.save()
        return instance


# ---------------- STOCK SALE ----------------
class StockSaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)

    class Meta:
        model = Sale
        sale_ref = serializers.ReadOnlyField()

        fields = [
            'id', 'sale_date', 'customer_name', 'contact_no',
            'bill_no', 'remarks',
            'grand_total', 'discount_percentage', 'discount_amount',
            'net_total',
            'paid_amount', 'remaining_amount', 'is_paid', 'paid_from',
            'handled_by', 'items'
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sale = Sale.objects.create(**validated_data)

        for item in items_data:
            SaleItem.objects.create(
                sale=sale,
                item=item['item'],
                quantity=item['quantity'],
                sale_price=item['sale_price'],
                total_price=item.get('total_price', item['quantity'] * item['sale_price'])
            )

        return sale

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                SaleItem.objects.create(
                    sale=instance,
                    item=item['item'],
                    quantity=item['quantity'],
                    sale_price=item['sale_price'],
                    total_price=item.get('total_price', item['quantity'] * item['sale_price'])
                )

        return instance

class ServiceSaleReadSerializer(serializers.ModelSerializer):
    items = SaleItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'sale_date', 'customer_name', 'contact_no', 'handled_by', 'bill_no', 'remarks',
            'is_servicing',
            # Service fields
            'vehicle_model', 'job_card_no', 'bike_registration_no', 'vehicle_type','vehicle_color', 'km_driven',
            'labour_charge', 'is_free_servicing', 'is_repair_job', 'is_accident', 'is_warranty_job', 'job_done_on_vehicle', 'technician_name',
            'received_date', 'delivery_date', 'follow_up_date', 'post_service_feedback_date',

            # totals
            'grand_total', 'discount_percentage', 'discount_amount',
            'net_total', 'paid_amount', 'remaining_amount', 'is_paid',

            'items'
        ]

# ---------------- SERVICE SALE ----------------
class ServiceSaleSerializer(StockSaleSerializer):
    class Meta(StockSaleSerializer.Meta):
        fields = StockSaleSerializer.Meta.fields + [
            'vehicle_model',
            'job_card_no',
            'bike_registration_no',
            'vehicle_type',
            'vehicle_color',
            'km_driven',
            'labour_charge',
            'is_free_servicing',
            'is_repair_job',
            'is_accident',
            'is_warranty_job',
            'job_done_on_vehicle', 
            'technician_name',
            'received_date',
            'delivery_date',
            'follow_up_date',
            'post_service_feedback_date'
        ]

    def create(self, validated_data):
        validated_data['is_servicing'] = True
        return super().create(validated_data)



# ---------------- FOLLOW-UP DASHBOARD ----------------
class FollowUpDashboardSerializer(serializers.ModelSerializer):
    sale = SaleReadSerializer(read_only=True)  # Sale nested view
    assigned_to = serializers.StringRelatedField()  # Staff name

    class Meta:
        model = FollowUpDashboard
        fields = [
            'id', 'sale', 'customer_name', 'contact_no', 'vehicle',
            'delivery_date', 'post_service_feedback_date', 'follow_up_date',
            'remarks', 'assigned_to', 'status', 'reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'reason', 'created_at', 'sale']



# ---------------- SALARY ----------------
class SalaryTrackerSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.name', read_only=True)

    class Meta:
        model = SalaryTracker
        fields = [
            'id', 'staff', 'staff_name', 'date',
            'total_salary', 'paid_amount', 'remaining_amount',
            'status', 'payment_mode'
        ]
        read_only_fields = ['remaining_amount', 'status']


class SalaryTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryTransaction
        fields = '__all__'


# ---------------- EXPENSE ----------------
class ExpenseSerializer(serializers.ModelSerializer):
    expense_date = serializers.DateField(format="%Y-%m-%d")

    class Meta:
        model = Expense
        fields = [
            'id',
            'expense_date',
            'title',
            'expense_type',
            'amount',    
            'payment_mode',
            'reference_type',
            'reference_id',
            'note',
            'spent_by',
            'created_at',
        ]
        read_only_fields = ['remaining_amount', 'status', 'created_at']

# ---------------- ORDER ----------------
class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'item', 'quantity', 'rate', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price()


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, required=False)

    total_amount = serializers.SerializerMethodField(read_only=True)
    remaining_amount = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer_name', 'contact_no',
            'vehicle_model', 'order_date',
            'items', 'total_amount',
            'advance', 'remaining_amount', 'status',
        ]

    def get_total_amount(self, obj):
        return sum(i.total_price() for i in obj.items.all())

    def get_remaining_amount(self, obj):
        return max(self.get_total_amount(obj) - obj.advance, 0)

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        status = validated_data.get('status')
        if status and status not in dict(Order.STATUS_CHOICES):
            raise serializers.ValidationError({"status": "Invalid status"})

        items_data = validated_data.pop('items', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            existing_items = {item.id: item for item in instance.items.all()}
            for item_data in items_data:
                item_id = item_data.get('id')
                if item_id and item_id in existing_items:
                    oi = existing_items.pop(item_id)
                    oi.item = item_data.get('item', oi.item)
                    oi.quantity = item_data.get('quantity', oi.quantity)
                    oi.rate = item_data.get('rate', oi.rate)
                    oi.save()
                else:
                    OrderItem.objects.create(order=instance, **item_data)
            for removed_item in existing_items.values():
                removed_item.delete()

        return instance


# ---------------- ORDER EXCEL ROW ----------------
class OrderExcelRowSerializer(serializers.Serializer):
    order_ref = serializers.CharField()
    customer_name = serializers.CharField()
    contact_no = serializers.CharField(required=False, allow_blank=True)
    vehicle_model = serializers.CharField(required=False, allow_blank=True)
    order_date = serializers.DateTimeField()
    advance = serializers.FloatField(default=0)
    item_no = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    rate = serializers.FloatField(min_value=0)

    def validate_item_no(self, value):
        item_no = extract_item_no(value).strip()
        try:
            stock = Stock.objects.get(item_no__iexact=item_no)
            return stock
        except Stock.DoesNotExist:
            raise serializers.ValidationError(f"Stock with item_no '{item_no}' does not exist")
