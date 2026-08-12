from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
    # ================= ViewSets =================
    UserViewSet,
    SupplierViewSet,
    CategoryViewSet,
    StockViewSet,
    PurchaseViewSet,
    SaleViewSet,
    OrderViewSet,
    StaffViewSet,
    FollowUpDashboardViewSet,
    SalaryTrackerViewSet,
    SalaryTransactionViewSet,
    ExpenseViewSet,
    dashboard_charts_api,
    dashboard_credit_api,
    followups_api,
    low_stock_api,

    # ================= Excel Upload =================
    order_excel_upload_api,
    orders_api,
    purchase_excel_upload_api,
    sale_excel_upload_api,
    staff_salary_api,
    stock_excel_upload_api,
    new_mrp_excel_upload_api,

# ================= Excel export =================
    stock_excel_export_api,

    #Bike Sale
    BikeSaleViewSet, EmiTrackerViewSet, EmiTrackerUpdateAPIView

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

# ---------------- Orders ----------------
router.register(r'orders', OrderViewSet, basename='order')

# ---------------- Staff ----------------
router.register(r'staffs', StaffViewSet, basename='staff')

# ---------------- Follow-Ups ----------------
router.register(r'followups', FollowUpDashboardViewSet, basename='followup')

# ---------------- Salary & Expense ----------------
router.register(r'salarytracker', SalaryTrackerViewSet, basename='salarytracker')
router.register(r'salarytransactions', SalaryTransactionViewSet, basename='salarytransaction')
router.register(r'expenses', ExpenseViewSet, basename='expense')

# ---------------- Bike Sale ----------------
router.register(r'bike-sales', BikeSaleViewSet, basename='bike-sale')

# ---------------- Bike sale tracker ----------------
router.register(r'emi-tracker', EmiTrackerViewSet, basename='emi-tracker')

# =================================================
# 🌐 URL PATTERNS
# =================================================
urlpatterns = [

    # ================= API ROUTES =================
    path('', include(router.urls)),

    # ================= AUTH =================
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ================= DASHBOARD =================
    # Charts only
    path(
        "dashboard/charts/",
        dashboard_charts_api,
        name="dashboard-charts",
    ),

    # Credit only
    path(
        "dashboard/credit/",
        dashboard_credit_api,
        name="dashboard-credit",
    ),

    # Tables (separate)
    path(
        "dashboard/tables/followups/",
        followups_api,
        name="dashboard-followups",
    ),
    path(
        "dashboard/tables/low-stock/",
        low_stock_api,
        name="dashboard-low-stock",
    ),
    path(
        "dashboard/tables/orders/",
        orders_api,
        name="dashboard-orders",
    ),
    path(
        "dashboard/tables/staff-salaries/",
        staff_salary_api,
        name="dashboard-staff-salaries",
    ),

    # ================= EXCEL UPLOAD =================
    path("upload/purchase-excel/", purchase_excel_upload_api),
    path("upload/sales-excel/", sale_excel_upload_api),
    path("upload/stock-excel/", stock_excel_upload_api),
    path("upload/order-excel/", order_excel_upload_api),
    path("upload/new-mrp-excel/", new_mrp_excel_upload_api),

# ================= EXCEL Export =================
    path("export/stock-excel/", stock_excel_export_api),

    #installment pay garda emi update hune endpoint
    path('emi/<int:id>/update/', EmiTrackerUpdateAPIView.as_view(), name='emi-update'),
]