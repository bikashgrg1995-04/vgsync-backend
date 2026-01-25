from collections import defaultdict
from django.db import transaction
from django.db.models import Sum
from rest_framework import viewsets, filters, status, generics
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend


from core.permissions import IsAdminOrReadOnlyForStaff
from core.services.dashoard.chart_service import get_dashboard_charts
from core.services.dashoard.credit_service import get_credit_summary
from core.services.dashoard.dashboard_followup import get_followups
from core.services.dashoard.dashboard_low_stock import get_low_stock
from core.services.dashoard.dashboard_order import get_orders
from core.services.dashoard.dashboard_staff_salary import get_staff_salaries
from core.services.uploads.order_upload import upload_order_excel
from core.services.uploads.purchase_upload import upload_purchase_excel
from core.services.uploads.sale_upload import upload_sales_excel
from core.services.uploads.stock_upload import upload_stock_excel


from .models import (
    Expense, SalaryTracker, SalaryTransaction, Supplier, Category, Stock,
    Purchase, PurchaseItem,
    Sale, SaleItem,
    FollowUpDashboard,
    Order, OrderItem,
    Staff, User, BikeSale, EmiTracker
)

from .serializers import (
    ExpenseSerializer,
    SalaryTrackerSerializer,
    SalaryTransactionSerializer,
    SaleReadSerializer,
    ServiceSaleReadSerializer,
    ServiceSaleSerializer,
    SupplierSerializer,
    CategorySerializer,
    StockSerializer,
    PurchaseSerializer,
    StockSaleSerializer,
    FollowUpDashboardSerializer,
    StaffSerializer,
    OrderSerializer,
    UserSerializer, BikeSaleSerializer, EmiTrackerSerializer, EmiTrackerUpdateSerializer

)


# ===================== CATEGORY =====================
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


# ===================== PURCHASE =====================
class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all().order_by('-date')
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        purchase = self.get_object()
        purchase.delete()
        return Response({"detail": "Purchase deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

# ===================== SALE =====================
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().order_by('-sale_date')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            data = getattr(self.request, 'data', {})
            if data.get('is_servicing') or data.get('job_card_no'):
                return ServiceSaleSerializer  # for POST/PUT
            return StockSaleSerializer
        # For GET: use read serializers
        sale = None
        if self.action in ['retrieve', 'list']:
            if self.action == 'retrieve':
                sale = self.get_object()
            # If list, we can’t check each, so fallback to SaleReadSerializer for stock, ServiceSaleReadSerializer for servicing
            return SaleReadSerializer
        return StockSaleSerializer

    def list(self, request, *args, **kwargs):
        sales = self.get_queryset()
        data = []
        for sale in sales:
            if sale.is_servicing:
                serializer = ServiceSaleReadSerializer(sale)
            else:
                serializer = SaleReadSerializer(sale)
            data.append(serializer.data)
        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        sale = self.get_object()
        if sale.is_servicing:
            serializer = ServiceSaleReadSerializer(sale)
        else:
            serializer = SaleReadSerializer(sale)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            sale = serializer.save()
        # return full data
        if sale.is_servicing:
            read_serializer = ServiceSaleReadSerializer(sale)
        else:
            read_serializer = SaleReadSerializer(sale)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            sale = serializer.save()
        if sale.is_servicing:
            read_serializer = ServiceSaleReadSerializer(sale)
        else:
            read_serializer = SaleReadSerializer(sale)
        return Response(read_serializer.data)


# ===================== STAFF =====================
class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by('name')
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnlyForStaff]


# ===================== USER =====================
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

# ===================== SUPPLIER =====================
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact', 'email']
    ordering_fields = ['name']

# ===================== CATEGORY =====================
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

# ===================== STOCK =====================
class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.all().order_by('name')
    serializer_class = StockSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'model', 'category__name']
    ordering_fields = ['name', 'stock', 'purchase_price', 'sale_price']

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"detail": "Stock item deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

# ===================== PURCHASE =====================
class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all().order_by('-date')
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        purchase = self.get_object()
        purchase.delete()
        return Response({"detail": "Purchase deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

# ===================== SALE =====================
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().order_by('-sale_date')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            data = getattr(self.request, 'data', {})
            if data.get('is_servicing') or data.get('job_card_no'):
                return ServiceSaleSerializer  # for POST/PUT
            return StockSaleSerializer
        # For GET: use read serializers
        sale = None
        if self.action in ['retrieve', 'list']:
            if self.action == 'retrieve':
                sale = self.get_object()
            # If list, we can’t check each, so fallback to SaleReadSerializer for stock, ServiceSaleReadSerializer for servicing
            return SaleReadSerializer
        return StockSaleSerializer

    def list(self, request, *args, **kwargs):
        sales = self.get_queryset()
        data = []
        for sale in sales:
            if sale.is_servicing:
                serializer = ServiceSaleReadSerializer(sale)
            else:
                serializer = SaleReadSerializer(sale)
            data.append(serializer.data)
        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        sale = self.get_object()
        if sale.is_servicing:
            serializer = ServiceSaleReadSerializer(sale)
        else:
            serializer = SaleReadSerializer(sale)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            sale = serializer.save()
        # return full data
        if sale.is_servicing:
            read_serializer = ServiceSaleReadSerializer(sale)
        else:
            read_serializer = SaleReadSerializer(sale)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            sale = serializer.save()
        if sale.is_servicing:
            read_serializer = ServiceSaleReadSerializer(sale)
        else:
            read_serializer = SaleReadSerializer(sale)
        return Response(read_serializer.data)


# =================================================
# 📊 CHART + CREDIT API
# =================================================
@api_view(["GET"])
def dashboard_charts_api(request):
    period = request.GET.get("period", "monthly")
    return Response(get_dashboard_charts(period))

@api_view(["GET"])
def dashboard_credit_api(request):
    period = request.GET.get("period", "monthly")
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 5))

    data = get_credit_summary(
        period=period,
        page=page,
        page_size=page_size,
    )

    return Response(data)

