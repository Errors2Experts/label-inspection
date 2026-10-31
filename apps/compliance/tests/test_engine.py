"""Pure-Python tests for the rules engine and date parser (no database)."""

from datetime import date
from unittest import TestCase

from apps.compliance.engine import evaluator as ev
from apps.compliance.engine.dates import parse_label_date


def spec(rule_type, parameters=None, applies_when=None, on_fail=ev.NON_COMPLIANT):
    return ev.RuleSpec('R-T', 'Test', rule_type, parameters or {}, applies_when or [], on_fail)


def run(s, data, today=date(2026, 10, 29)):
    return ev.evaluate_rule(s, data, {'reference_date': today}).outcome


class DateParserTests(TestCase):
    def test_m4_tc_001_common_label_formats(self):
        """Date parsing | DD/MM/YY, DD/MM/YYYY, DD-MON-YY, MON YYYY, MM/YYYY | parsed with right precision"""
        self.assertEqual(parse_label_date('05/03/2026').start, date(2026, 3, 5))
        self.assertEqual(parse_label_date('05-03-26').start, date(2026, 3, 5))
        self.assertEqual(parse_label_date('05 MAR 2026').start, date(2026, 3, 5))
        self.assertEqual(parse_label_date('12-Dec-26').start, date(2026, 12, 12))
        m = parse_label_date('MAR 2027')
        self.assertIsNone(m.day)
        self.assertEqual((m.start, m.end), (date(2027, 3, 1), date(2027, 3, 31)))
        self.assertEqual(parse_label_date('03/2027').end, date(2027, 3, 31))
        self.assertEqual(parse_label_date('February 2028').end, date(2028, 2, 29))

    def test_m4_tc_002_labels_and_junk(self):
        """Date parsing | 'EXP: 01/03/2027', 'Best before 03/2027', junk, impossible dates | prefix stripped; junk -> None"""
        self.assertEqual(parse_label_date('EXP: 01/03/2027').start, date(2027, 3, 1))
        self.assertEqual(parse_label_date('Best before 03/2027').end, date(2027, 3, 31))
        for bad in ('', None, 'soon', '31/02/2026', '13/13/2026', '2026', 'ABC 2026'):
            self.assertIsNone(parse_label_date(bad), bad)


