from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='report_list'),
    path('generate/', views.report_generate_list, name='report_generate_list'),
    path('generate/<int:inspection_pk>/', views.report_generate, name='report_generate'),
    path('<int:pk>/', views.report_preview, name='report_preview'),
    path('<int:pk>/download/', views.report_download, name='report_download'),
]