# =================================================
# 📋 TABLE DATA API
# =================================================
@api_view(["GET"])
def followups_api(request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 5))
    days = int(request.GET.get("days", 10))

    data = get_followups(
        days=days,
        page=page,
        page_size=page_size,
    )

    return Response(data)

@api_view(["GET"])
def low_stock_api(request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 5))
    threshold = int(request.GET.get("threshold", 5))

    data = get_low_stock(
        threshold=threshold,
        page=page,
        page_size=page_size,
    )

    return Response(data)

@api_view(["GET"])
def orders_api(request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 5))

    data = get_orders(
        page=page,
        page_size=page_size,
    )

    return Response(data)


@api_view(["GET"])
def staff_salary_api(request):
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 5))

    data = get_staff_salaries(
        page=page,
        page_size=page_size,
    )

    return Response(data)

# ===================== STAFF =====================
class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by('name')
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnlyForStaff]

class FollowUpDashboardViewSet(viewsets.ModelViewSet):
    queryset = FollowUpDashboard.objects.all()
    serializer_class = FollowUpDashboardSerializer

    @action(detail=True, methods=['post'], url_path='terminate')
    def terminate_followup(self, request, pk=None):
        """Terminate a follow-up with optional reason"""
        followup = self.get_object()
        reason = request.data.get('reason')
        followup.terminate(reason=reason)
        serializer = self.get_serializer(followup)
        return Response(serializer.data, status=status.HTTP_200_OK)

# ===================== ORDER =====================
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

# ===================== SALARY =====================
class SalaryTrackerViewSet(viewsets.ModelViewSet):
    queryset = SalaryTracker.objects.all()
    serializer_class = SalaryTrackerSerializer
    permission_classes = [IsAuthenticated]

class SalaryTransactionViewSet(viewsets.ModelViewSet):
    queryset = SalaryTransaction.objects.all()
    serializer_class = SalaryTransactionSerializer
    permission_classes = [IsAuthenticated]

# ===================== EXPENSE =====================
class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

# ===================== ORDER =====================
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

# ===================== SALARY =====================
class SalaryTrackerViewSet(viewsets.ModelViewSet):
    queryset = SalaryTracker.objects.all()
    serializer_class = SalaryTrackerSerializer
    permission_classes = [IsAuthenticated]

class SalaryTransactionViewSet(viewsets.ModelViewSet):
    queryset = SalaryTransaction.objects.all()
    serializer_class = SalaryTransactionSerializer
    permission_classes = [IsAuthenticated]

# ===================== EXPENSE =====================
class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_excel_upload_api(request):
    file = request.FILES.get("file")
    if not file:
        return Response({"error": "Excel file required"}, status=400)
    return Response(upload_purchase_excel(file, request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sale_excel_upload_api(request):
    file = request.FILES.get("file")
    if not file:
        return Response({"error": "Excel file required"}, status=400)
    return Response(upload_sales_excel(file))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stock_excel_upload_api(request):
    file = request.FILES.get("file")
    if not file:
        return Response({"error": "Excel file required"}, status=400)
    return Response(upload_stock_excel(file))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_excel_upload_api(request):
    file = request.FILES.get("file")
    if not file:
        return Response({"error": "Excel file required"}, status=400)
    return Response(upload_order_excel(file))


# ----------------- BikeSale CRUD -----------------
class BikeSaleViewSet(viewsets.ModelViewSet):
    queryset = BikeSale.objects.all().order_by('-sale_date')
    serializer_class = BikeSaleSerializer

    def create(self, request, *args, **kwargs):
        """
        Automatically reject EMI tracker creation if sale_type is not EMI
        """
        sale_type = request.data.get('sale_type')
        response = super().create(request, *args, **kwargs)
        if sale_type == 'emi':
            # Optionally: create EMI schedule automatically here
            pass
        return response

# ----------------- EMI Tracker CRUD -----------------
class EmiTrackerViewSet(viewsets.ModelViewSet):
    queryset = EmiTracker.objects.all().order_by('installment_no')
    serializer_class = EmiTrackerSerializer

    def create(self, request, *args, **kwargs):
        # Ensure only EMI sales can have EMI trackers
        sale_id = request.data.get('sale')
        sale = BikeSale.objects.get(id=sale_id)
        if sale.sale_type != 'emi':
            return Response(
                {"error": "EMI tracker can only be created for EMI sales."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)



class EmiTrackerUpdateAPIView(generics.UpdateAPIView):
    queryset = EmiTracker.objects.all()
    serializer_class = EmiTrackerUpdateSerializer
    lookup_field = 'id'  # frontend sends the EMI id