from rest_framework import serializers
from django.db import transaction
from datetime import date, timedelta
from .models import (
    Stock, Purchase, PurchaseItem, Sale, SaleItem, FollowUpDashboard,
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


# ---------------- SALE ITEM ----------------
class SaleItemSerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField(source='item.name')
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['id', 'item', 'item_name', 'quantity', 'price', 'total_price']

    def get_total_price(self, obj):
        return obj.quantity * obj.price

# ---------------- STOCK ----------------
class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            'id', 'item_no', 'name', 'group', 'model', 'category', 'stock',
            'purchase_price', 'sale_price', 'vat', 'image'
        ]


# ---------------- PURCHASE ITEM ----------------
class PurchaseItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    purchase_price = serializers.FloatField(source='price')
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseItem
        fields = [
            'item', 'item_name', 'quantity',
            'purchase_price', 'sale_price', 'vat', 'total_price'
        ]

    def get_total_price(self, obj):
        return obj.quantity * obj.price


# ---------------- PURCHASE ----------------
class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)
    
    total_amount = serializers.FloatField(read_only=True)
    discount_amount = serializers.FloatField(read_only=True)
    amount_after_discount = serializers.FloatField(read_only=True)
    vat_amount = serializers.FloatField(read_only=True)
    net_amount = serializers.FloatField(read_only=True)

    class Meta:
        model = Purchase
        fields = [
            'id', 'supplier', 'date', 'items', 'total_amount', 'discount_percentage',
            'discount_amount', 'amount_after_discount', 'vat_percentage',
            'vat_amount', 'net_amount'
        ]

    def _calculate_totals(self, items, discount, vat):
        total = sum(i['quantity'] * i['price'] for i in items)
        discount_amount = total * discount / 100
        after_discount = total - discount_amount
        vat_amount = after_discount * vat / 100
        net = after_discount + vat_amount
        return total, discount_amount, after_discount, vat_amount, net

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        purchase = Purchase.objects.create(**validated_data)
        total, d_amt, after_d, vat_amt, net = self._calculate_totals(
            items_data, purchase.discount_percentage, purchase.vat_percentage
        )
        for item in items_data:
            PurchaseItem.objects.create(purchase=purchase, **item)
            stock = item['item']
            stock.purchase_price = item['price']
            stock.sale_price = item.get('sale_price', stock.sale_price)
            stock.vat = item.get('vat', stock.vat)
            stock.save(update_fields=['purchase_price', 'sale_price', 'vat'])

        purchase.total_amount = total
        purchase.discount_amount = d_amt
        purchase.amount_after_discount = after_d
        purchase.vat_amount = vat_amt
        purchase.net_amount = net
        purchase.save()
        return purchase

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        old_items = {i.item_id: i for i in instance.items.all()}
        for item in items_data:
            stock = item['item']
            if stock.id in old_items:
                pi = old_items.pop(stock.id)
                pi.quantity = item['quantity']
                pi.price = item['price']
                pi.sale_price = item.get('sale_price', pi.sale_price)
                pi.vat = item.get('vat', pi.vat)
                pi.save()
            else:
                PurchaseItem.objects.create(purchase=instance, **item)
            stock.purchase_price = item['price']
            stock.sale_price = item.get('sale_price', stock.sale_price)
            stock.vat = item.get('vat', stock.vat)
            stock.save(update_fields=['purchase_price', 'sale_price', 'vat'])

        for removed in old_items.values():
            removed.delete()

        total, d_amt, after_d, vat_amt, net = self._calculate_totals(
            [{'quantity': i.quantity, 'price': i.price} for i in instance.items.all()],
            instance.discount_percentage,
            instance.vat_percentage
        )
        instance.total_amount = total
        instance.discount_amount = d_amt
        instance.amount_after_discount = after_d
        instance.vat_amount = vat_amt
        instance.net_amount = net
        instance.save()
        return instance

# class SaleReadSerializer(serializers.ModelSerializer):
#     items = SaleItemSerializer(many=True, read_only=True)

