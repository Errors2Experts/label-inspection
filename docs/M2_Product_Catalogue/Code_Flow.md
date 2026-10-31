# Code Flow - Module 2: Product Catalogue

Format per FDS 27.3. Code: `apps/catalogue/` (`gtin.py`, `models.py`, `serializers.py`, `views.py`, `services/`, `page_views.py`, templates, `static/catalogue/js/`).

## 1. Barcode lookup (API only - inspection step 1)

> Design change (Oct 2026): the scanner page and `scanner.js` were removed to match the approved Product Catalogue design. `GET /api/products/lookup/` is kept for the Inspection module; the catalogue screens do not call it.
```
Inspection module sends the barcode
-> GET /api/products/lookup/?gtin=<value>      (session cookie)
-> ProductViewSet.lookup  [ProductLookupThrottle 60/min/user, IsAnyRole]
-> gtin.validate_gtin(): digits only, length 8/12/13/14, GS1 check digit
     invalid -> 400 {gtin: [message]}                         -> red message under the field
-> services.lookup.resolve_gtin(gtin, user)
     1. Product.objects.filter(gtin14 = zero-padded gtin)     [DB]
        hit -> {found: true, source: local, external_status: skipped}
     2. services.open_food_facts.fetch_product(gtin)           [External: GET {base}/product/{gtin}.json, 5 s timeout]
        timeout / network / HTTP != 200/404 / bad JSON -> ExternalLookupError -> external_status: unavailable
        404 or status 0                                         -> external_status: not_found
        found -> map_product() -> Product.objects.create(source=open_food_facts, source_data=raw)  [DB cache]
                 (IntegrityError from a parallel request -> load the existing row)
-> Response 200
     found:true  -> green card (name, brand, qty, MRP) + View / Edit buttons
     found:false -> message + "Add product manually" (/products/add/?gtin=...) ; inspection may continue with images + OCR
```

## 2. List and search
```
/products/ -> catalogue.js: GET /api/products/?q=&category=&source=&page=
-> get_queryset(): clean_search_term() (strip control chars, collapse spaces, cap 100 chars)
   Q(name|brand|manufacturer|category icontains) OR gtin contains digits (if >= 4 digits)
-> DRF pagination (20) -> {count, next, previous, results} -> table + pager
```

## 3. Add product manually
```
/products/add/[?gtin=] -> form -> POST /api/products/  (IsAnyRole write)
-> ProductSerializer: gtin cleaned + checksum, name required/trimmed, mrp >= 0, image_url http(s) only,
   duplicate check on gtin14 (UPC-A == EAN-13 form)
-> perform_create: source = manual, created_by = updated_by = request.user
-> Product.save(): gtin -> digits, gtin14 = zero-padded or NULL
-> 201 -> toast -> /products/<id>/
```

## 4. Edit product
```
/products/<id>/edit/ -> GET /api/products/<id>/ fills the form
Save -> PUT /api/products/<id>/ -> same validation (duplicate check excludes itself) -> updated_by = user -> 200 -> details page
(source is read-only: an Open Food Facts record stays labelled as such after correction)
```

## 5. Details
```
/products/<id>/ -> GET /api/products/<id>/ -> details card; image only when URL is http(s); 404 -> "Product not found."
```

## 6. Manual Product Entry (list page)

`/products/` -> `catalogue.js initList` -> "+ Add Product" (or a row's Edit) opens the Manual Product Entry card above the list.
Fields: Product Name (required), Brand, Barcode (GTIN/EAN), Net Quantity, Category (Dairy / Snacks / Beverages / Other), Manufacturer.
Save -> `POST /api/products/` (add) or `PUT /api/products/<id>/` (edit) -> card closes, list reloads, toast shown.
`/products/add/` and `/products/<id>/edit/` open the same page with the card already showing. An unchanged barcode is not re-validated on edit, so demo data stays editable.
Other model fields (MRP, ingredients, allergens, FSSAI licence, country of origin, image URL) are kept in the database and API for later modules but are not shown on any catalogue screen.
