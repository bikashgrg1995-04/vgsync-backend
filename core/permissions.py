from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdminOrReadOnlyForStaff(BasePermission):
    """
    Permissions:
    - Superuser (admin): full access
    - Staff: can view but not access other staff/superusers
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False  # Must be logged in

        # Superuser has full access
        if user.is_superuser:
            return True

        # Staff can only read safe methods
        if user.is_staff:
            return request.method in SAFE_METHODS

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Superuser can access any object
        if user.is_superuser:
            return True

        # Staff cannot access other staff/superuser objects
        if user.is_staff:
            return not obj.is_staff and not obj.is_superuser

        return False
