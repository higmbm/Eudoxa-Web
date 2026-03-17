import unittest
from eudoxa import (
    Aspect, Consequence, VDiff, EudoxaManager,
    str_to_type
)

import logging
logging.getLogger("eudoxa").setLevel(logging.WARNING)

# -------------------------------------------------------------
# Helpers: build managers used across multiple tests
# -------------------------------------------------------------

def build_konsert_manager():
    """Build the 'konsert' manager (mirrors konsert.xlsx)."""
    mgr = EudoxaManager()
    mgr.add_aspect("Taxikostnad", "int", "Extrakostnad för taxi")
    mgr.add_aspect("Betyg", "str", "Betyg på tentamen")
    mgr.add_aspect("Konsert", "str", "Konsertupplevelse")

    mgr.add_aspect_level("Taxikostnad", "0",   "0 kr")
    mgr.add_aspect_level("Taxikostnad", "600", "600 kr")
    mgr.add_aspect_level("Betyg", "VG", None)
    mgr.add_aspect_level("Betyg", "G",  None)
    mgr.add_aspect_level("Betyg", "IG", None)
    mgr.add_aspect_level("Konsert", "K-", "Ingen konsert")
    mgr.add_aspect_level("Konsert", "K+", "Konsert")

    return mgr


def build_demo_manager():
    """Build a simple manager with two aspects and two consequences."""
    mgr = EudoxaManager()
    mgr.add_aspect("Kvalitet", "int", "Hur bra något är")
    mgr.add_aspect("Pris", "float", "Kostnadsnivå")

    mgr.add_aspect_level("Kvalitet", "1", "Låg kvalitet")
    mgr.add_aspect_level("Kvalitet", "2", "Medel kvalitet")
    mgr.add_aspect_level("Pris", "10",  "Billigt")
    mgr.add_aspect_level("Pris", "100", "Dyrt")

    mgr.add_consequence("C1", {"Kvalitet": "1", "Pris": "10"})
    mgr.add_consequence("C2", {"Kvalitet": "2", "Pris": "100"})

    return mgr


# -------------------------------------------------------------
# TEST: Serialization
# -------------------------------------------------------------

class TestSerialization(unittest.TestCase):

    def test_aspect_serialization(self):
        asp = Aspect("Kvalitet", int, "Beskrivning här")
        asp.levels = {"1": "Låg", "2": "Hög"}
        asp.vdiffs = [
            VDiff("Kvalitet", None, None),
            VDiff("Kvalitet", "1", "2"),
            VDiff("Kvalitet", "2", "1")
        ]

        d = asp.to_dict()
        asp2 = Aspect.from_dict(d)

        self.assertEqual(asp2.name, "Kvalitet")
        self.assertEqual(asp2.data_type, int)
        self.assertEqual(asp2.description, "Beskrivning här")
        self.assertEqual(asp2.levels, {"1": "Låg", "2": "Hög"})
        self.assertEqual(len(asp2.vdiffs), 3)
        self.assertEqual(asp2.vdiffs[1].from_level, "1")
        self.assertEqual(asp2.vdiffs[1].to_level, "2")

    def test_consequence_serialization(self):
        c = Consequence({"A": "1", "B": "x"})
        d = c.to_dict()
        c2 = Consequence.from_dict(d)

        self.assertEqual(c2.aspect_levels, {"A": "1", "B": "x"})

    def test_vdiff_cm_serialization_in_manager(self):
        mgr = build_demo_manager()
        d = mgr.to_dict()
        mgr2 = EudoxaManager.from_dict(d)

        self.assertEqual(
            set(mgr.vdiff_comparison_matrix.keys()),
            set(mgr2.vdiff_comparison_matrix.keys())
        )
        # Spot-check the first key
        for key in mgr.vdiff_comparison_matrix.keys():
            self.assertIn(key, mgr2.vdiff_comparison_matrix)
            self.assertEqual(
                set(mgr.vdiff_comparison_matrix[key].keys()),
                set(mgr2.vdiff_comparison_matrix[key].keys())
            )
            break

    def test_consequence_space_serialization(self):
        mgr = build_demo_manager()
        d = mgr.to_dict()
        mgr2 = EudoxaManager.from_dict(d)

        self.assertEqual(len(mgr.consequence_space), len(mgr2.consequence_space))
        for c1, c2 in zip(mgr.consequence_space, mgr2.consequence_space):
            self.assertEqual(c1.aspect_levels, c2.aspect_levels)

    def test_manager_full_roundtrip(self):
        mgr = build_demo_manager()
        d = mgr.to_dict()
        mgr2 = EudoxaManager.from_dict(d)

        self.assertEqual(mgr.aspects.keys(), mgr2.aspects.keys())
        for name in mgr.aspects:
            self.assertEqual(mgr.aspects[name].levels, mgr2.aspects[name].levels)
            self.assertEqual(len(mgr.aspects[name].vdiffs), len(mgr2.aspects[name].vdiffs))

        self.assertEqual(mgr.consequences.keys(), mgr2.consequences.keys())
        self.assertEqual(len(mgr.consequence_space), len(mgr2.consequence_space))
        self.assertEqual(
            set(mgr.vdiff_comparison_matrix.keys()),
            set(mgr2.vdiff_comparison_matrix.keys())
        )


