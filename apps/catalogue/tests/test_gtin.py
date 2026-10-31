from django.test import SimpleTestCase

from apps.catalogue.gtin import check_digit, normalize_gtin, to_gtin14, validate_gtin

from .base import EAN8, EAN13, UPC_A, UPC_AS_EAN13


class GtinTests(SimpleTestCase):
    def test_m2_tc_001_valid_codes_accepted(self):
        """Valid barcode formats | EAN-13, UPC-A, EAN-8 and a GTIN-14 with correct check digits | All accepted"""
        body14 = '1' + EAN13[:-1]  # 13 digits
        gtin14 = body14 + str(check_digit(body14))
        for code in (EAN13, UPC_A, EAN8, gtin14):
            self.assertEqual(validate_gtin(code), code)
        self.assertEqual(len(gtin14), 14)

    def test_m2_tc_002_formatting_characters_stripped(self):
        """Formatting tolerated | '4006 381-333931' | Normalised to digits only"""
        self.assertEqual(validate_gtin(' 4006 381-333931 '), EAN13)

    def test_m2_tc_003_wrong_length_rejected(self):
        """Wrong length | 7, 10 and 15 digit values | ValueError with length message"""
        for bad in ('1234567', '1234567890', '123456789012345'):
            with self.assertRaisesMessage(ValueError, '8, 12, 13 or 14 digits'):
                validate_gtin(bad)

    def test_m2_tc_004_bad_check_digit_rejected(self):
        """Bad check digit | EAN-13 with last digit changed | ValueError mentioning check digit"""
        with self.assertRaisesMessage(ValueError, 'check digit'):
            validate_gtin('4006381333932')

    def test_m2_tc_005_empty_or_non_numeric_rejected(self):
        """Empty / letters only | '' and 'abc' | ValueError"""
        for bad in ('', 'abc', None):
            with self.assertRaises(ValueError):
                validate_gtin(bad)

    def test_m2_tc_006_upc_and_ean_collapse_to_one_gtin14(self):
        """Canonical form | UPC-A and the same code as EAN-13 | Identical 14-digit value"""
        self.assertEqual(to_gtin14(normalize_gtin(UPC_A)), to_gtin14(normalize_gtin(UPC_AS_EAN13)))
        self.assertEqual(len(to_gtin14(EAN8)), 14)
