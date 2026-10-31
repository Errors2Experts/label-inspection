"""Seed content: FSSAI label rules in force today, written as data for the rules engine (apps.compliance.engine).

Sources (checked 29 Oct 2026). Only rules that are IN FORCE are seeded - nothing from upcoming amendments:
  * Food Safety and Standards (Labelling and Display) Regulations, 2020 - FSSAI compendium Version VIII (09 Sep 2025),
    in force since 1 July 2022 (clause numbers below are from it).
  * Food Safety and Standards (Vegan Foods) Regulations, 2022 - gazetted June 2022; Reg 4: vegan food must carry the
    FSSAI vegan logo and must also comply with the Labelling and Display Regulations 2020.
  * Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011, Reg 2.1 (dairy products).
  * Food Safety and Standards (Import) Regulations, 2017 (imported food).
  * Legal Metrology (Packaged Commodities) Rules, 2011 (MRP, net quantity, month and year of import).
The First Amendment to the Labelling and Display Regulations (in force 1 July 2027) is deliberately NOT included.

Everything here is editable in the app (Compliance Rules > Edit). It is inspection assistance, not legal advice.
Fields a rule can read: product_name, brand, mrp, net_quantity, manufacturing_date, best_before, expiry_date,
ingredients, fssai_license, manufacturer, packer, importer, other_declarations (see engine.evaluator.DATA_FIELDS).
Rules that need the physical label (symbols, nutrition panel, logo) are `manual_check` -> Requires Verification.
"""

LD = 'FSS (Labelling & Display) Regs 2020'
LM = 'Legal Metrology (Packaged Commodities) Rules 2011'
VEGAN = 'FSS (Vegan Foods) Regs 2022'
DAIRY = 'FSS (Food Products Standards & Food Additives) Regs 2011, Reg 2.1'
IMPORT = 'FSS (Import) Regs 2017'
ADDRESS = ['manufacturer', 'packer', 'importer']
V = 'non_compliant'
RV = 'requires_verification'
VEGAN_CLAIM = [{'field': ['product_name', 'other_declarations'], 'op': 'contains_any', 'values': ['vegan']}]
SWEETENERS = ['aspartame', 'acesulfame', 'sucralose', 'saccharin', 'neotame', 'sweetener']

CATEGORIES = [
    ('Mandatory Declarations', 'Particulars every pre-packaged food label must carry (Reg 5, L&D 2020)'),
    ('Quantity & Price', 'Net quantity and price declarations (Reg 5(8); Legal Metrology)'),
    ('Date Marking', 'Manufacture / expiry dates, batch, storage and import dates (Reg 5(9)-(10))'),
    ('Ingredients & Additives', 'Ingredient list and additive declarations (Reg 5(2), 5(5))'),
    ('Special Declarations', 'Allergens, origin, sweetener warnings and product-standard declarations'),
    ('Vegan Foods', 'Vegan logo and vegan claims (Vegan Foods Regulations 2022)'),
]