#     class Meta:
#         model = Sale
#         fields = [
#             # ---- common ----
#             'id',
#             'sale_date',
#             'customer_name',
#             'contact_no',
#             'vehicle_model',
#             'is_servicing',
#             'bill_no',
#             'technician_name',
#             'remarks',
#             'paid_amount',
#             'remaining_amount',
#             'total_amount',
#             'is_paid',
#             'paid_from',
#             'handled_by',
#             'items',
#             'labour_charge',
#             'received_date',
#             'delivery_date',

#             # ---- service fields ----
#             'follow_up_date',
#             'post_service_feedback_date',
#             'job_card_no',
#             'bike_registration_no',
#             'vehicle_color',
#             'km_driven',
#             'is_free_servicing',
#             'is_repair_job',
#             'is_accident',
#             'is_warranty_job',
#             'job_done_on_vehicle',
#         ]

#     def to_representation(self, instance):
#         data = super().to_representation(instance)

#         # ❌ hide service fields for stock sale
#         if not instance.is_servicing:
#             service_fields = [
#                 'follow_up_date',
#                 'post_service_feedback_date',
#                 'job_card_no',
#                 'bike_registration_no',
#                 'vehicle_color',
#                 'km_driven',
#                 'is_free_servicing',
#                 'is_repair_job',
#                 'is_accident',
#                 'is_warranty_job',
#                 'job_done_on_vehicle',
#                 'received_date',
#                 'delivery_date',
#             ]
#             for field in service_fields:
#                 data.pop(field, None)

#         return data

# ------------------ Stock Sale Serializer ------------------
class StockSaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    total_amount = serializers.FloatField(read_only=True)
    remaining_amount = serializers.FloatField(read_only=True)
    is_paid = serializers.CharField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'sale_date', 'customer_name', 'contact_no', 'vehicle_model',
            'is_servicing', 'bill_no', 'technician_name', 'remarks',
            'paid_amount', 'remaining_amount', 'is_paid', 'paid_from',
            'handled_by', 'items', 'labour_charge'
        ]

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        paid_amount = validated_data.pop('paid_amount', 0)

        sale = Sale.objects.create(**validated_data)
        sale.paid_amount = paid_amount

        total = 0
        for item_data in items_data:
            sale_item = SaleItem.objects.create(sale=sale, **item_data)
            total += sale_item.total_price()
            stock = sale_item.item
            stock.stock = max(stock.stock - sale_item.quantity, 0)
            stock.save(update_fields=['stock'])

        sale.total_amount = total + (sale.labour_charge or 0)
        sale.update_payment_status()
        sale.save()
        return sale

    @transaction.atomic
    def update(self, instance, validated_data):
        # Only update payment
        new_payment = validated_data.get('paid_amount', 0)
        paid_from = validated_data.get('paid_from', None)

        if new_payment:
            instance.paid_amount += new_payment
        if paid_from:
            instance.paid_from = paid_from

        instance.update_payment_status()
        instance.save()
        return instance


# ---------------- STAFF ----------------
class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = '__all__'


# ---------------- ORDER ----------------
class OrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'item', 'quantity', 'rate', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price()


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'customer_name', 'contact_no',
            'vehicle_model', 'order_date',
            'items', 'total_amount', 'advance', 'remaining_amount'
        ]

    def get_total_amount(self, obj):
        return sum(i.total_price() for i in obj.items.all())

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        for item in items:
            OrderItem.objects.create(order=order, **item)
        return order
    

    from rest_framework import serializers





