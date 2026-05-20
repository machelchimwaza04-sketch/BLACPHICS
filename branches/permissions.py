from rest_framework import permissions
from .models import User


class BranchScopedQuerysetMixin:
    """
    Mixin that automatically filters querysets by the authenticated user's branch.
    Admin users see all data, others see only their branch's data.
    """

    def get_queryset(self):
        queryset = super().get_queryset()

        # If user is not authenticated, return empty queryset
        if not self.request.user.is_authenticated:
            return queryset.none()

        # Admins see all data
        if self.request.user.is_admin:
            return queryset

        # Filter by branch for branch-scoped models
        model = queryset.model

        # Check if model has a branch field
        if hasattr(model, 'branch'):
            return queryset.filter(branch=self.request.user.branch)

        # Check if model has a branch_id field
        if hasattr(model, 'branch_id'):
            return queryset.filter(branch_id=self.request.user.branch_id)

        # If no branch field found, return unfiltered (for non-branch models)
        return queryset


class IsAdminOrBranchManager(permissions.BasePermission):
    """
    Allows access to admin users or branch managers.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_admin or request.user.is_branch_manager)
        )


class IsAdmin(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsBranchManager(permissions.BasePermission):
    """
    Allows access only to branch managers.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.is_branch_manager
        )


class IsCashier(permissions.BasePermission):
    """
    Allows access only to cashiers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_cashier


class BranchScopedPermission(permissions.BasePermission):
    """
    Base permission class for branch-scoped resources.
    Ensures users can only access data from their assigned branch.
    """

    def has_object_permission(self, request, view, obj):
        # Admins can access all branches
        if request.user.is_admin:
            return True

        # Check if object has a branch attribute
        if hasattr(obj, 'branch'):
            return request.user.has_branch_access(obj.branch)

        # Check if object has a branch_id attribute
        if hasattr(obj, 'branch_id'):
            return request.user.branch_id == obj.branch_id

        # If no branch association found, deny access
        return False


class BranchScopedListPermission(permissions.BasePermission):
    """
    Permission class for list views that filters queryset by user's branch.
    Should be used with BranchScopedQuerysetMixin.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsOwnerOrBranchManager(permissions.BasePermission):
    """
    Allows access to object owners or branch managers of the same branch.
    """

    def has_object_permission(self, request, view, obj):
        # Admins can access everything
        if request.user.is_admin:
            return True

        # Branch managers can access objects in their branch
        if request.user.is_branch_manager and hasattr(obj, 'branch'):
            return request.user.has_branch_access(obj.branch)

        # Users can access their own objects
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user

        return False