class RuleTypeTests(TestCase):
    def test_m4_tc_003_required(self):
        """required | all / any mode | compliant when declared, non-compliant naming the gap"""
        s = spec('required', {'fields': ['product_name', 'brand']})
        self.assertEqual(run(s, {'product_name': 'X', 'brand': 'Y'}), ev.COMPLIANT)
        out = ev.evaluate_rule(s, {'product_name': 'X', 'brand': '  '})
        self.assertEqual(out.outcome, ev.NON_COMPLIANT)
        self.assertIn('Brand', out.detail)
        anyr = spec('required', {'fields': ['manufacturer', 'packer'], 'mode': 'any'})
        self.assertEqual(run(anyr, {'packer': 'P'}), ev.COMPLIANT)
        self.assertEqual(run(anyr, {}), ev.NON_COMPLIANT)

    def test_m4_tc_004_on_fail_override(self):
        """on_fail | heuristic rule set to requires_verification | failure becomes Requires Verification"""
        self.assertEqual(run(spec('required', {'fields': ['ingredients']}, on_fail=ev.REQUIRES_VERIFICATION), {}), ev.REQUIRES_VERIFICATION)

    def test_m4_tc_005_regex_and_missing_modes(self):
        """regex | licence 14 digits; empty field with each on_missing mode | match / fail / n.a. / verify"""
        s = spec('regex', {'fields': ['fssai_license'], 'pattern': r'(?<!\d)\d{14}(?!\d)'})
        self.assertEqual(run(s, {'fssai_license': 'Lic. No. 10012345678901'}), ev.COMPLIANT)
        self.assertEqual(run(s, {'fssai_license': '1001234567890'}), ev.NON_COMPLIANT)
        self.assertEqual(run(s, {'fssai_license': '100123456789012'}), ev.NON_COMPLIANT)
        self.assertEqual(run(s, {}), ev.NOT_APPLICABLE)
        for mode, expected in (('fail', ev.NON_COMPLIANT), ('requires_verification', ev.REQUIRES_VERIFICATION)):
            s2 = spec('regex', {'fields': ['fssai_license'], 'pattern': 'x', 'on_missing': mode})
            self.assertEqual(run(s2, {}), expected)

    def test_m4_tc_006_quantity_format(self):
        """quantity_format | '500 g', '1.5 L', '2 x 100 g' ok; 'big pack', '500' not | pass/fail"""
        s = spec('quantity_format', {'field': 'net_quantity'})
        for ok in ('500 g', '1.5 L', '2 x 100 g', '250ml', '1 kg', '6 Nos'):
            self.assertEqual(run(s, {'net_quantity': ok}), ev.COMPLIANT, ok)
        for bad in ('big pack', '500', 'g'):
            self.assertEqual(run(s, {'net_quantity': bad}), ev.NON_COMPLIANT, bad)

    def test_m4_tc_007_date_valid_and_order(self):
        """date_valid / date_order | bad format, expiry before mfg, unreadable | non-compliant / verify"""
        v = spec('date_valid', {'fields': ['manufacturing_date', 'expiry_date']})
        self.assertEqual(run(v, {'manufacturing_date': '01/01/2026', 'expiry_date': 'JAN 2027'}), ev.COMPLIANT)
        self.assertEqual(run(v, {'manufacturing_date': 'yesterday'}), ev.NON_COMPLIANT)
        self.assertEqual(run(v, {}), ev.NOT_APPLICABLE)
        o = spec('date_order', {'first_field': 'manufacturing_date', 'second_field': 'expiry_date'})
        self.assertEqual(run(o, {'manufacturing_date': '01/06/2026', 'expiry_date': '01/12/2026'}), ev.COMPLIANT)
        self.assertEqual(run(o, {'manufacturing_date': '01/06/2026', 'expiry_date': '01/05/2026'}), ev.NON_COMPLIANT)
        self.assertEqual(run(o, {'manufacturing_date': 'JUN 2026', 'expiry_date': 'JUN 2026'}), ev.COMPLIANT)  # same month
        self.assertEqual(run(o, {'manufacturing_date': 'junk', 'expiry_date': '01/05/2026'}), ev.REQUIRES_VERIFICATION)
        self.assertEqual(run(o, {'manufacturing_date': '01/06/2026'}), ev.NOT_APPLICABLE)

    def test_m4_tc_008_not_expired(self):
        """not_expired | past, today, month-precision end, future, unreadable | verdicts against reference date"""
        s = spec('not_expired', {'field': 'expiry_date'})
        self.assertEqual(run(s, {'expiry_date': '28/10/2026'}), ev.NON_COMPLIANT)
        self.assertEqual(run(s, {'expiry_date': '29/10/2026'}), ev.COMPLIANT)  # valid through the expiry day
        self.assertEqual(run(s, {'expiry_date': 'OCT 2026'}), ev.COMPLIANT)  # month precision: valid to month end
        self.assertEqual(run(s, {'expiry_date': 'SEP 2026'}), ev.NON_COMPLIANT)
        self.assertEqual(run(s, {'expiry_date': '01/01/2030'}), ev.COMPLIANT)
        self.assertEqual(run(s, {'expiry_date': '??'}), ev.REQUIRES_VERIFICATION)
        self.assertEqual(run(s, {}), ev.NOT_APPLICABLE)

    def test_m4_tc_009_contains_any_numeric_manual(self):
        """contains_any / numeric_min / manual_check | keyword hit & miss, MRP bounds, manual prompt | outcomes"""
        c = spec('contains_any', {'fields': ['other_declarations'], 'keywords': ['Batch', 'lot']}, on_fail=ev.REQUIRES_VERIFICATION)
        self.assertEqual(run(c, {'other_declarations': 'BATCH no 4'}), ev.COMPLIANT)
        self.assertEqual(run(c, {'other_declarations': 'nothing'}), ev.REQUIRES_VERIFICATION)
        self.assertEqual(run(c, {}), ev.REQUIRES_VERIFICATION)
        n = spec('numeric_min', {'field': 'mrp', 'min': 0})
        self.assertEqual(run(n, {'mrp': '12.50'}), ev.COMPLIANT)
        self.assertEqual(run(n, {'mrp': '0'}), ev.NON_COMPLIANT)
        self.assertEqual(run(n, {'mrp': '-1'}), ev.NON_COMPLIANT)
        self.assertEqual(run(n, {'mrp': '₹ 1,200.00'}), ev.COMPLIANT)
        self.assertEqual(run(n, {'mrp': 'abc'}), ev.REQUIRES_VERIFICATION)
        self.assertEqual(run(n, {}), ev.NOT_APPLICABLE)
        m = spec('manual_check', {'prompt': 'Look at the logo'})
        out = ev.evaluate_rule(m, {})
        self.assertEqual((out.outcome, out.detail), (ev.REQUIRES_VERIFICATION, 'Look at the logo'))

    def test_m4_tc_010_applies_when(self):
        """applies_when | present/absent/contains_any/not_contains_any | Not Applicable when conditions fail"""
        s = spec('required', {'fields': ['brand']}, [{'field': 'importer', 'op': 'present'}])
        self.assertEqual(run(s, {}), ev.NOT_APPLICABLE)
        self.assertEqual(run(s, {'importer': 'ACME'}), ev.NON_COMPLIANT)
        s2 = spec('required', {'fields': ['brand']}, [{'field': ['ingredients', 'product_name'], 'op': 'contains_any', 'values': ['aspartame']}])
        self.assertEqual(run(s2, {'product_name': 'Diet drink (Aspartame)'}), ev.NON_COMPLIANT)
        self.assertEqual(run(s2, {'ingredients': 'water'}), ev.NOT_APPLICABLE)
        s3 = spec('required', {'fields': ['brand']}, [{'field': 'product_name', 'op': 'not_contains_any', 'values': ['infant']}])
        self.assertEqual(run(s3, {'product_name': 'Infant formula'}), ev.NOT_APPLICABLE)

    def test_m4_tc_011_broken_rule_is_contained(self):
        """Robustness | unknown type, missing parameter | Requires Verification, no exception"""
        self.assertEqual(run(spec('nonsense'), {}), ev.REQUIRES_VERIFICATION)
        self.assertEqual(run(spec('regex', {'fields': ['brand']}), {'brand': 'x'}), ev.REQUIRES_VERIFICATION)  # no pattern


