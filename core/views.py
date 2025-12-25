from collections import defaultdict
from django.utils import timezone
from django.db.models import Sum, F, FloatField
from django.db import transaction

import openpyxl
from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import IsAdminOrReadOnlyForStaff
from core.services.dashboard_overview import full_dashboard_service
from core.services.purchase_upload import upload_purchase_excel
from core.services.utils import extract_item_no
from .models import (
    Expense, SalaryTracker, SalaryTransaction, Supplier, Category, Stock, Purchase, PurchaseItem,
    Sale, SaleItem, FollowUpDashboard,
    Order, OrderItem, Staff, User
)
from .serializers import (
    ExpenseSerializer, FollowUpUploadSerializer, OrderExcelRowSerializer, SalaryTrackerSerializer, SalaryTransactionSerializer, SupplierSerializer, CategorySerializer, StockSerializer,
    PurchaseSerializer, StockSaleSerializer, ServiceSaleSerializer,
        FollowUpDashboardSerializer,
    StaffSerializer, OrderSerializer, UserSerializer
)
from rest_framework.decorators import action
from .services.stock_dashboard import get_stock_dashboard


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
VALID_STATUSES = {"pending", "completed", "terminated"}
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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def full_dashboard(request):
    data = full_dashboard_service()  # no request passed
    return Response(data)



# =====================================================
# ORDER
# =====================================================
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]


# ---------------- SalaryTracker ----------------
class SalaryTrackerViewSet(viewsets.ModelViewSet):
    queryset = SalaryTracker.objects.all()
    serializer_class = SalaryTrackerSerializer
    permission_classes = [IsAuthenticated]


# ---------------- SalaryTransaction ----------------
class SalaryTransactionViewSet(viewsets.ModelViewSet):
    queryset = SalaryTransaction.objects.all()
    serializer_class = SalaryTransactionSerializer
    permission_classes = [IsAuthenticated]


# ---------------- Expense ----------------
class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]


import pandas as pd
from django.utils.dateparse import parse_date

def parse_excel_date(value):
    """Convert Excel/str/NaN to Python date or None"""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        return parse_date(value)  # expects "YYYY-MM-DD"
    return pd.to_datetime(value).date()


@api_view(['POST'])
def followup_excel_upload(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"error": "No file uploaded"}, status=400)

    df = pd.read_excel(file)
    created_followups = []
    errors = []

    for idx, row in df.iterrows():
        row_number = idx + 2  # Excel row number (header + 1)

        try:
            # Resolve assigned_to
            assigned_user = None
            assigned_val = row.get('assigned_to')
            if assigned_val:
                try:
                    # If numeric, treat as PK
                    if str(assigned_val).isdigit():
                        assigned_user = Staff.objects.get(pk=int(assigned_val))
                    else:
                        # Otherwise, treat as name
                        assigned_user = Staff.objects.get(name=str(assigned_val))
                except Staff.DoesNotExist:
                    raise ValueError(f"Staff '{assigned_val}' not found")

            # Parse dates safely
            def parse_excel_date(value):
                if pd.isna(value) or value in [None, ""]:
                    return None
                if isinstance(value, str):
                    return timezone.datetime.strptime(value, "%Y-%m-%d").date()
                return value.date() if hasattr(value, "date") else value

            followup = FollowUpDashboard.objects.create(
                customer_name=row['customer_name'],
                contact_no=row.get('contact_no', ''),
                vehicle=row.get('vehicle', ''),
                follow_up_date=parse_excel_date(row['follow_up_date']),
                assigned_to=assigned_user,
                remarks=row.get('remarks', ''),
                delivery_date=parse_excel_date(row.get('delivery_date')),
                post_service_feedback_date=parse_excel_date(row.get('post_service_feedback_date'))
            )

            created_followups.append(followup.id)

        except Exception as e:
            errors.append({"row": row_number, "errors": str(e)})

    return Response({
        "created_followups": created_followups,
        "errors": errors
    })