# ------------------ Stock Sale Serializer ------------------
class StockSaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    total_amount = serializers.FloatField(read_only=True)
    remaining_amount = serializers.FloatField(read_only=True)
    is_paid = serializers.SerializerMethodField()  # ✅ fixed

    class Meta:
        model = Sale
        fields = [
            'id', 'sale_date', 'customer_name', 'contact_no',
            'is_servicing', 'bill_no', 'remarks',
            'paid_amount', 'remaining_amount', 'total_amount', 'is_paid', 'paid_from',
            'handled_by', 'items', 'labour_charge'
        ]

    def get_is_paid(self, obj):
        """Return payment status as string"""
        if obj.paid_amount >= (obj.total_amount or 0):
            return 'paid'
        elif obj.paid_amount > 0:
            return 'partial'
        else:
            return 'not_paid'

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        paid_amount = validated_data.pop('paid_amount', 0)

        sale = Sale.objects.create(**validated_data)
        sale.paid_amount = paid_amount

        total = 0
        for item_data in items_data:
            sale_item = SaleItem.objects.create(sale=sale, **item_data)
            total += sale_item.total_price()
            stock = sale_item.item
            stock.stock = max(stock.stock - sale_item.quantity, 0)
            stock.save(update_fields=['stock'])

        sale.total_amount = total + (sale.labour_charge or 0)
        sale.remaining_amount = max(sale.total_amount - sale.paid_amount, 0)
        sale.save()
        return sale

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        new_paid_amount = validated_data.get('paid_amount', None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update nested SaleItems
        if items_data is not None:
            existing_items = {item.id: item for item in instance.items.all()}

            for item_data in items_data:
                item_id = item_data.get('id', None)
                if item_id and item_id in existing_items:
                    # Update existing item
                    sale_item = existing_items.pop(item_id)
                    sale_item.quantity = item_data.get('quantity', sale_item.quantity)
                    sale_item.price = item_data.get('price', sale_item.price)
                    sale_item.save()
                else:
                    # Create new item
                    SaleItem.objects.create(sale=instance, **item_data)

            # Delete removed items
            for removed_item in existing_items.values():
                removed_item.delete()

        # Update payment if provided
        if new_paid_amount is not None:
            instance.paid_amount = new_paid_amount

        # Recalculate totals
        total = sum(item.quantity * item.price for item in instance.items.all())
        instance.total_amount = total + (instance.labour_charge or 0)
        instance.remaining_amount = max(instance.total_amount - (instance.paid_amount or 0), 0)
        instance.save()
        return instance


# ------------------ Service Sale Serializer ------------------
class ServiceSaleSerializer(StockSaleSerializer):
    follow_up_date = serializers.DateField(read_only=True)
    post_service_feedback_date = serializers.DateField(read_only=True)

    class Meta(StockSaleSerializer.Meta):
# include all fields you want in API
        fields = StockSaleSerializer.Meta.fields + [
            
            'job_card_no',
            'bike_registration_no',
            'vehicle_color',
            'km_driven',
            'is_free_servicing',
            'is_repair_job',
            'is_accident',
            'is_warranty_job',
            'job_done_on_vehicle',
            'received_date',
            'delivery_date',
            'follow_up_date',
            'post_service_feedback_date',
        ]

    @transaction.atomic
    def create(self, validated_data):
        sale = super().create(validated_data)
        if sale.delivery_date:
            sale.follow_up_date = sale.delivery_date + timedelta(days=30)
            sale.post_service_feedback_date = sale.delivery_date + timedelta(days=3)
            sale.save(update_fields=['follow_up_date', 'post_service_feedback_date'])
        return sale

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if instance.delivery_date:
            instance.follow_up_date = instance.delivery_date + timedelta(days=30)
            instance.post_service_feedback_date = instance.delivery_date + timedelta(days=3)
            instance.save(update_fields=['follow_up_date', 'post_service_feedback_date'])
        return instance


# ---------------- FOLLOW-UP DASHBOARD ----------------
class FollowUpDashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpDashboard
        fields = [
            'id',
            'sale',  # optional, link to sale
            'customer_name',
            'contact_no',
            'vehicle',
            'delivery_date',
            'post_service_feedback_date',
            'follow_up_date',
            'remarks',
            'assigned_to',
            'status',      # added
            'reason',      # added termination reason
            'created_at',  # optional, for dashboard display
            'updated_at'
        ]
        read_only_fields = ['status', 'reason', 'created_at']

