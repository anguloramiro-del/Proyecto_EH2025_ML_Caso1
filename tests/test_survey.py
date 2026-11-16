"""Casos analíticos pequeños, independientes de los microdatos privados."""
import unittest

import pandas as pd

from src.survey import SurveyDesign


class SurveyDomainTests(unittest.TestCase):
    def test_outside_domain_psus_remain_in_variance(self):
        # Scores por UPM: +1/4, 0, -1/4, 0. Varianza = 1/8.
        data = pd.DataFrame({
            'factor': [1., 1., 1., 1.], 'estrato': ['a', 'a', 'b', 'b'],
            'upm': ['p1', 'p2', 'p3', 'p4'],
            's01a_03': [12, 30, 12, 30], 'cmasi': [1, 1, 2, 2],
        })
        result = SurveyDesign(data, min_n=1).estimate()
        self.assertAlmostEqual(result['tasa_pct'], 50.)
        self.assertAlmostEqual(result['se_pp'] ** 2 / 10000, 1/8)
        self.assertEqual(result['n_muestra'], 2)

    def test_lonely_adjust_is_explicit_and_preserves_undefined_strict_variance(self):
        # Estrato a: varianza 1/16; b y c: aportan 1/64 cada uno con adjust.
        data = pd.DataFrame({
            'factor': [1., 1., 1., 1.], 'estrato': ['a', 'a', 'b', 'c'],
            'upm': ['p1', 'p2', 'p3', 'p4'],
            's01a_03': [12, 12, 12, 12], 'cmasi': [1, 2, 1, 2],
        })
        result = SurveyDesign(data, min_n=1).estimate()
        self.assertIsNone(result['se_pp'])
        self.assertIsNone(result['ic95_inf_pct'])
        self.assertAlmostEqual(result['variance_nonlonely_component'], 1/16)
        self.assertAlmostEqual(result['variance_lonely_adjustment_component'], 1/32)
        self.assertAlmostEqual(result['se_adjusted_pp'] ** 2 / 10000, 3/32)
        self.assertAlmostEqual(result['variance_lonely_adjustment_share_pct'], 100/3)

    def test_small_domain_rate_is_suppressed(self):
        data = pd.DataFrame({
            'factor': [1., 1., 1., 1.], 'estrato': ['a', 'a', 'b', 'b'],
            'upm': ['p1', 'p2', 'p3', 'p4'],
            's01a_03': [12, 30, 12, 30], 'cmasi': [1, 1, 2, 2],
        })
        result = SurveyDesign(data, min_n=30).estimate()
        self.assertTrue(result['suprimida'])
        self.assertIsNone(result['tasa_pct'])
        self.assertIsNone(result['se_adjusted_pp'])
        self.assertEqual(result['n_muestra'], 2)


if __name__ == '__main__':
    unittest.main()
