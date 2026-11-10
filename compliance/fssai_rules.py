"""Seed content: FSSAI label rules from the 2011 regulations, written as data for the rules engine (compliance.engine).

Only rules from the 2011 regulations are seeded (the client's competition was held under them):
  * Food Safety and Standards (Packaging and Labelling) Regulations, 2011 - Reg 2.2.2 (labelling of pre-packaged foods).
  * Food Safety and Standards (Food Products Standards and Food Additives) Regulations, 2011, Reg 2.1 (dairy products).
  * Food Safety and Standards (Licensing and Registration of Food Businesses) Regulations, 2011 (licence number).
  * Legal Metrology (Packaged Commodities) Rules, 2011 (MRP, net quantity, month and year of import).
Later regulations (Labelling and Display 2020, Vegan Foods 2022, Import 2017) are deliberately NOT included.

Everything here is editable in the app (Compliance Rules > Edit). It is inspection assistance, not legal advice.
Fields a rule can read: product_name, brand, mrp, net_quantity, manufacturing_date, best_before, expiry_date,
ingredients, fssai_license, manufacturer, packer, importer, other_declarations (see engine.evaluator.DATA_FIELDS).
Rules that need the physical label (symbols, nutrition panel) are `manual_check` -> Requires Verification.
"""

PL = 'FSS (Packaging & Labelling) Regs 2011, Reg 2.2.2'
LM = 'Legal Metrology (Packaged Commodities) Rules 2011'
LIC = 'FSS (Licensing & Registration of Food Businesses) Regs 2011'
DAIRY = 'FSS (Food Products Standards & Food Additives) Regs 2011, Reg 2.1'
ADDRESS = ['manufacturer', 'packer', 'importer']
V = 'non_compliant'
RV = 'requires_verification'

CATEGORIES = [
    ('Mandatory Declarations', 'Particulars every pre-packaged food label must carry (Packaging & Labelling Regs 2011)'),
    ('Quantity & Price', 'Net quantity and price declarations (Packaging & Labelling Regs 2011; Legal Metrology)'),
    ('Date Marking', 'Manufacture / expiry dates, batch, storage and import dates'),
    ('Ingredients & Additives', 'Ingredient list and additive declarations'),
    ('Special Declarations', 'Origin and product-standard declarations'),
]

# code, title, category, severity, regulation ref, rule_type, parameters, applies_when, on_fail, failure message
BASIC_RULES = [
    ('R-001', 'FSSAI License Number must be present', 'Mandatory Declarations', 'critical', LIC,
     'required', {'fields': ['fssai_license']}, [], V, 'FSSAI licence / registration number is missing.'),
    ('R-002', 'MRP must be declared', 'Mandatory Declarations', 'critical', LM,
     'required', {'fields': ['mrp']}, [], V, 'Maximum Retail Price (MRP) is missing.'),
    ('R-003', 'Name of the food must be declared', 'Mandatory Declarations', 'critical', PL,
     'required', {'fields': ['product_name']}, [], V, 'Name of the food is missing from the label.'),
    ('R-004', 'Name and address of manufacturer / packer must be declared', 'Mandatory Declarations', 'critical',
     PL, 'required', {'fields': ADDRESS, 'mode': 'any'}, [], V,
     'Name and address of the manufacturer / packer / importer is missing.'),
    ('R-005', 'Net quantity must be declared with a unit', 'Quantity & Price', 'critical', f'{PL}; {LM}',
     'quantity_format', {'field': 'net_quantity', 'on_missing': 'fail'}, [], V,
     'Net quantity is missing or is not a number with a unit (e.g. 500 g).'),
    ('R-006', 'Date of manufacture and expiry date must be declared', 'Date Marking', 'critical', PL,
     'required', {'fields': ['manufacturing_date', 'expiry_date']}, [], V,
     'Date of manufacture / packing or expiry / use-by date is missing.'),
    ('R-007', 'Product must not be past its expiry date', 'Date Marking', 'critical', PL,
     'not_expired', {'field': 'expiry_date'}, [], V, 'Product is past its expiry date.'),
    ('R-008', 'Batch / lot / code number must be declared', 'Date Marking', 'major', PL,
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['batch', 'lot', 'b.no', 'code'],
                      'fail_detail': 'No batch / lot / code number found in the declarations.'}, [], RV, ''),
    ('R-009', 'Veg / non-veg symbol on pack', 'Mandatory Declarations', 'major', PL,
     'manual_check', {'prompt': 'Check the pack: green circle-in-square (veg) or brown triangle-in-square (non-veg).'},
     [], RV, ''),
    ('R-010', 'Nutritional information panel', 'Mandatory Declarations', 'major', PL,
     'manual_check', {'prompt': 'Check the nutrition panel: energy value, protein, carbohydrate and fat, per 100 g / 100 ml '
                                'or per serving, plus any nutrient for which a claim is made.'}, [], RV, ''),
    ('R-011', 'List of ingredients must be declared', 'Ingredients & Additives', 'major', PL,
     'required', {'fields': ['ingredients']}, [], RV, 'Ingredient list not found (single-ingredient foods may be exempt).'),
]

