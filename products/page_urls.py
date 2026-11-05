from django.urls import path

from . import page_views as v

urlpatterns = [
    path('products/', v.ProductListPage.as_view(), name='page-products'),
    path('products/add/', v.ProductFormPage.as_view(mode='add'), name='page-product-add'),
    path('products/<int:pk>/', v.ProductDetailPage.as_view(), name='page-product-detail'),
    path('products/<int:pk>/edit/', v.ProductFormPage.as_view(mode='edit'), name='page-product-edit'),
]
