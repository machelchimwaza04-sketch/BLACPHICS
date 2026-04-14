from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from common.selectors import OrderSelector
from .models import Order, OrderItem, Payment
from .serializers import OrderSerializer, OrderItemSerializer, OrderListSerializer, PaymentSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.none()
    serializer_class = OrderSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['order_number', 'status', 'payment_status']

    def get_queryset(self):
        queryset = OrderSelector.get_queryset()
        branch = self.request.query_params.get('branch')
        payment_status = self.request.query_params.get('payment_status')
        transaction_type = self.request.query_params.get('transaction_type')
        status = self.request.query_params.get('status')

        if branch:
            queryset = queryset.filter(branch=branch)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        return OrderSerializer

    @action(detail=False, methods=['get'])
    def next_number(self, request):
        branch_id = request.query_params.get('branch')
        if not branch_id:
            return Response({'error': 'branch required'}, status=400)
        number = Order.generate_order_number(branch_id)
        return Response({'order_number': number})

    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        order = self.get_object()
        serializer = PaymentSerializer(order.payments.order_by('-created_at'), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        order = self.get_object()
        order.recalculate_payment_status()
        amount = float(request.data.get('amount', 0))
        method = request.data.get('method', 'cash')
        payment_type = request.data.get('payment_type', 'payment')
        notes = request.data.get('notes', '')
        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)
        if amount > float(order.balance_due):
            return Response({'error': 'Payment exceeds outstanding balance'}, status=400)
        Payment.objects.create(
            order=order, amount=amount,
            method=method, payment_type=payment_type, notes=notes
        )
        order.recalculate_payment_status()
        order.refresh_from_db()
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def writeoff(self, request, pk=None):
        order = self.get_object()
        balance = float(order.balance_due)
        if balance <= 0:
            return Response({'error': 'No balance to write off'}, status=400)
        Payment.objects.create(
            order=order, amount=balance,
            method='cash', payment_type='writeoff',
            notes=request.data.get('notes', 'Written off')
        )
        order.recalculate_payment_status()
        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def get_queryset(self):
        queryset = Payment.objects.all()
        order = self.request.query_params.get('order')
        if order:
            queryset = queryset.filter(order=order)
        return queryset