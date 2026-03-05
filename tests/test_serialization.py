import pytest
from eudoxa import (
    Aspect, Consequence, VDiff, EudoxaManager,
    str_to_type
)

# -------------------------------------------------------------
# Helper: build a simple manager with data
# -------------------------------------------------------------
def build_demo_manager():
    mgr = EudoxaManager()

    # Add aspects
    a1 = mgr.add_aspect("Kvalitet", "int", "Hur bra något är")
    a2 = mgr.add_aspect("Pris", "float", "Kostnadsnivå")

    # Add levels
    mgr.add_aspect_level("Kvalitet", "1", "Låg kvalitet")
    mgr.add_aspect_level("Kvalitet", "2", "Medel kvalitet")
    mgr.add_aspect_level("Pris", "10", "Billigt")
    mgr.add_aspect_level("Pris", "100", "Dyrt")

    # Add consequences
    mgr.add_consequence("C1", {"Kvalitet": "1", "Pris": "10"})
    mgr.add_consequence("C2", {"Kvalitet": "2", "Pris": "100"})

    return mgr


# -------------------------------------------------------------
# TEST: Aspect serialization
# -------------------------------------------------------------
def test_aspect_serialization():
    asp = Aspect("Kvalitet", int, "Beskrivning här")
    asp.levels = {"1": "Låg", "2": "Hög"}
    asp.vdiffs = [
        VDiff("Kvalitet", None, None),
        VDiff("Kvalitet", "1", "2"),
        VDiff("Kvalitet", "2", "1")
    ]

    d = asp.to_dict()
    asp2 = Aspect.from_dict(d)

    assert asp2.name == "Kvalitet"
    assert asp2.data_type == int
    assert asp2.description == "Beskrivning här"
    assert asp2.levels == {"1": "Låg", "2": "Hög"}
    assert len(asp2.vdiffs) == 3
    assert asp2.vdiffs[1].from_level == "1"
    assert asp2.vdiffs[1].to_level == "2"


# -------------------------------------------------------------
# TEST: Consequence serialization
# -------------------------------------------------------------
def test_consequence_serialization():
    c = Consequence({"A": "1", "B": "x"})
    d = c.to_dict()
    c2 = Consequence.from_dict(d)

    assert c2.aspect_levels == {"A": "1", "B": "x"}


# -------------------------------------------------------------
# TEST: VDiff Comparison Matrix serialization
# -------------------------------------------------------------
def test_vdiff_cm_serialization_in_manager():
    mgr = build_demo_manager()

    d = mgr.to_dict()
    mgr2 = EudoxaManager.from_dict(d)

    # keys should match
    assert set(mgr.vdiff_comparison_matrix.keys()) == set(mgr2.vdiff_comparison_matrix.keys())

    # spot-check a pair
    for key in mgr.vdiff_comparison_matrix.keys():
        assert key in mgr2.vdiff_comparison_matrix
        # Compare keys of the inner relation dict
        inner1 = mgr.vdiff_comparison_matrix[key]
        inner2 = mgr2.vdiff_comparison_matrix[key]

        assert set(inner1.keys()) == set(inner2.keys())
        break


# -------------------------------------------------------------
# TEST: Consequence Space serialization
# -------------------------------------------------------------
def test_consequence_space_serialization():
    mgr = build_demo_manager()
    d = mgr.to_dict()
    mgr2 = EudoxaManager.from_dict(d)

    assert len(mgr.consequence_space) == len(mgr2.consequence_space)
    for c1, c2 in zip(mgr.consequence_space, mgr2.consequence_space):
        assert c1.aspect_levels == c2.aspect_levels


# -------------------------------------------------------------
# TEST: Full roundtrip
# -------------------------------------------------------------
def test_manager_full_roundtrip():
    mgr = build_demo_manager()
    d = mgr.to_dict()
    mgr2 = EudoxaManager.from_dict(d)

    # Aspects
    assert mgr.aspects.keys() == mgr2.aspects.keys()

    for name in mgr.aspects:
        a1 = mgr.aspects[name]
        a2 = mgr2.aspects[name]
        assert a1.levels == a2.levels
        assert len(a1.vdiffs) == len(a2.vdiffs)

    # Consequences
    assert mgr.consequences.keys() == mgr2.consequences.keys()

    # Consequence space
    assert len(mgr.consequence_space) == len(mgr2.consequence_space)

    # VDiff comparison matrix
    assert set(mgr.vdiff_comparison_matrix.keys()) == set(mgr2.vdiff_comparison_matrix.keys())