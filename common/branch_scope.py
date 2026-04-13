"""
Branch-scoped API helpers (Sprint 6).

Use BranchScopedQuerysetMixin on ModelViewSets that are keyed by Branch to keep
querysets aligned with the active branch from ?branch=.
"""
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError


def parse_branch_id(request, param='branch', required=False):
    """
    Read branch id from query params. Validates numeric id when present.
    """
    raw = request.query_params.get(param)
    if raw is None or raw == '':
        if required:
            raise ValidationError({param: 'Branch is required for this endpoint.'})
        return None
    if not str(raw).isdigit():
        raise ValidationError({param: 'Invalid branch id.'})
    return int(raw)


class BranchScopedQuerysetMixin:
    """
    Filters queryset by ?branch=<id> when provided.

    Set branch_filter_field to the model field name (default: 'branch_id').
    Set branch_required=True to return an empty queryset when branch is missing.
    """
    branch_param = 'branch'
    branch_filter_field = 'branch_id'
    branch_required = False

    def _branch_id(self):
        return parse_branch_id(self.request, param=self.branch_param, required=False)

    def get_queryset(self):
        qs = super().get_queryset()
        bid = self._branch_id()
        if bid is None:
            if self.branch_required:
                return qs.none()
            return qs
        return qs.filter(**{self.branch_filter_field: bid})


def ensure_branch_scope(request, branch_id, user_branch_ids=None):
    """
    Hook for future auth: reject when the user may not access branch_id.
    When user_branch_ids is None, no extra check (dev / open API).
    """
    if user_branch_ids is not None and branch_id not in user_branch_ids:
        raise PermissionDenied('You do not have access to this branch.')
