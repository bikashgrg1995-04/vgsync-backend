from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    StockViewSet,
    SupplierViewSet,
    CategoryViewSet,
    PurchaseViewSet,
    SaleViewSet,
    FollowUpDashboardViewSet,
    UserViewSet,
    OrderViewSet,
    dashboard_summary,
    StaffViewSet,
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

# ---------------- FollowUp Dashboard ----------------
router.register(r'followups', FollowUpDashboardViewSet, basename='followup-dashboard')

# ---------------- Orders ----------------
router.register(r'orders', OrderViewSet, basename='order')

# ---------------- Staff ----------------
router.register(r'staffs', StaffViewSet, basename='staff')

urlpatterns = [
    path('', include(router.urls)),

    # JWT Authentication
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Dashboard overview
    path('dashboard/', dashboard_summary, name='dashboard-summary'),
]
