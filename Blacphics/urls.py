from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('branches.urls')),
    path('api/', include('products.urls')),
    path('api/', include('customers.urls')),
    path('api/', include('orders.urls')),
    path('api/', include('suppliers.urls')),
    path('api/', include('finance.urls')),
]
