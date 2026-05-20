from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import viewsets, filters, status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Branch, User
from .serializers import BranchSerializer, UserSerializer, UserCreateSerializer
from .permissions import BranchScopedQuerysetMixin, IsAdmin, BranchScopedPermission


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'role', 'role_display', 'branch', 'branch_name', 'is_active',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Authenticate user and return JWT tokens with user info.
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data['username']
    password = serializer.validated_data['password']

    user = authenticate(username=username, password=password)

    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {'error': 'Account is disabled'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Update last login
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    # Generate tokens
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)

    # Serialize user data
    user_serializer = UserSerializer(user)

    return Response({
        'access': access_token,
        'refresh': str(refresh),
        'user': user_serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def logout_view(request):
    """
    Logout by blacklisting the refresh token.
    Note: Access tokens are stateless and will expire naturally.
    """
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
def current_user_view(request):
    """
    Get current authenticated user information.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom token refresh view that includes updated user info.
    """

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Add updated user info to response
            user_serializer = UserSerializer(request.user)
            response.data['user'] = user_serializer.data

        return response


from common.mixins import BranchScopedViewSetMixin


class UserViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    """
    ViewSet for user management.
    - Admins can manage all users
    - Branch managers can manage users in their branch
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]  # Only admins can manage users for now
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering_fields = ['username', 'date_joined', 'last_login']
    ordering = ['username']

    def get_queryset(self):
        queryset = User.objects.select_related('branch')

        # Admins see all users
        if self.request.user.is_admin:
            return queryset

        # Branch managers see only users in their branch
        if self.request.user.is_branch_manager:
            return queryset.filter(branch=self.request.user.branch)

        # Others see only themselves
        return queryset.filter(id=self.request.user.id)

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        # Set created_by if not set
        if not serializer.validated_data.get('created_by'):
            serializer.save(created_by=self.request.user)


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'city', 'email']