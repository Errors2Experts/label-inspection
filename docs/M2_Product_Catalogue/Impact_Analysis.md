# Impact Analysis - Module 2: Product Catalogue

| Item | Detail |
|---|---|
| Developer | Manishashri P |
| Window | 16/10/2026 - 25/10/2026 |
| Status | Draft |

## 1. New functionality
Product catalogue (list, search, filters, details, manual add, edit), barcode validation (GS1 check digit), barcode lookup with local-first resolution and Open Food Facts fallback with caching, graceful handling of unknown products and API failures, `seed_products` demo command.

## 2. Existing functionality affected
| Area | Change |
|---|---|
| M1 navigation | `Product Catalogue` menu item switched to `ready: True` |
| Project URLs | `config/urls.py` includes `apps.catalogue.page_urls` |
| Settings | New: `PRODUCT_API_TIMEOUT`, `PRODUCT_API_USER_AGENT`, throttle rate `product_lookup` (existing `PRODUCT_API_BASE_URL` now used) |
| Shared CSS | `lip.css` gained textarea and product-card styles (no changes to existing rules other than adding `textarea` to the input rules) |

## 3. Database impact
| Table `catalogue_product` | Detail |
|---|---|
| `gtin` | Barcode as entered (digits, 8/12/13/14) or empty |
| `gtin14` | Zero-padded canonical value, **unique**, NULL when no barcode. Stops a UPC-A and its EAN-13 form from being stored twice |
| Label fields | name (required), brand, category, net_quantity, mrp, ingredients, allergens, manufacturer, fssai_license, country_of_origin, image_url |
| `source` / `source_data` | `manual` or `open_food_facts`; raw external payload kept for audit |
| `created_by` / `updated_by` | FK to `AUTH_USER_MODEL`, SET_NULL |
| Deletion | No delete endpoint, so inspection history (M3/M5) can keep valid product links |

## 4. API impact
| Endpoint | Method | Access | Notes |
|---|---|---|---|
| /api/products/ | GET | All roles | `?q=` `?category=` `?source=`; paginated (20) |
| /api/products/ | POST | All roles (FDS 7.2) | source forced to `manual`; barcode validated + unique |
| /api/products/{id}/ | GET, PUT, PATCH | All roles | PUT/PATCH set `updated_by` |
| /api/products/lookup/?gtin= | GET | All roles | 200 found / 200 not found / 400 malformed barcode; 60 requests per minute per user |

**Lookup result contract (for Module 3):** `found` (bool), `source` (`local` / `open_food_facts`), `external_status` (`skipped` / `found` / `not_found` / `unavailable`), `product` (when found), `can_continue` and `detail` (when not found). An unknown product or unavailable service is **never an HTTP error**, so the inspection wizard can continue with manual entry or images + OCR.

## 5. UI impact
Screens: Product List (with search - FDS "Product Search" is the search box + filters on this screen), Product Details; Add / Edit Product are the Manual Product Entry card on the list page (scanner screen removed - design change). Routes `/products/`, `/products/add/`, `/products/<id>/`, `/products/<id>/edit/`.

## 6. Integration impact
| Module | Dependency |
|---|---|
| M1 | Roles (`IsAnyRole`, `roles_required`), `AUTH_USER_MODEL`, shared layout |
| M3 Inspection | Step 1 "Identify Product" should call `/api/products/lookup/?gtin=` and store `product.id`; the "Product not in catalogue - proceed with images only" checkbox maps to `found: false`. Typeahead uses `/api/products/?q=` |
| M4 Compliance | Evaluates against Product fields (MRP, net quantity, FSSAI, ingredients, allergens) |
| M5 / M6 | Show product name / barcode via FK; products are never deleted |
| M7 | Catalogue counts, source mix |

## 7. Dependencies
`requests` (external API), Open Food Facts API (proposed source, FDS 5), browser `BarcodeDetector` or the html5-qrcode library (loaded from jsDelivr only when the native detector is missing).

## 8. Risks and mitigations
| Risk | Mitigation |
|---|---|
| External API slow / down | 5 s timeout (env-configurable), every failure becomes `external_status: unavailable` |
| Open Food Facts lacks FSSAI, MRP and many Indian products | Manual entry and edit; OCR (M3) is the intended source for those fields |
| External data is unreviewed but cached in the catalogue | Marked `source=open_food_facts`; editable. **Confirm with Tech Lead whether cached records need a "verified" flag** |
| Bad / mistyped barcodes | GS1 check-digit validation on lookup, create and edit |
| Duplicate products (UPC vs EAN forms) | Canonical `gtin14` unique constraint |
| Search abuse / injection | Input trimmed, control characters removed, length capped, ORM parameterisation; tested |
| Unsafe image URLs | Only http/https accepted; front end renders `<img>` only for http(s) |
| Hammering the external API | Per-user throttle on lookup |
| Write permissions | FDS matrix gives all roles access; single constant `CATALOGUE_WRITE_ROLES` in `views.py` if the approved permissions differ. **Confirm with Tech Lead** |

## Design change (Oct 2026)
Scanner screen, `scanner.js`, `product_scan.html`, `product_form.html` removed. The catalogue UI follows the approved screenshots (six-field Manual Product Entry card on the list page, Dairy / Snacks / Beverages / Other categories, products listed in the order added). Barcode lookup API stays for M3.
