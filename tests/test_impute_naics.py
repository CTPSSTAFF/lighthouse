import importlib.util
import unittest
from pathlib import Path

import pandas as pd

spec = importlib.util.spec_from_file_location(
    "imputation", Path(__file__).resolve().parents[1] / "scripts" / "impute-naics.py"
)
imputation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imputation)


class ImputationTests(unittest.TestCase):
    def test_notebook_conversion(self):
        for source, expected in [
            (None, None),
            (pd.NA, None),
            ("-1", None),
            ("3MS", "33"),
            ("4MS", "45"),
            ("722Z", "722"),
            ("7211", "721"),
            ("5415", "54"),
            ("928110P3", "92"),
            ("", None),
        ]:
            self.assertEqual(imputation.naicsp_to_naics(source), expected)

    def test_stratification_repeatability_and_row_order(self):
        counts = pd.Series(
            [3, 1, 1, 3],
            index=pd.MultiIndex.from_tuples(
                [(30, 1, "54"), (30, 1, "62"), (30, 3, "54"), (30, 3, "missing")],
                names=["age", "pemploy", "naics_code"],
            ),
        )
        target = pd.DataFrame(
            {"person_id": range(8), "age": [30] * 8, "pemploy": [1] * 4 + [3] * 4}
        )
        result, audit = imputation.impute(target, counts, 42)
        self.assertEqual(result.iloc[:4].value_counts().to_dict(), {54: 3, 62: 1})
        self.assertEqual(int(result.iloc[4:].isna().sum()), 3)
        reordered, _ = imputation.impute(target.iloc[::-1], counts, 42)
        pd.testing.assert_series_equal(result, reordered.reindex(target.index))
        again, _ = imputation.impute(target, counts, 42)
        pd.testing.assert_series_equal(result, again)
        self.assertTrue(all(s["age"] == s["donor_age"] for s in audit))

    def test_fallback_keeps_employment_type_and_reports_age(self):
        counts = pd.Series(
            [10, 10],
            index=pd.MultiIndex.from_tuples(
                [(30, 1, "54"), (40, 3, "62")],
                names=["age", "pemploy", "naics_code"],
            ),
        )
        target = pd.DataFrame({"person_id": [7], "age": [40], "pemploy": [1]})
        result, audit = imputation.impute(target, counts, 1)
        self.assertEqual(result.iloc[0], 54)
        self.assertEqual(audit[0]["donor_age"], 30)
        target["pemploy"] = 2
        with self.assertRaises(ValueError):
            imputation.impute(target, counts, 1)


if __name__ == "__main__":
    unittest.main()
