from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    StaffCreateView, SupplierViewSet, CustomerViewSet, CategoryViewSet,
    ItemViewSet, PurchaseViewSet, SaleViewSet, FollowUpViewSet, UserViewSet, dashboard_summary
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'suppliers', SupplierViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'items', ItemViewSet)
router.register(r'purchases', PurchaseViewSet)
router.register(r'sales', SaleViewSet)
router.register(r'followups', FollowUpViewSet)

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),

    # Staff creation endpoint
    path('staff/create/', StaffCreateView.as_view(), name='create_staff'),

    # JWT Authentication endpoints 
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ✅ Add dashboard summary endpoint
    path('dashboard/', dashboard_summary, name='dashboard-summary'),
]
