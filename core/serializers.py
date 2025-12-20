from rest_framework import serializers
from django.db import transaction
from .models import (
    Stock, Purchase, PurchaseItem, Sale, SaleItem, FollowUpDashboard,
    Supplier, Technician, Staff, Category, Order, OrderItem, User
)


# ---------------- USER ----------------
class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'is_admin']

    def get_is_admin(self, obj):
        return obj.is_superuser


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


# ---------------- STOCK ----------------
class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            'id', 'item_no', 'name', 'group', 'model', 'category', 'stock',
            'purchase_price', 'sale_price', 'vat', 'image'
        ]


# ---------------- PURCHASE ----------------

# ---------------- PURCHASE ITEM ----------------
class PurchaseItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    total_price = serializers.SerializerMethodField()
    purchase_price = serializers.FloatField(source='price')  # API 'purchase_price' -> model 'price'

    class Meta:
        model = PurchaseItem
        fields = ['item', 'item_name', 'quantity', 'purchase_price', 'total_price', 'vat', 'sale_price']

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

    def calculate_totals(self, items, discount_percentage, vat_percentage):
        # Use 'price' because PurchaseItem model has 'price'
        total_amount = sum([i['price'] * i['quantity'] for i in items])
        discount_amount = total_amount * discount_percentage / 100
        amount_after_discount = total_amount - discount_amount
        vat_amount = amount_after_discount * vat_percentage / 100
        net_amount = amount_after_discount + vat_amount
        return total_amount, discount_amount, amount_after_discount, vat_amount, net_amount

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        discount_percentage = validated_data.pop('discount_percentage', 0)
        vat_percentage = validated_data.pop('vat_percentage', 13)

        total_amount, discount_amount, amount_after_discount, vat_amount, net_amount = self.calculate_totals(
            items_data, discount_percentage, vat_percentage
        )

        # Create purchase
        purchase = Purchase.objects.create(**validated_data)
        purchase.discount_percentage = discount_percentage
        purchase.vat_percentage = vat_percentage
        purchase.total_amount = total_amount
        purchase.discount_amount = discount_amount
        purchase.amount_after_discount = amount_after_discount
        purchase.vat_amount = vat_amount
        purchase.net_amount = net_amount
        purchase.save()

        # Create PurchaseItems
        for item_data in items_data:
            item = item_data['item']
            qty = item_data['quantity']
            purchase_price = item_data['price']
            sale_price = item_data.get('sale_price', item.sale_price)
            vat = item_data.get('vat', item.vat)

            PurchaseItem.objects.create(
                purchase=purchase,
                item=item,
                quantity=qty,
                price=purchase_price,
                sale_price=sale_price,
                vat=vat
            )

            # Update stock and item pricing
            #item.adjust_stock(qty)
            item.purchase_price = purchase_price
            item.sale_price = sale_price
            item.vat = vat
            item.save(update_fields=['purchase_price', 'sale_price', 'vat'])

        return purchase

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        discount_percentage = validated_data.pop('discount_percentage', instance.discount_percentage)
        vat_percentage = validated_data.pop('vat_percentage', instance.vat_percentage)

        # Update purchase basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.discount_percentage = discount_percentage
        instance.vat_percentage = vat_percentage
        instance.save()

        # Map existing items
        old_items = {pi.item.id: pi for pi in instance.items.all()}

        for item_data in items_data:
            item = item_data['item']
            qty = item_data['quantity']
            purchase_price = item_data['price']
            sale_price = item_data.get('sale_price', item.sale_price)
            vat = item_data.get('vat', item.vat)

            if item.id in old_items:
                # Update existing PurchaseItem
                pi = old_items.pop(item.id)
                qty_diff = qty - pi.quantity  # Difference for stock
                pi.quantity = qty
                pi.price = purchase_price
                pi.sale_price = sale_price
                pi.vat = vat
                pi.save()  # Stock adjustment in save()
            else:
                # Create new PurchaseItem
                pi = PurchaseItem.objects.create(
                    purchase=instance,
                    item=item,
                    quantity=qty,
                    price=purchase_price,
                    sale_price=sale_price,
                    vat=vat
                )
                #item.adjust_stock(qty)

            # Update stock pricing
            item.purchase_price = purchase_price
            item.sale_price = sale_price
            item.vat = vat
            item.save(update_fields=['purchase_price', 'sale_price', 'vat'])

        # Remove deleted items
        for removed in old_items.values():
           # removed.item.adjust_stock(-removed.quantity)
            removed.delete()

        # Recalculate totals
        total_amount = sum([pi.quantity * pi.price for pi in instance.items.all()])
        discount_amount = total_amount * discount_percentage / 100
        amount_after_discount = total_amount - discount_amount
        vat_amount = amount_after_discount * vat_percentage / 100
        net_amount = amount_after_discount + vat_amount

        instance.total_amount = total_amount
        instance.discount_amount = discount_amount
        instance.amount_after_discount = amount_after_discount
        instance.vat_amount = vat_amount
        instance.net_amount = net_amount
        instance.save()

        return instance


