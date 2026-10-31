# UTC - Module 2: Product Catalogue

| Item | Detail |
|---|---|
| Developer | Manishashri P |
| Window | 16/10/2026 - 25/10/2026 |
| FDS reference | Section 10 |
| Automated tests | `apps/catalogue/tests/` (40 tests; run `python manage.py test apps.catalogue`) |
| Test database | SQLite (external Open Food Facts calls are mocked) |
| Status | Draft - automated tests passing; manual browser testing pending |

## 1. Use cases
| ID | Use case | Actor | Main flow |
|---|---|---|---|
| UC-M2-01 | Identify product by barcode | Inspection module (API) | GTIN -> validate -> local catalogue -> external API -> product (no scanner screen in the catalogue) |
| UC-M2-02 | Handle unknown product | All roles | Not found / API down -> clear message -> add manually or continue with images + OCR |
| UC-M2-03 | Browse and search catalogue | All roles | Search name/brand/manufacturer/barcode, filter category/source, page through results |
| UC-M2-04 | View product details | All roles | Open product -> see all stored label data |
| UC-M2-05 | Add product manually | All roles | Fill form (barcode optional) -> validate -> save as source=manual |
| UC-M2-06 | Edit product | All roles | Change fields -> validate (unique barcode) -> save, updated_by recorded |

## 2. Test cases
| Test ID | Scenario | Steps / input | Expected result | Status |
|---|---|---|---|---|
| M2-TC-001 | Valid barcode formats | EAN-13, UPC-A, EAN-8 and a GTIN-14 with correct check digits | All accepted | Pass |
| M2-TC-002 | Formatting tolerated | '4006 381-333931' | Normalised to digits only | Pass |
| M2-TC-003 | Wrong length | 7, 10 and 15 digit values | ValueError with length message | Pass |
| M2-TC-004 | Bad check digit | EAN-13 with last digit changed | ValueError mentioning check digit | Pass |
| M2-TC-005 | Empty / letters only | '' and 'abc' | ValueError | Pass |
| M2-TC-006 | Canonical form | UPC-A and the same code as EAN-13 | Identical 14-digit value | Pass |
| M2-TC-010 | Authentication | Anonymous GET /api/products/ | 401/403 | Pass |
| M2-TC-011 | Read access | Admin, Supervisor, Inspector GET list and detail | 200 for each | Pass |
| M2-TC-012 | Search | ?q=butter, ?q=nestle, ?q=<partial barcode> | Only matching products | Pass |
| M2-TC-013 | Search sanitising | Control chars, 5000-char string, SQL-looking text | 200, no error, no leak | Pass |
| M2-TC-014 | Filters | ?source=open_food_facts, ?category=dairy, bogus source | Filtered; bogus ignored | Pass |
| M2-TC-015 | Pagination | GET list | Response has count, next, previous, results | Pass |
| M2-TC-020 | Manual entry | Inspector POST valid product with spaced barcode | 201; source=manual; barcode normalised | Pass |
| M2-TC-021 | Product without barcode | POST name only; then a second one | Both 201 (NULL barcodes do not clash) | Pass |
| M2-TC-022 | Mandatory field | POST without name / blank name | 400 on name | Pass |
| M2-TC-023 | Barcode validation | Bad check digit, wrong length | 400 on gtin | Pass |
| M2-TC-024 | Duplicate barcode | Create UPC-A, then the same code as EAN-13 | 400 'already exists' | Pass |
| M2-TC-025 | MRP validation | mrp = -5 | 400 on mrp | Pass |
| M2-TC-026 | Image URL safety | image_url = javascript:alert(1) | 400 on image_url | Pass |
| M2-TC-027 | Edit | PUT new name/MRP on a product | 200; saved; updated_by set; source unchanged | Pass |
| M2-TC-028 | Duplicate on edit | Change product B's barcode to product A's | 400 | Pass |
| M2-TC-029 | No delete | DELETE /api/products/{id}/ | 405 (history must keep valid product links) | Pass |
| M2-TC-030 | Read-only fields | POST with source and created_by in payload | Ignored; server values used | Pass |
| M2-TC-040 | Local lookup | GET lookup?gtin= for a catalogued barcode | found, source=local, no external call | Pass |
| M2-TC-041 | UPC/EAN equivalence | Catalogue holds UPC-A; look up its EAN-13 form | Found locally | Pass |
| M2-TC-042 | Malformed barcode | gtin missing / bad check digit / letters | 400 with message | Pass |
| M2-TC-043 | External lookup | Unknown locally, API returns product; look up twice | Fetched, saved; 2nd call is local | Pass |
| M2-TC-044 | Unknown product | API returns status 0 and HTTP 404 | found=false, not_found, can_continue=true, 200 | Pass |
| M2-TC-045 | API timeout | requests raises Timeout | 200 found=false, external_status=unavailable, manual-entry message | Pass |
| M2-TC-046 | API HTTP 500 | Product service errors | Same graceful 'unavailable' result | Pass |
| M2-TC-047 | API garbage | 200 response that is not JSON | Graceful 'unavailable' result | Pass |
| M2-TC-048 | Field mapping | Payload with tags, multiple brands, http image, no name | Clean Product fields | Pass |
| M2-TC-049 | Authentication | Anonymous GET lookup | 401/403 | Pass |
| M2-TC-050 | Rate limit | 61 lookups in a minute | 61st returns 429 | Pass |
| M2-TC-051 | Outbound call | Unknown barcode lookup | requests.get called with configured timeout and User-Agent | Pass |
| M2-TC-060 | Page access | Anonymous GET catalogue pages | 302 redirect to /login/?next= | Pass |
| M2-TC-061 | Role access | Admin, Supervisor, Inspector open list, add, details, edit | 200 for every role | Pass |
| M2-TC-062 | Navigation | Open dashboard as inspector | Product Catalogue link present and not marked 'coming soon' | Pass |
| M2-TC-063 | Assets | Resolve catalogue JS files | Found by staticfiles | Pass |
| M2-TC-064 | Demo data | Run seed_products twice | 5 valid-barcode products, no duplicates | Pass |
| M2-TC-065 | Design | list and add pages | no scanner route/link; entry form has only the 6 designed fields | Pass |
| M2-TC-066 | Edit | save a seeded product without touching its barcode | 200 (barcode not re-validated) | Pass |

