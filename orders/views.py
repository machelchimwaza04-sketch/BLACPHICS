from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Order, OrderItem, Payment, OrderIdempotencyRecord
from .serializers import OrderSerializer, OrderItemSerializer, PaymentSerializer
from common.mixins import BranchScopedViewSetMixin
from common.selectors import OrderSelector
from .services import OrderService  # Add OrderService import


class OrderViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = OrderSelector.get_queryset()
    serializer_class = OrderSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['order_number', 'status', 'payment_status']

    def create(self, request, *args, **kwargs):
        idempotency_key = request.data.get('idempotency_key')
        if idempotency_key:
            # Check for existing idempotency record
            existing_record = OrderIdempotencyRecord.objects.filter(
                key=idempotency_key,
                method=request.method
            ).first()
            if existing_record:
                # Return the stored response
                return Response(
                    existing_record.response_body,
                    status=existing_record.response_code
                )
        
        # Proceed with normal creation
        response = super().create(request, *args, **kwargs)
        
        # Store the idempotency record if key was provided
        if idempotency_key and response.status_code == status.HTTP_201_CREATED:
            try:
                OrderIdempotencyRecord.objects.create(
                    key=idempotency_key,
                    endpoint='/api/orders/',  # Keep for now
                    method=request.method,
                    request_body={'order_number': request.data.get('order_number')},  # Minimal data
                    response_code=response.status_code,
                    response_body={'id': response.data.get('id'), 'order_number': response.data.get('order_number')}  # Minimal data
                )
            except Exception as e:
                print(f"Failed to create idempotency record: {e}")
                pass  # Don't fail the request if record creation fails
        
        return response

    def get_queryset(self):
        """Use optimized OrderSelector with filtering."""
        branch_param = self.request.query_params.get('branch')
        status_filter = self.request.query_params.get('status')
        payment_status = self.request.query_params.get('payment_status')
        transaction_type = self.request.query_params.get('transaction_type')

        # Start with optimized queryset
        if self.request.user.is_admin and branch_param:
            queryset = OrderSelector.get_for_branch(branch_param)
        else:
            queryset = OrderSelector.get_queryset()

        queryset = self.filter_queryset_by_branch(queryset)

        # Apply additional filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)

        return queryset

    @action(detail=False, methods=['get'])
    def next_number(self, request):
        from branches.models import Branch
        branch_id = request.query_params.get('branch')
        if not branch_id:
            if self.request.user.is_admin:
                return Response({'error': 'branch required'}, status=400)
            branch_id = self.get_branch_id()
        
        try:
            branch = Branch.objects.get(id=branch_id)
            number = OrderService.generate_order_number(branch)
            return Response({'order_number': number})
        except Branch.DoesNotExist:
            return Response({'error': 'Branch not found'}, status=404)

    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        order = self.get_object()
        amount = float(request.data.get('amount', 0))
        method = request.data.get('method', 'cash')
        payment_type = request.data.get('payment_type', 'payment')
        notes = request.data.get('notes', '')
        
        if amount <= 0:
            return Response({'error': 'Amount must be positive'}, status=400)
        
        try:
            payment = OrderService.add_payment(
                order=order,
                amount=amount,
                method=method,
                processed_by=request.user,
                payment_type=payment_type,
                notes=notes
            )
            return Response(PaymentSerializer(payment).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm order - reserve stock for custom orders."""
        order = self.get_object()
        try:
            order = OrderService.confirm_order(order, request.user)
            return Response(OrderSerializer(order).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete order - deduct stock and finalize."""
        order = self.get_object()
        try:
            order = OrderService.complete_order(order, request.user)
            return Response(OrderSerializer(order).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel order - release reserved stock."""
        order = self.get_object()
        try:
            order = OrderService.cancel_order(order, request.user)
            return Response(OrderSerializer(order).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Process refund for completed order."""
        order = self.get_object()
        amount = float(request.data.get('amount', 0))
        reason = request.data.get('reason', '')
        
        if amount <= 0:
            return Response({'error': 'Refund amount must be positive'}, status=400)
        
        try:
            refund = OrderService.refund_order(
                order=order,
                amount=amount,
                reason=reason,
                processed_by=request.user
            )
            return Response(PaymentSerializer(refund).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def writeoff(self, request, pk=None):
        order = self.get_object()
        balance = float(order.balance_due)
        if balance <= 0:
            return Response({'error': 'No balance to write off'}, status=400)
        
        try:
            payment = OrderService.add_payment(
                order=order,
                amount=balance,
                method='cash',
                processed_by=request.user,
                payment_type='writeoff',
                notes=request.data.get('notes', 'Written off')
            )
            return Response(PaymentSerializer(payment).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)


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