# ---------------- SALE ----------------
class SaleItemSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['item', 'item_name', 'quantity', 'price', 'total_price']

    def get_total_price(self, obj):
        return obj.quantity * obj.price


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    total_amount = serializers.FloatField(read_only=True)

    class Meta:
        model = Sale
        fields = ['id', 'sale_date', 'customer_name', 'contact_no', 'vehicle_model',
                  'is_servicing', 'total_amount', 'items']

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sale = Sale.objects.create(**validated_data)
        total_amount = 0

        for item_data in items_data:
            si = SaleItem.objects.create(sale=sale, **item_data)
            total_amount += si.quantity * si.price

        sale.total_amount = total_amount
        sale.save()
        return sale

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        old_items = {pi.item.id: pi for pi in instance.items.all()}
        total_amount = 0

        for item_data in items_data:
            item = item_data['item']
            qty = item_data['quantity']
            price = item_data['price']

            if item.id in old_items:
                pi = old_items.pop(item.id)
                pi.quantity = qty
                pi.price = price
                pi.save()  # Stock handled in SaleItem.save()
            else:
                pi = SaleItem.objects.create(sale=instance, **item_data)
            total_amount += qty * price

        # Remove deleted items
        for removed in old_items.values():
            removed.delete()  # Stock restored in SaleItem.delete()

        instance.total_amount = total_amount
        instance.save()
        return instance


# ---------------- FOLLOW-UP DASHBOARD ----------------
class FollowUpDashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpDashboard
        fields = [
            'id', 'sale', 'customer_name', 'contact_no', 'vehicle',
            'delivery_date', 'follow_up_date', 'remarks'
        ]


# ---------------- STAFF CREATION ----------------
class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff']

    def create(self, validated_data):
        validated_data['is_staff'] = True
        return User.objects.create_user(**validated_data)


# ---------------- STAFF ----------------
class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ['id', 'user', 'designation']


# ---------------- TECHNICIAN ----------------
class TechnicianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Technician
        fields = ['id', 'user', 'specialization']


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
    advance = serializers.FloatField()

    class Meta:
        model = Order
        fields = ['id', 'customer_name', 'contact_no', 'vehicle_model', 'order_date', 'items', 'total_amount', 'advance', "remaining_amount"]

    def get_total_amount(self, obj):
        return sum(item.total_price() for item in obj.items.all())

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

    def update(self, instance, validated_data):
        instance.customer_name = validated_data.get('customer_name', instance.customer_name)
        instance.contact_no = validated_data.get('contact_no', instance.contact_no)
        instance.vehicle_model = validated_data.get('vehicle_model', instance.vehicle_model)
        instance.order_date = validated_data.get('order_date', instance.order_date)
        instance.advance = validated_data.get('advance', instance.advance)
        instance.save()

        if 'items' in validated_data:
            items_data = validated_data.pop('items')
            existing_ids = [item.id for item in instance.items.all()]
            new_ids = []

            for item_data in items_data:
                item_id = item_data.get('id', None)
                if item_id and item_id in existing_ids:
                    item = OrderItem.objects.get(id=item_id, order=instance)
                    item.item = item_data.get('item', item.item)
                    item.quantity = item_data.get('quantity', item.quantity)
                    item.rate = item_data.get('rate', item.rate)
                    item.save()
                    new_ids.append(item_id)
                else:
                    new_item = OrderItem.objects.create(order=instance, **item_data)
                    new_ids.append(new_item.id)

            for item in instance.items.all():
                if item.id not in new_ids:
                    item.delete()

        return instance