## 3. Acceptance criteria traceability (FDS 10.10)
| Acceptance criterion | Covered by |
|---|---|
| Supported barcodes resolve to product data when available | M2-TC-040, 041, 043, 048 |
| Unknown products can be entered manually and used in inspections | M2-TC-044, 045, 046, 047 (graceful result), 020, 021 (manual entry) |
| Product search and detail views function correctly | M2-TC-011, 012, 013, 014, 015, 061 |
| Barcode format validated; API timeouts / not-found handled (FDS 10.8) | M2-TC-001 to 006, 023, 042, 044 to 047, 051 |
| Write operations authorised; search input sanitised (FDS 10.8) | M2-TC-010, 013, 020, 049 |

## 4. Manual UI checklist (browser; not yet run)
| ID | Check | Expected |
|---|---|---|
| M2-UI-01 | Open /products/ and search while typing | Table filters after a short pause; counts and paging correct |
| M2-UI-06 | Add product: leave name empty, bad barcode, duplicate barcode | Field-level messages |
| M2-UI-07 | Edit product and save | Toast, redirect to details, values updated |
| M2-UI-08 | Product details with / without image URL | Image shown only for http(s) URLs |
| M2-UI-09 | Resize below 900px | Layout matches M1 (menu button, single-column form) |
| M2-UI-09 | Click "+ Add Product" | Manual Product Entry card with 6 fields (Product Name *, Brand, Barcode, Net Quantity, Category, Manufacturer), Save Product and Cancel |
| M2-UI-10 | Click Edit on a row | Card opens filled with that product; saving updates the row |
| M2-UI-11 | Look for scanner, camera or extra fields (MRP, ingredients, allergens, licence, image URL) | None on any catalogue screen |
