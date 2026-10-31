"""RBAC helpers (FDS 7.2). Other modules import from here, e.g.

from apps.accounts.permissions import IsAdminOrSupervisor
permission_classes = [IsAdminOrSupervisor]
"""

from rest_framework.permissions import BasePermission

from .models import Role

# Role-permission matrix from FDS 7.2. 'limited' / 'permitted' are enforced
# per-module (e.g. inspectors only see permitted history).
ROLE_PERMISSION_MATRIX = {
    'Login': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'yes'},
    'User Management': {'admin': 'yes', 'supervisor': 'limited', 'inspector': 'no'},
    'Product Catalogue': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'yes'},
    'Barcode Scan': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'yes'},
    'Create Inspection': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'yes'},
    'Perform Inspection': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'yes'},
    'Manage Compliance Rules': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'no'},
    'View History': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'permitted'},
    'View Reports': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'permitted'},
    'Dashboard': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'yes'},
    'Analytics': {'admin': 'yes', 'supervisor': 'yes', 'inspector': 'permitted'},
}


def roles_required(*roles):
    """Build a permission class that allows only active, authenticated users with one of `roles`."""

    class _RolePermission(BasePermission):
        message = 'You do not have permission to perform this action.'

        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.is_active and user.role in roles)

    _RolePermission.__name__ = 'RolesRequired_' + '_'.join(roles)
    return _RolePermission


IsAdmin = roles_required(Role.ADMIN)
IsAdminOrSupervisor = roles_required(Role.ADMIN, Role.SUPERVISOR)
IsAnyRole = roles_required(Role.ADMIN, Role.SUPERVISOR, Role.INSPECTOR)
