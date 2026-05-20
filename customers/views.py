from rest_framework import viewsets, filters
from .models import Customer
from .serializers import CustomerSerializer
from common.mixins import BranchScopedViewSetMixin
from common.selectors import CustomerSelector


class CustomerViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CustomerSelector.get_queryset()
    serializer_class = CustomerSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone']

    def get_queryset(self):
        branch_param = self.request.query_params.get('branch')
        if self.request.user.is_admin and branch_param:
            queryset = CustomerSelector.get_for_branch(branch_param)
        else:
            queryset = CustomerSelector.get_queryset()
        return self.filter_queryset_by_branch(queryset)