class AggregationTests(TestCase):
    def test_m4_tc_012_overall_status(self):
        """Aggregation | mixes of outcomes | non-compliant > requires verification > compliant > n.a."""
        f = ev.overall_status
        self.assertEqual(f([ev.COMPLIANT, ev.NON_COMPLIANT, ev.REQUIRES_VERIFICATION]), ev.NON_COMPLIANT)
        self.assertEqual(f([ev.COMPLIANT, ev.REQUIRES_VERIFICATION, ev.NOT_APPLICABLE]), ev.REQUIRES_VERIFICATION)
        self.assertEqual(f([ev.COMPLIANT, ev.NOT_APPLICABLE]), ev.COMPLIANT)
        self.assertEqual(f([ev.NOT_APPLICABLE]), ev.NOT_APPLICABLE)
        self.assertEqual(f([]), ev.NOT_APPLICABLE)


class ValidationTests(TestCase):
    def test_m4_tc_013_validate_rule_config(self):
        """Validation (FDS 12.7) | bad type/field/regex/op/on_fail | readable errors; valid config -> []"""
        ok = ev.validate_rule_config('required', {'fields': ['brand']}, [], ev.NON_COMPLIANT)
        self.assertEqual(ok, [])
        self.assertTrue(ev.validate_rule_config('magic', {}, [], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('required', {'fields': ['colour']}, [], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('required', {}, [], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('regex', {'fields': ['brand'], 'pattern': '('}, [], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('regex', {'fields': ['brand'], 'pattern': 'a' * 400}, [], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('contains_any', {'fields': ['brand'], 'keywords': []}, [], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('date_order', {'first_field': 'brand'}, [], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('required', {'fields': ['brand']}, [{'field': 'brand', 'op': 'weird'}], ev.NON_COMPLIANT))
        self.assertTrue(ev.validate_rule_config('required', {'fields': ['brand']}, [], 'compliant'))
        self.assertTrue(ev.validate_rule_config('required', {'fields': ['brand'], 'on_missing': 'x'}, [], ev.NON_COMPLIANT))
