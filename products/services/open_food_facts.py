"""Client for the Open Food Facts product API (FDS 5 'Product Data', proposed source).

`fetch_product` returns a dict of Product field values, `None` when the product is unknown, and raises
`ExternalLookupError` on timeouts / network / server problems so the caller can fall back to manual entry.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger('lip.catalogue')

REQUEST_FIELDS = (
    'product_name,generic_name,brands,categories,quantity,ingredients_text,allergens_tags,'
    'manufacturing_places,origins,countries,image_url'
)


class ExternalLookupError(Exception):
    """The external product service could not be reached or returned something unusable."""


def _clip(value, length):
    return (value or '').strip()[:length]


def _first(csv_text):
    return (csv_text or '').split(',')[0].strip()


def map_product(raw: dict, gtin: str) -> dict:
    """Translate an Open Food Facts product payload into our Product fields."""
    allergens = ', '.join(t.split(':', 1)[-1].replace('-', ' ') for t in raw.get('allergens_tags') or [])
    image = raw.get('image_url') or ''
    return {
        'name': _clip(raw.get('product_name') or raw.get('generic_name'), 255) or f'Unnamed product {gtin}',
        'brand': _clip(_first(raw.get('brands')), 150),
        'category': _clip(_first(raw.get('categories')), 150),
        'net_quantity': _clip(raw.get('quantity'), 50),
        'ingredients': (raw.get('ingredients_text') or '').strip(),
        'allergens': allergens,
        'manufacturer': _clip(raw.get('manufacturing_places'), 255),
        'country_of_origin': _clip(_first(raw.get('origins')) or _first(raw.get('countries')), 100),
        'image_url': image if image.startswith(('http://', 'https://')) and len(image) <= 500 else '',
    }


def fetch_product(gtin: str):
    url = f'{settings.PRODUCT_API_BASE_URL.rstrip("/")}/product/{gtin}.json'
    try:
        response = requests.get(
            url,
            params={'fields': REQUEST_FIELDS},
            headers={'User-Agent': settings.PRODUCT_API_USER_AGENT},
            timeout=settings.PRODUCT_API_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning('Product API unreachable for gtin=%s: %s', gtin, exc.__class__.__name__)
        raise ExternalLookupError('Product service unreachable') from exc

    if response.status_code == 404:
        return None
    if response.status_code != 200:
        logger.warning('Product API returned HTTP %s for gtin=%s', response.status_code, gtin)
        raise ExternalLookupError(f'Product service returned HTTP {response.status_code}')
    try:
        data = response.json()
    except ValueError as exc:
        raise ExternalLookupError('Product service returned invalid JSON') from exc
    if data.get('status') != 1 or not data.get('product'):
        return None
    return {'fields': map_product(data['product'], gtin), 'raw': data['product']}
