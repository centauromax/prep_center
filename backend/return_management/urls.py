from django.contrib.auth import views as auth_views
from django.urls import path
from .views import product_return_list, product_return_edit

urlpatterns = [
    path('', product_return_list, name='home'),  # Imposta product_return_list come home page
    path('login/', auth_views.LoginView.as_view(template_name='return_management/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('edit/', product_return_edit, name='product_return_edit'),
]

