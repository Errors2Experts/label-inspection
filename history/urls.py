from django.urls import path
from . import views 

urlpatterns = [
    path('', views.history_evidence, name='history_evidence'),
    path('inspection/<int:pk>/', views.inspection_detail, name='inspection_detail'),
]