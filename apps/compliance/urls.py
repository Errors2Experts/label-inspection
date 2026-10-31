from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ComplianceResultViewSet,
    RuleCategoryViewSet,
    RulePackViewSet,
    RuleViewSet,
    ViolationViewSet,
    evaluate_view,
)

router = DefaultRouter()
router.register('rules', RuleViewSet, basename='rule')
router.register('rule-categories', RuleCategoryViewSet, basename='rule-category')
router.register('rule-packs', RulePackViewSet, basename='rule-pack')
router.register('compliance/results', ComplianceResultViewSet, basename='compliance-result')
router.register('compliance/violations', ViolationViewSet, basename='compliance-violation')

urlpatterns = [
    path('compliance/evaluate/', evaluate_view, name='compliance-evaluate'),
    path('', include(router.urls)),
]