@api_view(['POST'])
def stock_excel_upload(request):
    file = request.FILES.get('file')

    if not file:
        return Response({"error": "No file uploaded"}, status=400)

    try:
        df = pd.read_excel(file)
    except Exception as e:
        return Response({"error": f"Invalid Excel file: {str(e)}"}, status=400)

    required_columns = [
        'item_no', 'name', 'category', 'model',
        'purchase_price', 'sale_price', 'stock'
    ]

    for col in required_columns:
        if col not in df.columns:
            return Response({"error": f"Missing column: {col}"}, status=400)

    created = []
    updated = []
    errors = []

    for idx, row in df.iterrows():
        row_number = idx + 2  # Excel row number

        try:
            with transaction.atomic():
                # Category
                category_name = str(row['category']).strip()
                category, _ = Category.objects.get_or_create(name=category_name)

                group_value = (
                    str(row['group']).strip()
                    if 'group' in row and pd.notna(row['group'])
                    else category.name
                )

                stock_obj, is_created = Stock.objects.update_or_create(
                    item_no=str(row['item_no']).strip(),
                    defaults={
                        'name': str(row['name']).strip(),
                        'category': category,
                        'model': str(row['model']).strip(),
                        'group': group_value,
                        'purchase_price': float(row['purchase_price']),
                        'sale_price': float(row['sale_price']),
                        'vat': float(row['vat']) if 'vat' in row and pd.notna(row['vat']) else 0,
                        'stock': int(row['stock'])
                    }
                )

                if is_created:
                    created.append(stock_obj.item_no)
                else:
                    updated.append(stock_obj.item_no)

        except Exception as e:
            errors.append({
                "row": row_number,
                "item_no": row.get('item_no'),
                "error": str(e)
            })

    return Response({
        "created": created,
        "updated": updated,
        "errors": errors
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_excel_upload(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"detail": "Excel file is required"}, status=400)

    wb = openpyxl.load_workbook(file)
    sheet = wb.active

    grouped_rows = defaultdict(list)
    row_errors = []

    # ---------------- READ + VALIDATE ----------------
    for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
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
        if not serializer.is_valid():
            row_errors.append({
                "row": row_number,
                "errors": serializer.errors
            })
            continue

        grouped_rows[serializer.validated_data["order_ref"]].append(
            serializer.validated_data
        )

    created_orders = []
    order_errors = []

    # ---------------- CREATE ORDERS ----------------
    for order_ref, rows in grouped_rows.items():
        try:
            with transaction.atomic():
                first = rows[0]

                order = Order.objects.create(
                    customer_name=first["customer_name"].strip(),
                    contact_no=first["contact_no"].strip(),
                    vehicle_model=first["vehicle_model"].strip(),
                    order_date=first["order_date"],
                    advance=float(first["advance"])
                )

                total_amount = 0

                for r in rows:
                    item_no = extract_item_no(r["item_no"]).strip().upper()
                    try:
                        stock = Stock.objects.get(item_no=item_no)
                    except Stock.DoesNotExist:
                        raise Exception(f"Stock with item_no '{item_no}' does not exist")

                    qty = int(r["quantity"])
                    rate = float(r["rate"])

                    OrderItem.objects.create(
                        order=order,
                        item=stock,
                        quantity=qty,
                        rate=rate
                    )

                    total_amount += qty * rate

                # Update totals
                order.total_amount = total_amount
                order.remaining_amount = total_amount - order.advance
                order.save(update_fields=['total_amount', 'remaining_amount'])

                created_orders.append(order.id)

        except Exception as e:
            order_errors.append({
                "order_ref": order_ref,
                "error": str(e)
            })

    return Response({
        "created_orders": created_orders,
        "row_errors": row_errors,
        "order_errors": order_errors
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_purchase_excel_api(request):
    file = request.FILES.get('file')
    if not file:
        return Response({"error": "Excel file required"}, status=400)

    result = upload_purchase_excel(file, request.user)
    return Response(result)

