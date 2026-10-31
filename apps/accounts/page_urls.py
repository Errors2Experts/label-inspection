from django.urls import path

from . import page_views as v

urlpatterns = [
    path('', v.HomeRedirect.as_view(), name='page-home'),
    path('login/', v.LoginPage.as_view(), name='page-login'),
    path('forgot-password/', v.ForgotPasswordPage.as_view(), name='page-forgot-password'),
    path('reset-password/', v.ResetPasswordPage.as_view(), name='page-reset-password'),
    path('dashboard/', v.DashboardPage.as_view(), name='page-dashboard'),
    path('users/', v.UserListPage.as_view(), name='page-users'),
    path('users/add/', v.UserFormPage.as_view(mode='add'), name='page-user-add'),
    path('users/<int:pk>/', v.UserDetailPage.as_view(), name='page-user-detail'),
    path('users/<int:pk>/edit/', v.UserFormPage.as_view(mode='edit'), name='page-user-edit'),
    path('roles/', v.RolesPage.as_view(), name='page-roles'),
    path('profile/', v.ProfilePage.as_view(), name='page-profile'),
]
