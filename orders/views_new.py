from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from .models import Order, OrderItem, Payment, OrderNumberSequence
from .serializers import OrderSerializer, OrderItemSerializer, PaymentSerializer
from .services import OrderService
from common.mixins import BranchScopedViewSetMixin


class OrderViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    """
    Production-grade Order API with proper state management.
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_queryset(self):
        """Filter orders by branch and user permissions."""
        queryset = Order.objects.filter(branch=self.get_branch())

        # Admin can see all orders in their branch
        if not self.request.user.is_admin:
            # Non-admin users see only their own orders
            queryset = queryset.filter(created_by=self.request.user)

        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-created_at')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create order using service layer."""
        branch = self.get_branch()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Extract data
        order_data = serializer.validated_data.copy()
        items_data = order_data.pop('items', [])
        payments_data = order_data.pop('payments', [])

        # Create order via service
        order = OrderService.create_order(
            branch=branch,
            created_by=request.user,
            **order_data
        )

        # Add items via service
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            variant = item_data.get('variant')

            OrderService.add_order_item(
                order=order,
                product=product,
                quantity=quantity,
                variant=variant,
                **{k: v for k, v in item_data.items()
                   if k not in ['product', 'quantity', 'variant']}
            )

        # Add payments via service
        for payment_data in payments_data:
            OrderService.add_payment(
                order=order,
                amount=payment_data['amount'],
                method=payment_data.get('method', 'cash'),
                processed_by=request.user,
                **{k: v for k, v in payment_data.items()
                   if k not in ['amount', 'method']}
            )

        # Return created order
        response_serializer = self.get_serializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm order - reserve stock."""
        order = self.get_object()
        try:
            OrderService.confirm_order(order, request.user)
            serializer = self.get_serializer(order)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete order - deduct stock and make immutable."""
        order = self.get_object()
        try:
            OrderService.complete_order(order, request.user)
            serializer = self.get_serializer(order)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel order - release reserved stock."""
        order = self.get_object()
        try:
            OrderService.cancel_order(order, request.user)
            serializer = self.get_serializer(order)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """Add payment to order."""
        order = self.get_object()
        amount = request.data.get('amount')
        method = request.data.get('method', 'cash')

        if not amount:
            return Response({'error': 'Amount required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = OrderService.add_payment(
                order=order,
                amount=amount,
                method=method,
                processed_by=request.user,
                **{k: v for k, v in request.data.items()
                   if k not in ['amount', 'method']}
            )
            serializer = self.get_serializer(order)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def next_number(self, request):
        """Get next order number preview."""
        branch = self.get_branch()
        number = OrderNumberSequence.generate_order_number(branch)
        return Response({'order_number': number})


class OrderItemViewSet(viewsets.ModelViewSet):
    """Order items management."""
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

    def get_queryset(self):
        queryset = OrderItem.objects.filter(order__branch=self.request.user.branch)
        order_id = self.request.query_params.get('order')
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset


class PaymentViewSet(viewsets.ModelViewSet):
    """Payment management."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def get_queryset(self):
        queryset = Payment.objects.filter(order__branch=self.request.user.branch)
        order_id = self.request.query_params.get('order')
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset