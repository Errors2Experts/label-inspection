from django.conf import settings
from django.core.validators import MinValueValidator, URLValidator
from django.db import models

from .gtin import normalize_gtin, to_gtin14


class ProductSource(models.TextChoices):
    MANUAL = 'manual', 'Manual entry'
    OPEN_FOOD_FACTS = 'open_food_facts', 'Open Food Facts'


class Product(models.Model):
    """A packaged food product (FDS 10.6). The barcode lives on the product itself.

    `gtin` keeps what the user entered (8/12/13/14 digits); `gtin14` is the zero-padded canonical value
    used for lookup and uniqueness, so a UPC-A and its EAN-13 form cannot both exist. Products may have no
    barcode (manual entry when the code is unreadable): `gtin` is then '' and `gtin14` NULL.
    """

    gtin = models.CharField(max_length=14, blank=True)
    gtin14 = models.CharField(  # noqa: DJ001 - NULL (not '') so many barcode-less products satisfy `unique`
        max_length=14, unique=True, null=True, blank=True, editable=False
    )
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=150, blank=True)
    category = models.CharField(max_length=150, blank=True)
    net_quantity = models.CharField(max_length=50, blank=True, help_text='As printed, e.g. "500 g"')
    mrp = models.DecimalField(
        'MRP (INR)', max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    ingredients = models.TextField(blank=True)
    allergens = models.TextField(blank=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    fssai_license = models.CharField('FSSAI licence no.', max_length=30, blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)
    image_url = models.URLField(max_length=500, blank=True, validators=[URLValidator(schemes=['http', 'https'])])

    source = models.CharField(max_length=20, choices=ProductSource.choices, default=ProductSource.MANUAL)
    source_data = models.JSONField(default=dict, blank=True, help_text='Raw external payload, kept for audit')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        indexes = [models.Index(fields=['name']), models.Index(fields=['brand'])]

    def __str__(self):
        return f'{self.name} ({self.gtin or "no barcode"})'

    def save(self, *args, **kwargs):
        self.gtin = normalize_gtin(self.gtin)
        self.gtin14 = to_gtin14(self.gtin) if self.gtin else None
        super().save(*args, **kwargs)
