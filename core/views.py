from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, F, FloatField, Case, When, IntegerField

from core.permissions import IsAdminOrReadOnlyForStaff
from .models import Supplier, Customer, Category, Item, Purchase, Sale, FollowUp, PurchaseItem, User
from .serializers import (
    StaffCreateSerializer, SupplierSerializer, CustomerSerializer, CategorySerializer,
    ItemSerializer, PurchaseSerializer, SaleSerializer, FollowUpSerializer, UserSerializer
)
from datetime import timedelta
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
#from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrReadOnlyForStaff]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:  # Admin
            return User.objects.all()
        elif user.is_staff:
            # Staff sees only regular users
            return User.objects.filter(is_staff=False, is_superuser=False)
        return User.objects.none()


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by('name')
    serializer_class = SupplierSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact', 'email']
    ordering_fields = ['name']

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by('name')
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact', 'email']
    ordering_fields = ['name']

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all().order_by('name')
    serializer_class = ItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'model', 'category__name', 'group']
    ordering_fields = ['name', 'stock', 'sale_price', 'purchase_price']

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all().order_by('-date')
    serializer_class = PurchaseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['supplier__name']
    ordering_fields = ['date']

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.order_by('-sale_date')
    serializer_class = SaleSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['is_servicing', 'customer']
    ordering_fields = ['sale_date', 'total_amount']
    search_fields = ['customer__name']


class FollowUpViewSet(viewsets.ModelViewSet):
    queryset = FollowUp.objects.all().order_by('follow_up_date')
    serializer_class = FollowUpSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['completed']
    ordering_fields = ['follow_up_date', 'completed']
    search_fields = ['sale__customer__name']


class StaffCreateView(APIView):
    permission_classes = [IsAdminOrReadOnlyForStaff]  # Only admin can create staff

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
    


@api_view(['GET'])
def dashboard_summary(request):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    last_week = today - timedelta(days=6)

    # ---------------- Totals ----------------
    total_sales_count = Sale.objects.count()
    total_purchases_count = Purchase.objects.count()
    total_customers = Customer.objects.count()
    total_suppliers = Supplier.objects.count()
    total_items = Item.objects.count()

    # ---------------- Amounts ----------------
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

    # ---------------- Stock Alerts ----------------
    low_stock_items = Item.objects.filter(stock__lt=5).values(
        'id', 'name', 'stock', 'category__name'
    )
    stock_threshold = 5

    # ---------------- Follow-Ups ----------------
    upcoming_followups = FollowUp.objects.select_related('sale__customer').annotate(
        incomplete_first=Case(
            When(completed=False, then=0),
            default=1,
            output_field=IntegerField()
        )
    ).order_by('incomplete_first', 'follow_up_date').values(
        'id', 'sale__customer__name', 'follow_up_date', 'remarks', 'completed'
    )

    # High priority: due today or overdue
    high_priority = upcoming_followups.filter(follow_up_date__lte=today)

    # Medium priority: within next 7 days
    medium_priority = upcoming_followups.filter(
        follow_up_date__gt=today,
        follow_up_date__lte=today + timedelta(days=7)
    )

    # Low priority: beyond 7 days
    low_priority = upcoming_followups.filter(follow_up_date__gt=today + timedelta(days=7))

    # ---------------- Sales by Category ----------------
    category_sales = (
        Sale.objects.values('items__item__category__name')
        .annotate(total_sales=Sum('total_amount'))
        .order_by('-total_sales')
    )

    # ---------------- 7-Day Chart Data ----------------
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

    # ---------------- Response ----------------
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
            "customers": total_customers,
            "suppliers": total_suppliers,
            "items": total_items,
        },
        "low_stock_items": list(low_stock_items),
        "stock_threshold": stock_threshold,
        "upcoming_followups": list(upcoming_followups),
        "followups_by_priority": {
            "high": list(high_priority),
            "medium": list(medium_priority),
            "low": list(low_priority),
        },
        "sales_by_category": [
            {"category_name": c['items__item__category__name'], "total_sales": c['total_sales']}
            for c in category_sales
        ],
        "sales_chart": [
            {"date": s['sale_date__date'], "total": s['total']} for s in sales_data
        ],
        "purchase_chart": [
            {"date": p['purchase__date__date'], "total": p['total']} for p in purchase_data
        ],
    })