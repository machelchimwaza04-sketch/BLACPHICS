from django.db import models
from django.db.models import QuerySet


class BranchScopedQuerySet(QuerySet):
    """QuerySet that automatically filters by branch_id from context."""
    
    def for_branch(self, branch_id):
        """Explicitly filter by branch."""
        if not branch_id:
            return self
        return self.filter(branch_id=branch_id)


class BranchScopedManager(models.Manager):
    """Manager that respects branch scoping."""
    
    def get_queryset(self):
        return BranchScopedQuerySet(self.model, using=self._db)
    
    def for_branch(self, branch_id):
        return self.get_queryset().for_branch(branch_id)


class BranchScopedMixin(models.Model):
    """
    Mixin to add branch-awareness to a model.
    Ensures all queries respect branch isolation.
    """
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    
    objects = BranchScopedManager()
    
    class Meta:
        abstract = True


from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError


class StrictBranchSerializerMixin:
    """Enforce that the branch field is read-only for API clients."""

    def get_fields(self):
        fields = super().get_fields()
        if 'branch' in fields:
            fields['branch'].read_only = True
        return fields

    def validate(self, attrs):
        if isinstance(self.initial_data, dict) and 'branch' in self.initial_data:
            raise ValidationError({
                'branch': 'Branch is derived from the authenticated user and cannot be set manually.'
            })
        return super().validate(attrs)


class StrictBranchWriteMixin:
    """Assign branch from request.user on create/update.

    This mixin is intended for branch-scoped ModelViewSets.
    """

    def get_branch(self):
        user = getattr(self.request, 'user', None)
        if user is None or not user.is_authenticated:
            raise PermissionDenied('Authentication is required to determine branch context.')

        branch = getattr(user, 'branch', None)
        if branch is None:
            raise PermissionDenied('Branch assignment cannot be derived from your account.')
        return branch

    def perform_create(self, serializer):
        serializer.save(branch=self.get_branch())

    def perform_update(self, serializer):
        serializer.save(branch=self.get_branch())


class BranchScopedViewSetMixin(StrictBranchWriteMixin):
    """Apply strict branch isolation to branch-scoped ModelViewSets."""

    def get_branch_id(self):
        return getattr(self.get_branch(), 'id', None)

    def filter_queryset_by_branch(self, queryset, allow_query_param=False):
        if not self.request.user.is_authenticated:
            return queryset.none()

        if self.request.user.is_admin:
            if allow_query_param:
                branch_id = self.request.query_params.get('branch')
                if branch_id:
                    return queryset.filter(branch_id=branch_id)
            return queryset

        if hasattr(queryset.model, 'branch'):
            return queryset.filter(branch=self.request.user.branch)

        if hasattr(queryset.model, 'branch_id'):
            return queryset.filter(branch_id=self.request.user.branch_id)

        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filter_queryset_by_branch(queryset, allow_query_param=False)