# -------------------------------------------------------------
# TEST: Type validation in Aspect.add_level  (Step 1)
# -------------------------------------------------------------

class TestTypeValidation(unittest.TestCase):

    # --- int aspect ---

    def test_int_level_valid(self):
        """Integer strings are accepted on an int aspect."""
        mgr = EudoxaManager()
        mgr.add_aspect("Cost", "int")
        mgr.add_aspect_level("Cost", "0",   "Zero")
        mgr.add_aspect_level("Cost", "600", "Six hundred")
        self.assertEqual(list(mgr.aspects["Cost"].levels.keys()), ["0", "600"])

    def test_int_level_rejects_non_integer(self):
        """A non-integer string must raise ValueError on an int aspect."""
        mgr = EudoxaManager()
        mgr.add_aspect("Cost", "int")
        with self.assertRaises(ValueError):
            mgr.add_aspect_level("Cost", "abc", None)

    def test_int_level_rejects_float_string(self):
        """A float string (e.g. '1.5') must raise ValueError on an int aspect."""
        mgr = EudoxaManager()
        mgr.add_aspect("Cost", "int")
        with self.assertRaises(ValueError):
            mgr.add_aspect_level("Cost", "1.5", None)

    # --- float aspect ---

    def test_float_level_valid(self):
        """Integer and float strings are both accepted on a float aspect."""
        mgr = EudoxaManager()
        mgr.add_aspect("Price", "float")
        mgr.add_aspect_level("Price", "10",  "Ten")
        mgr.add_aspect_level("Price", "1.5", "One point five")
        self.assertEqual(list(mgr.aspects["Price"].levels.keys()), ["10", "1.5"])

    def test_float_level_rejects_non_numeric(self):
        """A non-numeric string must raise ValueError on a float aspect."""
        mgr = EudoxaManager()
        mgr.add_aspect("Price", "float")
        with self.assertRaises(ValueError):
            mgr.add_aspect_level("Price", "expensive", None)

    # --- str aspect ---

    def test_str_level_accepts_anything(self):
        """Any string is valid on a str aspect."""
        mgr = EudoxaManager()
        mgr.add_aspect("Grade", "str")
        mgr.add_aspect_level("Grade", "VG", None)
        mgr.add_aspect_level("Grade", "G",  None)
        mgr.add_aspect_level("Grade", "IG", None)
        self.assertEqual(list(mgr.aspects["Grade"].levels.keys()), ["VG", "G", "IG"])

    def test_str_level_accepts_numeric_string(self):
        """Numeric strings are also valid on a str aspect."""
        mgr = EudoxaManager()
        mgr.add_aspect("Code", "str")
        mgr.add_aspect_level("Code", "42", None)
        self.assertIn("42", mgr.aspects["Code"].levels)

    # --- konsert fixture ---

    def test_konsert_manager_builds_without_error(self):
        """The full konsert example must build without any type errors."""
        mgr = build_konsert_manager()
        self.assertEqual(set(mgr.aspects.keys()), {"Taxikostnad", "Betyg", "Konsert"})
        self.assertEqual(list(mgr.aspects["Taxikostnad"].levels.keys()), ["0", "600"])
        self.assertEqual(list(mgr.aspects["Betyg"].levels.keys()),       ["VG", "G", "IG"])
        self.assertEqual(list(mgr.aspects["Konsert"].levels.keys()),     ["K-", "K+"])

    def test_konsert_int_aspect_rejects_bad_level(self):
        """Adding a non-integer level to Taxikostnad (int) must raise ValueError."""
        mgr = build_konsert_manager()
        with self.assertRaises(ValueError):
            mgr.add_aspect_level("Taxikostnad", "gratis", None)


if __name__ == "__main__":
    unittest.main()