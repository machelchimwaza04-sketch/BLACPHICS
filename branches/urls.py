from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BranchViewSet,
    UserViewSet,
    login_view,
    logout_view,
    current_user_view,
    CustomTokenRefreshView
)

router = DefaultRouter()
router.register(r'branches', BranchViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', current_user_view, name='current-user'),
    path('auth/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh'),

    # Branch management
    path('', include(router.urls)),
]