from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, F, FloatField
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

from core.permissions import IsAdminOrReadOnlyForStaff
from .models import (
    Supplier, Category, Stock, Purchase, PurchaseItem,
    Sale, SaleItem, FollowUpDashboard, Order, OrderItem,
    Technician, Staff, User
)
from .serializers import (
    UserSerializer, SupplierSerializer, CategorySerializer, StockSerializer,
    PurchaseSerializer, SaleSerializer, FollowUpDashboardSerializer,
    StaffCreateSerializer, StaffSerializer, TechnicianSerializer,
    OrderSerializer
)

# ---------------- USER ----------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnlyForStaff]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.all()
        elif user.is_staff:
            return User.objects.filter(is_staff=False, is_superuser=False)
        return User.objects.none()


# ---------------- SUPPLIER ----------------
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact', 'email']
    ordering_fields = ['name']


# ---------------- CATEGORY ----------------
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


# ---------------- STOCK ----------------
class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.all().order_by('name')
    serializer_class = StockSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'model', 'category__name']
    ordering_fields = ['name', 'stock', 'purchase_price', 'sale_price']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"detail": "Stock item deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


# ---------------- PURCHASE ----------------
class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all().order_by('-date')
    serializer_class = PurchaseSerializer

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        purchase = self.get_object()
        # Reduce stock for all items in this purchase
        for pi in purchase.items.all():
            pi.item.adjust_stock(-pi.quantity)
        return super().destroy(request, *args, **kwargs)


# ---------------- SALE ----------------
# ---------------- SALE ----------------
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.order_by('-sale_date')
    serializer_class = SaleSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        sale = serializer.save()
        # Adjust stock
        for item_data in self.request.data.get('items', []):
            item = Stock.objects.get(id=item_data['item'])
            #item.adjust_stock(-item_data['quantity'])

    @transaction.atomic
    def perform_update(self, serializer):
        old_sale = self.get_object()
        sale = serializer.save()
        # Adjust stock for changed quantities
        old_items = {item.item.id: item.quantity for item in old_sale.items.all()}
        new_items = {int(item['item']): item['quantity'] for item in self.request.data.get('items', [])}

        for item_id, new_qty in new_items.items():
            old_qty = old_items.get(item_id, 0)
            diff = new_qty - old_qty
            if diff != 0:
                Stock.objects.get(id=item_id).adjust_stock(-diff)

        # Restore stock for removed items
        for item_id, old_qty in old_items.items():
            if item_id not in new_items:
                Stock.objects.get(id=item_id).adjust_stock(old_qty)


# ---------------- FOLLOW-UP DASHBOARD ----------------
class FollowUpDashboardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FollowUpDashboard.objects.all().order_by('follow_up_date')
    serializer_class = FollowUpDashboardSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['follow_up_date']


# ---------------- STAFF CREATION ----------------
class StaffCreateView(APIView):
    permission_classes = [IsAdminOrReadOnlyForStaff]

    def post(self, request):
        serializer = StaffCreateSerializer(data=request.data)
        if serializer.is_valid():
            staff_user = serializer.save()
            return Response({
                "id": staff_user.id,
                "username": staff_user.username,
                "email": staff_user.email,
                "is_staff": staff_user.is_staff
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------- DASHBOARD SUMMARY ----------------
@api_view(['GET'])
def dashboard_summary(request):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    last_week = today - timedelta(days=6)

    # Totals
    total_sales_count = Sale.objects.count()
    total_purchases_count = Purchase.objects.count()
    total_categories = Category.objects.count()
    total_suppliers = Supplier.objects.count()
    total_items = Stock.objects.count()

    # Amounts
    total_sales_amount = Sale.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    today_sales_amount = Sale.objects.filter(sale_date__date=today).aggregate(total=Sum('total_amount'))['total'] or 0
    monthly_sales_amount = Sale.objects.filter(sale_date__date__gte=start_of_month).aggregate(total=Sum('total_amount'))['total'] or 0

    total_purchases_amount = PurchaseItem.objects.aggregate(
        total=Sum(F('quantity') * F('price'), output_field=FloatField())
    )['total'] or 0
    today_purchases_amount = PurchaseItem.objects.filter(purchase__date__date=today).aggregate(
        total=Sum(F('quantity') * F('price'), output_field=FloatField())
    )['total'] or 0
    monthly_purchases_amount = PurchaseItem.objects.filter(purchase__date__date__gte=start_of_month).aggregate(
        total=Sum(F('quantity') * F('price'), output_field=FloatField())
    )['total'] or 0

    # Low stock
    stock_threshold = 5
    low_stock_items = Stock.objects.filter(stock__lt=stock_threshold).values('id', 'name', 'stock', 'category__name')

    # Follow-ups
    upcoming_followups = FollowUpDashboard.objects.order_by('follow_up_date').values(
        'id', 'follow_up_date', 'customer_name', 'vehicle', 'remarks'
    )

    # Sales by category
    category_sales = (
        Sale.objects.values('items__item__category__name')
        .annotate(total_sales=Sum('total_amount'))
        .order_by('-total_sales')
    )

    # 7-day chart data
    sales_data = (
        Sale.objects.filter(sale_date__date__gte=last_week)
        .values('sale_date__date')
        .order_by('sale_date__date')
        .annotate(total=Sum('total_amount'))
    )
    purchase_data = (
        PurchaseItem.objects.filter(purchase__date__date__gte=last_week)
        .values('purchase__date__date')
        .order_by('purchase__date__date')
        .annotate(total=Sum(F('quantity') * F('price'), output_field=FloatField()))
    )

    return Response({
        "summary": {
            "sales": {
                "count": total_sales_count,
                "amount": total_sales_amount,
                "today_amount": today_sales_amount,
                "monthly_amount": monthly_sales_amount,
            },
            "purchases": {
                "count": total_purchases_count,
                "amount": total_purchases_amount,
                "today_amount": today_purchases_amount,
                "monthly_amount": monthly_purchases_amount,
            },
            "categories": total_categories,
            "suppliers": total_suppliers,
            "items": total_items,
        },
        "low_stock_items": list(low_stock_items),
        "stock_threshold": stock_threshold,
        "upcoming_followups": list(upcoming_followups),
        "sales_by_category": [
            {"category_name": c['items__item__category__name'], "total_sales": c['total_sales']}
            for c in category_sales
        ],
        "sales_chart": [{"date": s['sale_date__date'], "total": s['total']} for s in sales_data],
        "purchase_chart": [{"date": p['purchase__date__date'], "total": p['total']} for p in purchase_data],
    })


# ---------------- ORDER ----------------
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]  # Does NOT affect stock


# ---------------- TECHNICIAN ----------------
class TechnicianViewSet(viewsets.ModelViewSet):
    queryset = Technician.objects.all()
    serializer_class = TechnicianSerializer


# ---------------- STAFF ----------------
class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
