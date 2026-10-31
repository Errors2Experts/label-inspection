# Porting M2 into the team repository

M2 depends on M1 (`apps.accounts`). Port M1 first.

1. Copy `apps/catalogue/` (including `migrations/0001_initial.py`).
2. `settings.py`: add `'apps.catalogue'` to `INSTALLED_APPS`; add `PRODUCT_API_BASE_URL`, `PRODUCT_API_TIMEOUT`,
   `PRODUCT_API_USER_AGENT`; add `'product_lookup': '60/min'` to `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`.
3. Root `urls.py`: `path('api/', include('apps.catalogue.urls'))` and `path('', include('apps.catalogue.page_urls'))`.
4. Shared files: merge the "Catalogue" block and the `textarea` rules from `static/css/lip.css`.
5. Navigation (`apps/accounts/navigation.py`): set `'ready': True` for `catalogue`.
6. `pip install requests` (already in requirements.txt), then `python manage.py migrate` and `python manage.py test apps.catalogue` (expect 40 passing).
7. Optional demo data: `python manage.py seed_products` (fictional barcodes, dev only).
