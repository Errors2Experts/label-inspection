"""Barcode -> product resolution used by GET /api/products/lookup/ (FDS 10.3).

Order: local catalogue first, then the external product API (result is cached in the catalogue so
inspections can reference it). The inspection workflow must never be blocked, so every outcome except an
invalid barcode is returned as data, not raised.
"""

from dataclasses import dataclass

from django.db import IntegrityError

from ..gtin import to_gtin14
from ..models import Product, ProductSource
from .open_food_facts import ExternalLookupError, fetch_product


@dataclass
class LookupResult:
    product: Product | None
    source: str | None  # 'local' | 'open_food_facts' | None
    external_status: str  # 'skipped' | 'found' | 'not_found' | 'unavailable'


def resolve_gtin(gtin: str, user) -> LookupResult:
    local = Product.objects.filter(gtin14=to_gtin14(gtin)).first()
    if local:
        return LookupResult(local, 'local', 'skipped')

    try:
        external = fetch_product(gtin)
    except ExternalLookupError:
        return LookupResult(None, None, 'unavailable')
    if external is None:
        return LookupResult(None, None, 'not_found')

    try:
        product = Product.objects.create(
            gtin=gtin,
            source=ProductSource.OPEN_FOOD_FACTS,
            source_data=external['raw'],
            created_by=user,
            updated_by=user,
            **external['fields'],
        )
    except IntegrityError:  # another request cached the same barcode a moment ago
        product = Product.objects.get(gtin14=to_gtin14(gtin))
    return LookupResult(product, 'open_food_facts', 'found')
