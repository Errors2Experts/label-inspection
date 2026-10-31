from django.core.management.base import BaseCommand

from apps.catalogue.models import Product

# Demo data only (the five products shown in the design). Barcodes are illustrative, not verified GS1 codes.
DEMO = [
    ('Amul Pasteurised Butter', 'Amul', '8901030865483', 'Dairy', '500 g'),
    ('Maggi 2-Minute Noodles', 'Nestlé', '8901058901234', 'Snacks', '70 g'),
    ('Britannia Good Day Cookies', 'Britannia', '8901063123456', 'Snacks', '200 g'),
    ('Tata Salt', 'Tata', '8901030865999', 'Other', '1 kg'),
    ('Parle-G Original', 'Parle', '8901719100012', 'Snacks', '800 g'),
]


class Command(BaseCommand):
    help = 'Create a few demo products for local development (never run in production).'

    def handle(self, *args, **options):
        for name, brand, gtin, category, qty in DEMO:
            _, created = Product.objects.get_or_create(
                gtin14=gtin.zfill(14),
                defaults={'gtin': gtin, 'name': name, 'brand': brand, 'category': category, 'net_quantity': qty},
            )
            self.stdout.write(f'{"created" if created else "exists "} {name} ({gtin})')
