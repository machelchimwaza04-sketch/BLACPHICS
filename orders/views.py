from rest_framework import viewsets, filters
from .models import Order, OrderItem
from .serializers import OrderSerializer, OrderItemSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['order_number', 'status', 'payment_status']

    def get_queryset(self):
        queryset = Order.objects.all()
        branch = self.request.query_params.get('branch')
        status = self.request.query_params.get('status')
        if branch:
            queryset = queryset.filter(branch=branch)
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer