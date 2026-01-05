from collections import defaultdict
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

import openpyxl
import pandas as pd
from django.utils.dateparse import parse_date

from core.permissions import IsAdminOrReadOnlyForStaff
from core.services.dashboard_overview import full_dashboard_service
from core.services.purchase_upload import upload_purchase_excel
from core.services.sale_upload import upload_sales_excel
from core.services.utils import extract_item_no

from .models import (
    Expense, SalaryTracker, SalaryTransaction, Supplier, Category, Stock,
    Purchase, PurchaseItem,
    Sale, SaleItem,
    FollowUpDashboard,
    Order, OrderItem,
    Staff, User
)

from .serializers import (
    ExpenseSerializer,
    OrderExcelRowSerializer,
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
    UserSerializer
)

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


# ===================== FOLLOW-UP DASHBOARD =====================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def full_dashboard(request):
    period = request.query_params.get('period', 'monthly')
    data = full_dashboard_service(period)
    return Response(data)

# ===================== STAFF =====================
class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by('name')
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnlyForStaff]

class FollowUpDashboardViewSet(viewsets.ModelViewSet):
    queryset = FollowUpDashboard.objects.all()
    serializer_class = FollowUpDashboardSerializer


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

# ===================== EXCEL HELPERS =====================
def parse_excel_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        return parse_date(value)
    return pd.to_datetime(value).date()

# ===================== STOCK EXCEL UPLOAD =====================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stock_excel_upload(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"error": "No file uploaded"}, status=400)

    try:
        df = pd.read_excel(file)
    except Exception as e:
        return Response({"error": f"Invalid Excel file: {str(e)}"}, status=400)

    required_columns = ['item_no', 'name', 'category', 'model', 'purchase_price', 'sale_price', 'stock']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        return Response({"error": f"Missing columns: {', '.join(missing_cols)}"}, status=400)

    created, updated, errors = [], [], []

    for idx, row in df.iterrows():
        try:
            with transaction.atomic():
                category, _ = Category.objects.get_or_create(name=str(row['category']).strip())
                stock_defaults = {
                    'name': str(row['name']).strip(),
                    'category': category,
                    'model': str(row['model']).strip(),
                    'purchase_price': float(row['purchase_price']),
                    'sale_price': float(row['sale_price']),
                    'stock': int(row['stock'])
                }
                stock, created_flag = Stock.objects.update_or_create(
                    item_no=str(row['item_no']).strip(),
                    defaults=stock_defaults
                )
                (created if created_flag else updated).append(stock.item_no)
        except Exception as e:
            errors.append({"row": idx + 2, "error": str(e)})

    return Response({"created": created, "updated": updated, "errors": errors})

# ===================== ORDER EXCEL UPLOAD =====================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_excel_upload(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"detail": "Excel file is required"}, status=400)

    wb = openpyxl.load_workbook(file)
    sheet = wb.active
    grouped_rows, row_errors = defaultdict(list), []

    for row_no, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        data = {
            "order_ref": row[0],
            "customer_name": row[1],
            "contact_no": row[2],
            "vehicle_model": row[3],
            "order_date": row[4],
            "advance": row[5] or 0,
            "item_no": row[6],
            "quantity": row[7],
            "rate": row[8],
        }
        serializer = OrderExcelRowSerializer(data=data)
        if serializer.is_valid():
            grouped_rows[serializer.validated_data["order_ref"]].append(serializer.validated_data)
        else:
            row_errors.append({"row": row_no, "errors": serializer.errors})

    created_orders, order_errors = [], []

    for order_ref, rows in grouped_rows.items():
        try:
            with transaction.atomic():
                first = rows[0]
                order = Order.objects.create(
                    customer_name=first["customer_name"].strip(),
                    contact_no=first["contact_no"].strip(),
                    vehicle_model=first["vehicle_model"].strip(),
                    order_date=first["order_date"],
                    advance=float(first["advance"]),
                )
                total = 0
                for r in rows:
                    stock = Stock.objects.get(item_no=extract_item_no(r["item_no"]).upper())
                    qty, rate = int(r["quantity"]), float(r["rate"])
                    OrderItem.objects.create(order=order, item=stock, quantity=qty, rate=rate)
                    total += qty * rate
                order.total_amount = total
                order.remaining_amount = total - order.advance
                order.save()
                created_orders.append(order.id)
        except Exception as e:
            order_errors.append({"order_ref": order_ref, "error": str(e)})

    return Response({"created_orders": created_orders, "row_errors": row_errors, "order_errors": order_errors})

# ===================== PURCHASE/SALES EXCEL =====================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_purchase_excel_api(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"error": "Excel file required"}, status=400)
    return Response(upload_purchase_excel(file, request.user))

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_sales_excel_api(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"error": "Excel file required"}, status=400)
    return Response(upload_sales_excel(file))
