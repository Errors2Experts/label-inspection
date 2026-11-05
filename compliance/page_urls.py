from django.urls import path

from . import page_views as v

urlpatterns = [
    path('rules/', v.RulesOverviewPage.as_view(), name='page-rules'),
    path('rules/add/', v.RuleFormPage.as_view(mode='add'), name='page-rule-add'),
    path('rules/<int:pk>/edit/', v.RuleFormPage.as_view(mode='edit'), name='page-rule-edit'),
    path('rules/<int:pk>/versions/', v.RuleVersionsPage.as_view(), name='page-rule-versions'),
    path('rules/categories/', v.CategoriesPage.as_view(), name='page-rule-categories'),
    path('rules/packs/add/', v.PackFormPage.as_view(mode='add'), name='page-pack-add'),
    path('rules/packs/<int:pk>/', v.PackFormPage.as_view(mode='edit'), name='page-pack-detail'),
    path('rules/evaluate/', v.EvaluatePage.as_view(), name='page-evaluate'),
    path('rules/results/', v.ResultListPage.as_view(), name='page-results'),
    path('rules/results/<int:pk>/', v.ResultDetailPage.as_view(), name='page-result-detail'),
    path('rules/violations/', v.ViolationsPage.as_view(), name='page-violations'),
]
