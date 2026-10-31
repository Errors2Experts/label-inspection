
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InspectionViewSet, test_ocr, test_ai_extraction

router = DefaultRouter()

router.register(
    r"inspections",
    InspectionViewSet,
    basename="inspection",
)

urlpatterns = [
    path("", include(router.urls)),
    path("test-ocr/", test_ocr, name="test-ocr"),
    path("test-ai/", test_ai_extraction, name="test-ai-extraction",),
]
