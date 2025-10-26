from rest_framework import serializers
from django.db import transaction
from datetime import timedelta
from django.utils import timezone
from .models import Sale, SaleItem, FollowUp, Supplier, Customer, Category, Item, Purchase, PurchaseItem, User

FOLLOW_UP_INTERVAL_DAYS = 30


class UserSerializer(serializers.ModelSerializer):
    # Add a read-only field to indicate admin
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'is_admin']

    def get_is_admin(self, obj):
        return obj.is_superuser  # True for superuser/admin, False otherwise
        
# ---------------- CORE SERIALIZERS ----------------

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = '__all__'

# ------------------ PURCHASE ------------------

class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = ['item', 'quantity', 'price', 'total_price']

class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)
    date = serializers.DateTimeField(required=False)  # optional from frontend

    class Meta:
        model = Purchase
        fields = ['id', 'supplier', 'date', 'items', 'total_amount']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        purchase = Purchase.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseItem.objects.create(purchase=purchase, **item_data)
        return purchase

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        instance.supplier = validated_data.get('supplier', instance.supplier)
        instance.date = validated_data.get('date', instance.date)
        instance.save()

        # Replace existing items
        instance.items.all().delete()
        for item_data in items_data:
            PurchaseItem.objects.create(purchase=instance, **item_data)
        return instance

# ------------------ SALES ------------------

class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ['item', 'quantity', 'price', 'total_price']

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    sale_date = serializers.DateTimeField(required=False)  # optional from frontend

    class Meta:
        model = Sale
        fields = ['id', 'customer', 'sale_date', 'items', 'is_servicing', 'total_amount']
        read_only_fields = ['sale_date', 'total_amount']

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sale = Sale.objects.create(**validated_data)

        # Create SaleItems
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)

        # Calculate total_amount
        sale.total_amount = sum(item.total_price() for item in sale.items.all())
        sale.save(update_fields=['total_amount'])

        return sale

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        instance.customer = validated_data.get('customer', instance.customer)
        instance.is_servicing = validated_data.get('is_servicing', instance.is_servicing)
        instance.sale_date = validated_data.get('sale_date', instance.sale_date)
        instance.save()

        # Delete old SaleItems
        instance.items.all().delete()

        # Add new SaleItems
        for item_data in items_data:
            SaleItem.objects.create(sale=instance, **item_data)

        # Recalculate total_amount
        instance.total_amount = sum(item.total_price() for item in instance.items.all())
        instance.save(update_fields=['total_amount'])

        return instance


class FollowUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUp
        fields = ['id', 'sale', 'service_date', 'follow_up_date', 'completed', 'remarks']
        read_only_fields = ['service_date', 'follow_up_date', 'completed']


class StaffCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_staff']

    def create(self, validated_data):
        # Always make new user staff
        validated_data['is_staff'] = True
        user = User.objects.create_user(**validated_data)
        return user
