import re

from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAnyRole, roles_required

from .gtin import validate_gtin
from .models import Product, ProductSource
from .serializers import ProductSerializer
from .services.lookup import resolve_gtin
from .throttles import ProductLookupThrottle

# FDS 7.2: Product Catalogue = Yes for all roles. Change here if the approved permissions differ.
CATALOGUE_WRITE_ROLES = (Role.ADMIN, Role.SUPERVISOR, Role.INSPECTOR)
MAX_SEARCH_LENGTH = 100

LOOKUP_MESSAGES = {
    'not_found': 'Product not found in the catalogue or the external product database. '
    'You can enter it manually or continue with package images and OCR.',
    'unavailable': 'The external product service is not reachable right now. '
    'You can enter the product manually or continue with package images and OCR.',
}


def clean_search_term(raw: str) -> str:
    """Trim, drop control characters, collapse spaces and cap the length of free-text search input."""
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', raw or '')
    return re.sub(r'\s+', ' ', text).strip()[:MAX_SEARCH_LENGTH]


class ProductViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """/api/products/ - list+search, detail, create, update, and /lookup/?gtin=. No delete (not in FDS).

    Filters: ?q=<name/brand/barcode/manufacturer>  ?category=<text>  ?source=manual|open_food_facts
    """

    queryset = Product.objects.select_related('created_by')
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update'):
            return [roles_required(*CATALOGUE_WRITE_ROLES)()]
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        term = clean_search_term(params.get('q'))
        if term:
            digits = re.sub(r'\D', '', term)
            query = (
                Q(name__icontains=term)
                | Q(brand__icontains=term)
                | Q(manufacturer__icontains=term)
                | Q(category__icontains=term)
            )
            if digits and len(digits) >= 4:
                query |= Q(gtin__contains=digits)
            qs = qs.filter(query)
        category = clean_search_term(params.get('category'))
        if category:
            qs = qs.filter(category__icontains=category)
        if params.get('source') in ProductSource.values:
            qs = qs.filter(source=params['source'])
        return qs.order_by('id')  # the list shows products in the order they were added

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user, source=ProductSource.MANUAL)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=['get'], pagination_class=None)
    def categories(self, request):
        """GET /api/products/categories/ - distinct product categories, for the list filter dropdown."""
        names = Product.objects.exclude(category='').values_list('category', flat=True).distinct().order_by('category')
        return Response(list(names))

    @action(detail=False, methods=['get'], throttle_classes=[ProductLookupThrottle])
    def lookup(self, request):
        """GET /api/products/lookup/?gtin=...

        200 {found: true, source, product}      - known locally or fetched from the external API (and cached)
        200 {found: false, external_status, ...} - unknown or external service down: the inspection continues
        400                                     - the barcode itself is malformed
        """
        raw = request.query_params.get('gtin', '')
        try:
            gtin = validate_gtin(raw)
        except ValueError as exc:
            return Response({'gtin': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

        result = resolve_gtin(gtin, request.user)
        if result.product:
            return Response(
                {
                    'found': True,
                    'source': result.source,
                    'external_status': result.external_status,
                    'product': self.get_serializer(result.product).data,
                }
            )
        return Response(
            {
                'found': False,
                'gtin': gtin,
                'external_status': result.external_status,
                'can_continue': True,
                'detail': LOOKUP_MESSAGES[result.external_status],
            }
        )
