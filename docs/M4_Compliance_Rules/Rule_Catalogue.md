# Rule Catalogue - Module 4

Seeded by `python manage.py seed_compliance` from `apps/compliance/fssai_rules.py` (checked 29 Oct 2026). Everything is editable in the app.

## Sources used (all in force)

| Source | Used for |
|---|---|
| Food Safety and Standards (Labelling and Display) Regulations, 2020 - FSSAI compendium Version VIII (09 Sep 2025); in force since 1 July 2022 | Mandatory label declarations, date marking, allergens, imported-food labelling |
| Food Safety and Standards (Vegan Foods) Regulations, 2022 (Reg 3-4) | Vegan logo and vegan claims (including imported vegan food) |
| Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011, Reg 2.1 | Dairy product checks |
| Food Safety and Standards (Import) Regulations, 2017 | Imported food: licence and shelf life at import |
| Legal Metrology (Packaged Commodities) Rules, 2011 | MRP, net quantity, month and year of import |

**Not included on purpose:** the First Amendment to the Labelling and Display Regulations (notified 2026, applies from 1 July 2027). It is not in force yet, so no rule, version or pack for it is seeded. Add it later as new rule versions and a new pack when it takes effect.

Result of a rule: **Compliant**, **Non-Compliant** (recorded as a violation), **Requires Verification** (inspector must check the physical label) or **Not Applicable** (rule condition not met). Rules that need the physical pack (symbols, nutrition panel, logos) are always *Inspector check*.

## FSSAI Basic Label Pack (v2.1) - active

Applies to: All packaged food.

| Rule ID | Rule name | Category | Severity | Check | Regulation |
|---|---|---|---|---|---|
| R-001 | FSSAI License Number must be present | Mandatory Declarations | Critical | Field check | FSS (Labelling & Display) Regs 2020, Reg 5(7)(b) |
| R-002 | MRP must be declared | Mandatory Declarations | Critical | Field check | Legal Metrology (Packaged Commodities) Rules 2011 |
| R-003 | Name of the food must be declared | Mandatory Declarations | Critical | Field check | FSS (Labelling & Display) Regs 2020, Reg 5(1) |
| R-004 | Name and address of manufacturer / packer must be declared | Mandatory Declarations | Critical | Field check | FSS (Labelling & Display) Regs 2020, Reg 5(6) |
| R-005 | Net quantity must be declared with a unit | Quantity & Price | Critical | Format check | FSS (Labelling & Display) Regs 2020, Reg 5(8); Legal Metrology (Packaged Commodities) Rules 2011 |
| R-006 | Date of manufacture and expiry date must be declared | Date Marking | Critical | Field check | FSS (Labelling & Display) Regs 2020, Reg 5(10)(a) |
| R-007 | Product must not be past its expiry date | Date Marking | Critical | Date check | FSS (Labelling & Display) Regs 2020, Reg 5(10) |
| R-008 | Batch / lot / code number must be declared | Date Marking | Major | Keyword check | FSS (Labelling & Display) Regs 2020, Reg 5(9) |
| R-009 | Veg / non-veg symbol on pack | Mandatory Declarations | Major | Inspector check | FSS (Labelling & Display) Regs 2020, Reg 5(4) |
| R-010 | Nutritional information panel | Mandatory Declarations | Major | Inspector check | FSS (Labelling & Display) Regs 2020, Reg 5(3) |
| R-011 | List of ingredients must be declared | Ingredients & Additives | Major | Field check | FSS (Labelling & Display) Regs 2020, Reg 5(2) |
| R-012 | Vegan claim: FSSAI vegan logo and no animal-derived ingredients | Vegan Foods | Major | Inspector check (only when a vegan claim / sweetener / additive is present) | FSS (Vegan Foods) Regs 2022, Reg 4 |

## Dairy Specific Pack (v1.3) - active

Applies to: Dairy products. Also applies every rule of **FSSAI Basic Label Pack**.

| Rule ID | Rule name | Category | Severity | Check | Regulation |
|---|---|---|---|---|---|
| R-013 | Allergen declaration: "Contains milk" | Special Declarations | Major | Keyword check | FSS (Labelling & Display) Regs 2020, Reg 5(14) |
| R-014 | Dairy product name must state the product type | Mandatory Declarations | Major | Inspector check | FSS (Food Products Standards & Food Additives) Regs 2011, Reg 2.1 |
| R-015 | Milk fat / composition as per the product standard | Special Declarations | Major | Inspector check | FSS (Food Products Standards & Food Additives) Regs 2011, Reg 2.1 |
| R-016 | Heat treatment declared (Pasteurised / UHT / Sterilised) | Special Declarations | Minor | Keyword check | FSS (Food Products Standards & Food Additives) Regs 2011, Reg 2.1 |
| R-017 | Storage instructions must be declared | Date Marking | Major | Keyword check | FSS (Labelling & Display) Regs 2020, Reg 5(13) |
| R-018 | Sweetener warning declaration | Special Declarations | Major | Keyword check (only when a vegan claim / sweetener / additive is present) | FSS (Labelling & Display) Regs 2020, Schedule II |
| R-019 | Additives declared by class name and INS / name | Ingredients & Additives | Minor | Inspector check (only when a vegan claim / sweetener / additive is present) | FSS (Labelling & Display) Regs 2020, Reg 5(5) |
| R-020 | Milk fat must not be replaced by other fat without declaration | Special Declarations | Major | Inspector check | FSS (Food Products Standards & Food Additives) Regs 2011, Reg 2.1 |

## Import Goods Pack (v1.0) - draft

Applies to: Imported products. Also applies every rule of **FSSAI Basic Label Pack**.

| Rule ID | Rule name | Category | Severity | Check | Regulation |
|---|---|---|---|---|---|
| R-021 | Importer name and address must be declared | Mandatory Declarations | Critical | Field check | FSS (Labelling & Display) Regs 2020, Reg 5(6) and 5(11) |
| R-022 | FSSAI import licence number must be a 14-digit number | Mandatory Declarations | Critical | Format check | FSS (Labelling & Display) Regs 2020, Reg 5(7); FSS (Import) Regs 2017 |
| R-023 | Country of origin must be declared | Special Declarations | Critical | Keyword check | FSS (Labelling & Display) Regs 2020, Reg 5(12) |
| R-024 | Month and year of import must be declared | Date Marking | Major | Keyword check | Legal Metrology (Packaged Commodities) Rules 2011 |
| R-025 | Remaining shelf life at import | Date Marking | Major | Inspector check | FSS (Import) Regs 2017 |
| R-026 | Imported vegan food must carry the FSSAI vegan logo | Vegan Foods | Major | Inspector check (only when a vegan claim / sweetener / additive is present) | FSS (Vegan Foods) Regs 2022, Reg 3 and 4 |

## What is not encoded

- Font size, colour contrast, symbol size and placement, nutrition table layout and the vegan logo artwork can only be checked on the physical label, so they appear as inspector checks.
- Exemptions (single-ingredient foods, small packs, short shelf-life foods) are handled by the *Requires Verification* outcome rather than hard-coded.
- Seeded rules are inspection assistance, not legal advice. Have a domain reviewer confirm them against the Gazette text before production use.