# code, title, category, severity, regulation ref, rule_type, parameters, applies_when, on_fail, failure message
BASIC_RULES = [
    ('R-001', 'FSSAI License Number must be present', 'Mandatory Declarations', 'critical', f'{LD}, Reg 5(7)(b)',
     'required', {'fields': ['fssai_license']}, [], V, 'FSSAI licence / registration number is missing.'),
    ('R-002', 'MRP must be declared', 'Mandatory Declarations', 'critical', LM,
     'required', {'fields': ['mrp']}, [], V, 'Maximum Retail Price (MRP) is missing.'),
    ('R-003', 'Name of the food must be declared', 'Mandatory Declarations', 'critical', f'{LD}, Reg 5(1)',
     'required', {'fields': ['product_name']}, [], V, 'Name of the food is missing from the label.'),
    ('R-004', 'Name and address of manufacturer / packer must be declared', 'Mandatory Declarations', 'critical',
     f'{LD}, Reg 5(6)', 'required', {'fields': ADDRESS, 'mode': 'any'}, [], V,
     'Name and address of the manufacturer / packer / importer is missing.'),
    ('R-005', 'Net quantity must be declared with a unit', 'Quantity & Price', 'critical', f'{LD}, Reg 5(8); {LM}',
     'quantity_format', {'field': 'net_quantity', 'on_missing': 'fail'}, [], V,
     'Net quantity is missing or is not a number with a unit (e.g. 500 g).'),
    ('R-006', 'Date of manufacture and expiry date must be declared', 'Date Marking', 'critical', f'{LD}, Reg 5(10)(a)',
     'required', {'fields': ['manufacturing_date', 'expiry_date']}, [], V,
     'Date of manufacture / packing or expiry / use-by date is missing.'),
    ('R-007', 'Product must not be past its expiry date', 'Date Marking', 'critical', f'{LD}, Reg 5(10)',
     'not_expired', {'field': 'expiry_date'}, [], V, 'Product is past its expiry date.'),
    ('R-008', 'Batch / lot / code number must be declared', 'Date Marking', 'major', f'{LD}, Reg 5(9)',
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['batch', 'lot', 'b.no', 'code'],
                      'fail_detail': 'No batch / lot / code number found in the declarations.'}, [], RV, ''),
    ('R-009', 'Veg / non-veg symbol on pack', 'Mandatory Declarations', 'major', f'{LD}, Reg 5(4)',
     'manual_check', {'prompt': 'Check the pack: green circle-in-square (veg) or brown triangle-in-square (non-veg), '
                                'on the principal display panel near the name of the food, on a contrasting background.'}, [], RV, ''),
    ('R-010', 'Nutritional information panel', 'Mandatory Declarations', 'major', f'{LD}, Reg 5(3)',
     'manual_check', {'prompt': 'Check the nutrition panel: energy, protein, carbohydrate (total and added sugars), total fat, '
                                'saturated fat, trans fat and sodium, per 100 g / 100 ml and per serve with %RDA.'}, [], RV, ''),
    ('R-011', 'List of ingredients must be declared', 'Ingredients & Additives', 'major', f'{LD}, Reg 5(2)',
     'required', {'fields': ['ingredients']}, [], RV, 'Ingredient list not found (single-ingredient foods may be exempt).'),
    ('R-012', 'Vegan claim: FSSAI vegan logo and no animal-derived ingredients', 'Vegan Foods', 'major', f'{VEGAN}, Reg 4',
     'manual_check', {'prompt': 'The pack makes a vegan claim: check it carries the FSSAI-approved vegan logo, that no ingredient, '
                                'additive or flavouring is of animal origin, and that the other label particulars of the '
                                'Labelling and Display Regulations 2020 are present.'}, VEGAN_CLAIM, RV, ''),
]

DAIRY_RULES = [
    ('R-013', 'Allergen declaration: "Contains milk"', 'Special Declarations', 'major', f'{LD}, Reg 5(14)',
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['contains milk', 'contains: milk', 'milk and milk products', 'allergen'],
                      'fail_detail': 'No "Contains milk" allergen statement found.'}, [], RV, ''),
    ('R-014', 'Dairy product name must state the product type', 'Mandatory Declarations', 'major', DAIRY,
     'manual_check', {'prompt': 'Check the name describes the standardised product (for example Table Butter, Ghee, Paneer, Curd, '
                                'Cheese) and not a misleading generic name.'}, [], RV, ''),
    ('R-015', 'Milk fat / composition as per the product standard', 'Special Declarations', 'major', DAIRY,
     'manual_check', {'prompt': 'Check any declared milk fat / milk solids / moisture figures meet the standard for the product type '
                                '(for example butter must meet its minimum milk fat).'}, [], RV, ''),
    ('R-016', 'Heat treatment declared (Pasteurised / UHT / Sterilised)', 'Special Declarations', 'minor', DAIRY,
     'contains_any', {'fields': ['product_name', 'other_declarations'], 'keywords': ['pasteuri', 'uht', 'steril', 'boiled'],
                      'fail_detail': 'No heat-treatment wording found. Confirm whether the product is pasteurised, UHT or sterilised.'}, [], RV, ''),
    ('R-017', 'Storage instructions must be declared', 'Date Marking', 'major', f'{LD}, Reg 5(13)',
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['store', 'refrigerat', 'keep in', 'keep cool', 'chill'],
                      'fail_detail': 'No storage instruction found (for example "Store under refrigeration").'}, [], RV, ''),
    ('R-018', 'Sweetener warning declaration', 'Special Declarations', 'major', f'{LD}, Schedule II',
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['not recommended for children', 'phenylketonuric', 'contains artificial sweetener', 'contains sweetener'],
                      'fail_detail': 'Product contains a sweetener but no warning statement was found.'},
     [{'field': 'ingredients', 'op': 'contains_any', 'values': SWEETENERS}], V, 'Required sweetener warning is missing.'),
    ('R-019', 'Additives declared by class name and INS / name', 'Ingredients & Additives', 'minor', f'{LD}, Reg 5(5)',
     'manual_check', {'prompt': 'Ingredient list mentions additives: confirm each is declared with its functional class and specific name or INS number.'},
     [{'field': 'ingredients', 'op': 'contains_any', 'values': ['ins', 'colour', 'color', 'preservative', 'emulsifier', 'antioxidant',
                                                              'stabiliser', 'stabilizer', 'acidity regulator', 'flavour', 'flavor']}], RV, ''),
    ('R-020', 'Milk fat must not be replaced by other fat without declaration', 'Special Declarations', 'major', DAIRY,
     'manual_check', {'prompt': 'Check that the name and ingredient list agree: a product with vegetable fat or other non-milk fat must not '
                                'be named or presented as butter, ghee, cream or similar milk-fat products.'}, [], RV, ''),
]

