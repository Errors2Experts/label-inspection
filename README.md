# LIP - Label Inspection Project

AI-Integrated Food Product Inspection & Compliance System
(Python / Django, DRF, PostgreSQL, PaddleOCR, ReportLab). Built from FDS v1.0 (`docs/FDS/`).

Planned completion: **31 Oct 2026**.

## Modules in this delivery

| # | Module | App | Developer | Window |
|---|--------|-----|-----------|--------|
| M1 | Authentication and Users (role based) | `apps/accounts` | Manishashri P | 05-15 Oct |
| M2 | Product Catalogue | `apps/catalogue` | Manishashri P | 16-25 Oct |
| M4 | Compliance Rules | `apps/compliance` | Sathish Vishnu A | 16-25 Oct |

This project contains only M1, M2 and M4. M3 (Inspection), M5 (History), M6 (Reports) and M7 (Dashboard) are built separately and appear in the sidebar as "coming soon". M4 does not depend on them: it evaluates inspector-verified label data passed to its API.

## Quick start

Requires Python 3.12+.

```bash
python -m pip install -r requirements.txt
export USE_SQLITE=1            # PowerShell: $env:USE_SQLITE = "1"; omit to use PostgreSQL (see .env.example)
python manage.py migrate
python manage.py seed_users        # demo users (dev only)
python manage.py seed_products     # demo products (dev only)
python manage.py seed_compliance   # 6 categories, 26 FSSAI rules, 3 rule packs
python manage.py runserver
```

Open http://localhost:8000/ and sign in as `admin1`, `supervisor1` or `inspector1` (password `Lip@12345`).
Tests: `python manage.py test apps` (141 tests).

Settings come from environment variables. Copy `.env.example` to `.env` (next to `manage.py`); it is loaded automatically.

## Module status

| Module | Status |
|--------|--------|
| M1 Authentication and Users | Back end + 9 screens + 52 tests + docs (`docs/M1_Authentication_Users/`) |
| M2 Product Catalogue | Back end + screens (list/search with category filter, inline Manual Product Entry for add/edit, details; no scanner) + 43 tests + docs (`docs/M2_Product_Catalogue/`) |
| M4 Compliance Rules | Rules engine, versioned rules, categories, rule packs, evaluation API, results and violations; 11 screens (overview matches the approved design); 47 tests; UTC / Impact Analysis / Code Flow / Rule Catalogue (`docs/M4_Compliance_Rules/`) |

## Compliance rules (M4) in brief

- Roles: Admin and Supervisor manage rules, categories and packs; every role can call evaluate; inspectors see only their own results.
- Editing a rule's logic never changes history: it saves a new version, and packs pin exact versions.
- Seeded packs (rules in force only): **FSSAI Basic Label Pack v2.1** (12 rules, all packaged food), **Dairy Specific Pack v1.3** (8 rules, also applies the Basic pack), **Import Goods Pack v1.0** (6 rules, Draft). Sources: FSS Labelling & Display Regulations 2020 (compendium Version VIII), FSS Vegan Foods Regulations 2022, dairy standards, Import Regulations 2017 and Legal Metrology rules. The First Amendment 2026 (in force 1 July 2027) is intentionally not included.
- Evaluate from code: `apps.compliance.services.evaluate(data, pack, user, reference)`, or `POST /api/compliance/evaluate/`. Only pass inspector-verified data.
- Rule sources and what is not encoded: `docs/M4_Compliance_Rules/Rule_Catalogue.md`.

## Git workflow

- `main` - stable, protected. `develop` - integration branch.
- One branch per module/feature: `feature/m1-auth`, `feature/m3-inspection`, ...
- Open a pull request into `develop`; Tech Lead reviews before merge.
- Never commit `.env`, API keys, or uploaded images.

## Per-module deliverables (FDS section 27)

Each `docs/Mx_*/` folder holds `UTC.md`, `Impact_Analysis.md`, `Code_Flow.md`.
Complete them inside the module window, alongside testing and bug fixing.

## Key rules from the FDS

- Inspector verification is mandatory before compliance evaluation; AI has no final authority.
- Unknown barcodes must never block an inspection (manual entry / OCR fallback).
- Rules are configurable and versioned; history keeps the rule version used.
