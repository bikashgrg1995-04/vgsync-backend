from django.utils import timezone
from django.db.models import Sum, F, FloatField
from django.db import transaction

from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import IsAdminOrReadOnlyForStaff
from .models import (
    Supplier, Category, Stock, Purchase, PurchaseItem,
    Sale, SaleItem, FollowUpDashboard,
    Order, OrderItem, Staff, User
)
from .serializers import (
    SupplierSerializer, CategorySerializer, StockSerializer,
    PurchaseSerializer, StockSaleSerializer, ServiceSaleSerializer,
        FollowUpDashboardSerializer,
    StaffSerializer, OrderSerializer, UserSerializer
)
from rest_framework.decorators import action


# =====================================================
# USER
# =====================================================
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


# =====================================================
# SUPPLIER
# =====================================================
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact', 'email']
    ordering_fields = ['name']


# =====================================================
# CATEGORY
# =====================================================
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


# =====================================================
# STOCK
# =====================================================
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
        return Response(
            {"detail": "Stock item deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


# =====================================================
# PURCHASE
# =====================================================
class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all().order_by('-date')
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Purchase deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


# =====================================================
# SALE
# =====================================================
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().order_by('-sale_date')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['is_servicing', 'sale_date', 'customer_name']
    search_fields = ['customer_name', 'bill_no']
    ordering_fields = ['sale_date', 'total_amount']

    def get_serializer_class(self):
    # ---------- READ ----------
        if self.action in ['list', 'retrieve']:
            # Decide based on object (retrieve) or query (list)
            if self.action == 'retrieve':
                sale = self.get_object()
                if sale.is_servicing:
                    return ServiceSaleSerializer
                return StockSaleSerializer

            # list: return FULL serializer so mixed data works
            return ServiceSaleSerializer

        # ---------- WRITE ----------
        if self.action in ['create', 'update', 'partial_update']:
            is_servicing = self.request.data.get('is_servicing', False)
            if str(is_servicing).lower() in ['true', '1']:
                return ServiceSaleSerializer
            return StockSaleSerializer

        return StockSaleSerializer


    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update sale.
        Stock & follow-up handled by signals.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated_sale = serializer.save()
        return Response(self.get_serializer(updated_sale).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete sale.
        Stock restore & follow-up delete handled by signals.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Sale deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )
    
# ---------------- STOCK SALE ----------------
class StockSaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.filter(is_servicing=False)  # Only stock sales
    serializer_class = StockSaleSerializer

# ---------------- SERVICING SALE ----------------
class ServiceSaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.filter(is_servicing=True)  # Only servicing sales
    serializer_class = ServiceSaleSerializer


# =====================================================
# FOLLOW-UP DASHBOARD
# =====================================================
class FollowUpDashboardViewSet(viewsets.ModelViewSet):
    queryset = FollowUpDashboard.objects.all()
    serializer_class = FollowUpDashboardSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['follow_up_date']

    @action(detail=True, methods=["post"])
    def terminate(self, request, pk=None):
        """
        Terminate a follow-up so it stops showing in dashboard.
        Optional: provide a reason in POST data.
        """
        followup = self.get_object()
        if followup.status == "terminated":
            return Response({"detail": "Follow-up already terminated"}, status=status.HTTP_400_BAD_REQUEST)

        reason: str | None = request.data.get("reason", None)  # <-- get reason safely
        followup.terminate(reason=reason)

        return Response({"detail": "Follow-up terminated successfully"}, status=status.HTTP_200_OK)


# =====================================================
# STAFF
# =====================================================
class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by('name')
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnlyForStaff]


# =====================================================
# DASHBOARD SUMMARY
# =====================================================
@api_view(['GET'])
def dashboard_summary(request):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    total_sales_count = Sale.objects.count()
    total_purchases_count = Purchase.objects.count()
    total_categories = Category.objects.count()
    total_suppliers = Supplier.objects.count()
    total_items = Stock.objects.count()

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

    stock_threshold = 5
    low_stock_items = Stock.objects.filter(stock__lt=stock_threshold).values('id', 'name', 'stock', 'category__name')

    upcoming_followups = FollowUpDashboard.objects.filter(status="pending").order_by("follow_up_date").values(
        "id", "customer_name", "vehicle", "follow_up_date", "remarks", "created_at", 'updated_at'
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
    })


# =====================================================
# ORDER
# =====================================================
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