IMPORT_RULES = [
    ('R-021', 'Importer name and address must be declared', 'Mandatory Declarations', 'critical', f'{LD}, Reg 5(6) and 5(11)',
     'required', {'fields': ['importer']}, [], V, 'Name and address of the importer in India is missing.'),
    ('R-022', 'FSSAI import licence number must be a 14-digit number', 'Mandatory Declarations', 'critical', f'{LD}, Reg 5(7); {IMPORT}',
     'regex', {'fields': ['fssai_license'], 'pattern': r'(?<!\d)\d{14}(?!\d)', 'on_missing': 'fail',
               'fail_detail': 'Licence number is missing or is not a 14-digit number.'}, [], V,
     'FSSAI licence number of the importer is missing or not a valid 14-digit number.'),
    ('R-023', 'Country of origin must be declared', 'Special Declarations', 'critical', f'{LD}, Reg 5(12)',
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['country of origin', 'origin', 'made in', 'product of'],
                      'fail_detail': 'No country of origin found in the declarations.'}, [], RV, ''),
    ('R-024', 'Month and year of import must be declared', 'Date Marking', 'major', LM,
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['month and year of import', 'date of import', 'import date', 'imported on', 'imported in'],
                      'fail_detail': 'No month / year of import found in the declarations.'}, [], RV, ''),
    ('R-025', 'Remaining shelf life at import', 'Date Marking', 'major', IMPORT,
     'manual_check', {'prompt': 'Check the product had at least 60% of its shelf life (or 3 months before expiry, whichever is less) '
                                'at the time of import, using the import documents.'}, [], RV, ''),
    ('R-026', 'Imported vegan food must carry the FSSAI vegan logo', 'Vegan Foods', 'major', f'{VEGAN}, Reg 3 and 4',
     'manual_check', {'prompt': 'Imported food sold as vegan must carry the FSSAI vegan logo like any vegan food sold in India. '
                                'Check the logo is on the pack.'}, VEGAN_CLAIM, RV, ''),
]

RULES = BASIC_RULES + DAIRY_RULES + IMPORT_RULES

PACKS = [
    dict(name='FSSAI Basic Label Pack', version='v2.1', applies_to='All packaged food', status='active',
         effective_from='2022-07-01', regulation_ref=f'{LD}; {VEGAN}', product_categories=[], extends=None,
         description='Core label checks for every pre-packaged food, from the Labelling and Display Regulations 2020, '
                     'Legal Metrology rules and the Vegan Foods Regulations 2022.',
         rules=[r[0] for r in BASIC_RULES]),
    dict(name='Dairy Specific Pack', version='v1.3', applies_to='Dairy products', status='active',
         effective_from='2022-07-01', regulation_ref=DAIRY, product_categories=['Dairy'], extends='FSSAI Basic Label Pack',
         description='Extra checks for milk and milk products. Also applies every rule of the FSSAI Basic Label Pack.',
         rules=[r[0] for r in DAIRY_RULES]),
    dict(name='Import Goods Pack', version='v1.0', applies_to='Imported products', status='draft',
         effective_from=None, regulation_ref=f'{IMPORT}; {LD}, Reg 5(11)-(12)', product_categories=[], extends='FSSAI Basic Label Pack',
         description='Extra checks for imported food. Draft: not used for evaluation until an Admin activates it.',
         rules=[r[0] for r in IMPORT_RULES]),
]
