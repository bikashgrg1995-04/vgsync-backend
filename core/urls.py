from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    ExpenseViewSet,
    SalaryTrackerViewSet,
    SalaryTransactionViewSet,
    UserViewSet,
    SupplierViewSet,
    CategoryViewSet,
    StockViewSet,
    PurchaseViewSet,
    SaleViewSet,
    FollowUpDashboardViewSet,
    OrderViewSet,
    StaffViewSet,
    followup_excel_upload,
    full_dashboard,
    order_excel_upload,
    stock_excel_upload,
    upload_purchase_excel_api,
    upload_sales_excel_api,
)

router = DefaultRouter()

# ---------------- User ----------------
router.register(r'users', UserViewSet, basename='user')

# ---------------- Supplier ----------------
router.register(r'suppliers', SupplierViewSet, basename='supplier')

# ---------------- Category ----------------
router.register(r'categories', CategoryViewSet, basename='category')

# ---------------- Stock ----------------
router.register(r'stocks', StockViewSet, basename='stock')

# ---------------- Purchase ----------------
router.register(r'purchases', PurchaseViewSet, basename='purchase')

# ---------------- Sale ----------------
router.register(r'sales', SaleViewSet, basename='sale')

# ---------------- Follow-Up Dashboard ----------------
router.register(r'followups', FollowUpDashboardViewSet, basename='followup-dashboard')

# ---------------- Orders ----------------
router.register(r'orders', OrderViewSet, basename='order')

# ---------------- Staff ----------------
router.register(r'staffs', StaffViewSet, basename='staff')

router.register(r'salarytracker', SalaryTrackerViewSet)
router.register(r'salarytransactions', SalaryTransactionViewSet)
router.register(r'expenses', ExpenseViewSet)

urlpatterns = [
    # API routes
    path('', include(router.urls)),

    # JWT Authentication
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Dashboard overview
    path('dashboard/', full_dashboard, name='dashboard-summary'),

    #followup_upload_file
    path('followup/excel-upload/', followup_excel_upload, name='followup_excel_upload'),
    
    #stock_upload_file
    path('stock/excel-upload/', stock_excel_upload),

    # order_upload_file
    path("order-excel-upload/", order_excel_upload),


    path('upload/purchase-excel/', upload_purchase_excel_api),
    path('upload/sales-excel/', upload_sales_excel_api),
]
