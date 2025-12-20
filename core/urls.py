from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    StaffCreateView,
    StockViewSet,
    SupplierViewSet,
    CategoryViewSet,
    StockViewSet,
    PurchaseViewSet,
    SaleViewSet,
    FollowUpDashboardViewSet,
    UserViewSet,
    OrderViewSet,
    TechnicianViewSet,
    StaffViewSet,
    dashboard_summary,
)

router = DefaultRouter()

# ---------------- User ----------------
router.register(r'users', UserViewSet, basename='user')

# ---------------- Supplier ----------------
router.register(r'suppliers', SupplierViewSet)

# ---------------- Category ----------------
router.register(r'categories', CategoryViewSet)

# ---------------- Stock (Read-only) ----------------
router.register(r'stocks', StockViewSet, basename='stock')

# # ---------------- Item CRUD ----------------
# router.register(r'items', StockViewSet, basename='item')

# ---------------- Purchase ----------------
router.register(r'purchases', PurchaseViewSet)

# ---------------- Sale ----------------
router.register(r'sales', SaleViewSet)

# ---------------- FollowUp Dashboard ----------------
router.register(r'followups', FollowUpDashboardViewSet, basename='followup-dashboard')

# ---------------- Orders ----------------
router.register(r'orders', OrderViewSet)

# ---------------- Technicians ----------------
router.register(r'technicians', TechnicianViewSet)

# ---------------- Staff ----------------
router.register(r'staffs', StaffViewSet)

urlpatterns = [
    path('', include(router.urls)),

    # Staff creation endpoint
    path('staff/create/', StaffCreateView.as_view(), name='create_staff'),

    # JWT Authentication
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Dashboard overview
    path('dashboard/', dashboard_summary, name='dashboard-summary'),
]