DAIRY_RULES = [
    ('R-014', 'Dairy product name must state the product type', 'Mandatory Declarations', 'major', DAIRY,
     'manual_check', {'prompt': 'Check the name describes the standardised product (for example Table Butter, Ghee, Paneer, Curd, '
                                'Cheese) and not a misleading generic name.'}, [], RV, ''),
    ('R-015', 'Milk fat / composition as per the product standard', 'Special Declarations', 'major', DAIRY,
     'manual_check', {'prompt': 'Check any declared milk fat / milk solids / moisture figures meet the standard for the product type '
                                '(for example butter must meet its minimum milk fat).'}, [], RV, ''),
    ('R-016', 'Heat treatment declared (Pasteurised / UHT / Sterilised)', 'Special Declarations', 'minor', DAIRY,
     'contains_any', {'fields': ['product_name', 'other_declarations'], 'keywords': ['pasteuri', 'uht', 'steril', 'boiled'],
                      'fail_detail': 'No heat-treatment wording found. Confirm whether the product is pasteurised, UHT or sterilised.'}, [], RV, ''),
    ('R-017', 'Storage instructions must be declared', 'Date Marking', 'major', PL,
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['store', 'refrigerat', 'keep in', 'keep cool', 'chill'],
                      'fail_detail': 'No storage instruction found (for example "Store under refrigeration").'}, [], RV, ''),
    ('R-019', 'Additives declared by class name and INS / name', 'Ingredients & Additives', 'minor', PL,
     'manual_check', {'prompt': 'Ingredient list mentions additives: confirm each is declared with its functional class and specific name or INS number.'},
     [{'field': 'ingredients', 'op': 'contains_any', 'values': ['ins', 'colour', 'color', 'preservative', 'emulsifier', 'antioxidant',
                                                              'stabiliser', 'stabilizer', 'acidity regulator', 'flavour', 'flavor']}], RV, ''),
    ('R-020', 'Milk fat must not be replaced by other fat without declaration', 'Special Declarations', 'major', DAIRY,
     'manual_check', {'prompt': 'Check that the name and ingredient list agree: a product with vegetable fat or other non-milk fat must not '
                                'be named or presented as butter, ghee, cream or similar milk-fat products.'}, [], RV, ''),
]

IMPORT_RULES = [
    ('R-021', 'Importer name and address must be declared', 'Mandatory Declarations', 'critical', PL,
     'required', {'fields': ['importer']}, [], V, 'Name and address of the importer in India is missing.'),
    ('R-023', 'Country of origin must be declared', 'Special Declarations', 'critical', PL,
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['country of origin', 'origin', 'made in', 'product of'],
                      'fail_detail': 'No country of origin found in the declarations.'}, [], RV, ''),
    ('R-024', 'Month and year of import must be declared', 'Date Marking', 'major', LM,
     'contains_any', {'fields': ['other_declarations'], 'keywords': ['month and year of import', 'date of import', 'import date', 'imported on', 'imported in'],
                      'fail_detail': 'No month / year of import found in the declarations.'}, [], RV, ''),
]

RULES = BASIC_RULES + DAIRY_RULES + IMPORT_RULES

PACKS = [
    dict(name='FSSAI Basic Label Pack', version='v2.1', applies_to='All packaged food', status='active',
         effective_from='2011-08-05', regulation_ref=f'{PL}; {LM}', product_categories=[], extends=None,
         description='Core label checks for every pre-packaged food, from the Packaging and Labelling Regulations 2011 '
                     'and the Legal Metrology rules 2011.',
         rules=[r[0] for r in BASIC_RULES]),
    dict(name='Dairy Specific Pack', version='v1.3', applies_to='Dairy products', status='active',
         effective_from='2011-08-05', regulation_ref=DAIRY, product_categories=['Dairy'], extends='FSSAI Basic Label Pack',
         description='Extra checks for milk and milk products. Also applies every rule of the FSSAI Basic Label Pack.',
         rules=[r[0] for r in DAIRY_RULES]),
    dict(name='Import Goods Pack', version='v1.0', applies_to='Imported products', status='draft',
         effective_from=None, regulation_ref=f'{PL}; {LM}', product_categories=[], extends='FSSAI Basic Label Pack',
         description='Extra checks for imported food. Draft: not used for evaluation until an Admin activates it.',
         rules=[r[0] for r in IMPORT_RULES]),
]