from rest_framework import viewsets, filters
from .models import Customer
from .serializers import CustomerSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone']

    def get_queryset(self):
        queryset = Customer.objects.all()
        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch=branch)
        return queryset