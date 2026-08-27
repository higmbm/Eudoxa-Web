import logging
import unittest
from eudoxa import (
    VDiff, EudoxaManager,
    get_vdiff_relation, set_vdiff_relation,
    TRUE, FALSE, UNDEFINED,
    GT, GTE, DEQ, LTE, LT,
    BT, BTE, EQ, WTE, WT,
)

logging.getLogger("eudoxa").setLevel(logging.WARNING)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mgr(aspects):
    """
    Build a manager from a dict {aspect_name: [level, ...]}.
    Aspects and levels are added in dict-insertion order.
    """
    mgr = EudoxaManager()
    for name, levels in aspects.items():
        mgr.add_aspect(name, "str")
        for level in levels:
            mgr.add_aspect_level(name, level, None)
    return mgr


def rel(closure, a1, l1a, l1b, a2, l2a, l2b):
    """Return the relation at (Δ(a1,l1a,l1b), Δ(a2,l2a,l2b)) in closure."""
    return get_vdiff_relation(closure, VDiff(a1, l1a, l1b), VDiff(a2, l2a, l2b))


# ── Basic / sanity ────────────────────────────────────────────────────────────

class TestClosureBasic(unittest.TestCase):
    """Sanity checks: empty/minimal setups and reflexivity of zero-diffs."""

    def test_empty_manager_no_collision(self):
        mgr = EudoxaManager()
        _, _, colls = mgr.closure()
        self.assertEqual(colls, [])

    def test_single_aspect_no_relations_no_collision(self):
        mgr = make_mgr({"A": ["1", "2", "3"]})
        _, _, colls = mgr.closure()
        self.assertEqual(colls, [])

    def test_zero_diff_reflexive_intra_aspect(self):
        """◬_A ⊒ ◬_A is pre-established and survives closure."""
        mgr = make_mgr({"A": ["1", "2"]})
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "1", "A", "1", "1"), TRUE)

    def test_zero_diffs_equal_cross_aspect(self):
        """◬_A ⊒ ◬_B and ◬_B ⊒ ◬_A are pre-established."""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "1", "B", "1", "1"), TRUE)
        self.assertEqual(rel(closure, "B", "1", "1", "A", "1", "1"), TRUE)

    def test_single_relation_no_collision(self):
        """Setting one GTE relation produces no collision."""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        _, _, colls = mgr.closure()
        self.assertEqual(colls, [])

    def test_unrelated_vdiffs_remain_undefined(self):
        """Setting Δ(A,1,2) ⊒ Δ(B,1,2) should not affect Δ(A,1,2) vs Δ(C,1,2)."""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"], "C": ["1", "2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "C", "1", "2"), UNDEFINED)
        self.assertEqual(rel(closure, "C", "1", "2", "A", "1", "2"), UNDEFINED)


# ── TransP ────────────────────────────────────────────────────────────────────

class TestClosureTransP(unittest.TestCase):
    """TransP: ab⊒cd & cd⊒ef ==> ab⊒ef"""

    def test_transp_intra_aspect(self):
        """Δ(A,1,2)⊒Δ(A,2,3) & Δ(A,2,3)⊒Δ(A,3,4) ==> Δ(A,1,2)⊒Δ(A,3,4)"""
        mgr = make_mgr({"A": ["1", "2", "3", "4"]})
        mgr.set_rel("A", "1", "2", "A", "2", "3", GTE)
        mgr.set_rel("A", "2", "3", "A", "3", "4", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "A", "3", "4"), TRUE)

    def test_transp_cross_aspect(self):
        """Δ(A,1,2)⊒Δ(B,1,2) & Δ(B,1,2)⊒Δ(C,1,2) ==> Δ(A,1,2)⊒Δ(C,1,2)"""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"], "C": ["1", "2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        mgr.set_rel("B", "1", "2", "C", "1", "2", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "C", "1", "2"), TRUE)

    def test_transp_chain_length_4(self):
        """Four-link chain across five aspects derives the end-to-end relation."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"],
                        "D": ["1","2"], "E": ["1","2"]})
        for a1, a2 in [("A","B"), ("B","C"), ("C","D"), ("D","E")]:
            mgr.set_rel(a1, "1", "2", a2, "1", "2", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "E", "1", "2"), TRUE)

    def test_transp_no_spurious_reverse(self):
        """Δ(A,1,2)⊒Δ(B,1,2) alone must not derive Δ(B,1,2)⊒Δ(A,1,2)."""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "B", "1", "2", "A", "1", "2"), UNDEFINED)


# ── NegTransP ─────────────────────────────────────────────────────────────────

class TestClosureNegTransP(unittest.TestCase):
    """NegTransP: ab⋣cd & cd⋣ef ==> ab⋣ef"""

    def test_negtransp_cross_aspect(self):
        """Δ(A,1,2)⋣Δ(B,1,2) & Δ(B,1,2)⋣Δ(C,1,2) ==> Δ(A,1,2)⋣Δ(C,1,2)"""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", LT)
        mgr.set_rel("B", "1", "2", "C", "1", "2", LT)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "C", "1", "2"), FALSE)

    def test_negtransp_chain_length_4(self):
        """Four-link negative chain derives the end-to-end relation."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"],
                        "D": ["1","2"], "E": ["1","2"]})
        for a1, a2 in [("A","B"), ("B","C"), ("C","D"), ("D","E")]:
            mgr.set_rel(a1, "1", "2", a2, "1", "2", LT)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "E", "1", "2"), FALSE)

    def test_negtransp_no_spurious_positive(self):
        """A single ⋣ assertion must not cause NegTransP to produce FALSE for
        the reverse pair.  set_vdiff_relation is used directly so that the
        complementary ⊒ half is NOT written; the reverse cell must then stay
        UNDEFINED after closure (NegTransP needs two FALSE premises)."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"]})
        mgr.set_vdiff_relation(VDiff("A","1","2"), VDiff("B","1","2"), FALSE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        # No rule can derive Δ(B,1,2)⋣Δ(A,1,2) from a single premise
        self.assertEqual(rel(closure, "B", "1", "2", "A", "1", "2"), UNDEFINED)


# ── DiffP / NegDiffP ──────────────────────────────────────────────────────────

class TestClosureDiffP(unittest.TestCase):
    """DiffP:    cd⊒ef (same aspect) ==> ce⊒df
       NegDiffP: cd⋣ef (same aspect) ==> fd⋣ec"""

    def test_diffp(self):
        """Δ(A,1,3)⊒Δ(A,2,4) ==> Δ(A,1,2)⊒Δ(A,3,4)
           (c=1,d=3,e=2,f=4 → ce=Δ(1,2), df=Δ(3,4))"""
        mgr = make_mgr({"A": ["1", "2", "3", "4"]})
        mgr.set_rel("A", "1", "3", "A", "2", "4", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "A", "3", "4"), TRUE)

    def test_negdiffp(self):
        """Δ(A,1,3)⋣Δ(A,2,4) ==> Δ(A,4,3)⋣Δ(A,2,1)
           (c=1,d=3,e=2,f=4 → fd=Δ(4,3), ec=Δ(2,1))"""
        mgr = make_mgr({"A": ["1", "2", "3", "4"]})
        mgr.set_rel("A", "1", "3", "A", "2", "4", LT)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "4", "3", "A", "2", "1"), FALSE)

    def test_diffp_does_not_apply_cross_aspect(self):
        """DiffP is only for same-aspect pairs; cross-aspect GTE should not trigger it."""
        mgr = make_mgr({"A": ["1", "2", "3", "4"], "B": ["1", "2", "3", "4"]})
        mgr.set_rel("A", "1", "3", "B", "2", "4", GTE)  # cross-aspect: no DiffP
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        # Δ(A,1,2)⊒Δ(B,3,4) must NOT be derived (DiffP only applies within one aspect)
        self.assertEqual(rel(closure, "A", "1", "2", "B", "3", "4"), UNDEFINED)

    def test_diffp_then_transp(self):
        """DiffP creates a new intermediate; TransP then chains through it.
           Δ(A,1,3)⊒Δ(A,2,4) → DiffP → Δ(A,1,2)⊒Δ(A,3,4)
           Δ(A,3,4)⊒Δ(B,1,2)  → TransP → Δ(A,1,2)⊒Δ(B,1,2)
           This may require the outer fixed-point pass to complete."""
        mgr = make_mgr({"A": ["1", "2", "3", "4"], "B": ["1", "2"]})
        mgr.set_rel("A", "1", "3", "A", "2", "4", GTE)
        mgr.set_rel("A", "3", "4", "B", "1", "2", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "B", "1", "2"), TRUE)


# ── InvP_R / InvP_L ───────────────────────────────────────────────────────────

class TestClosureInvP(unittest.TestCase):
    """InvP_R: ab⊒cd & cd⊒xx ==> dc⊒ba
       InvP_L: xx⊒cd & cd⊒ef ==> fe⊒dc"""

    def test_invp_r(self):
        """Δ(A,1,2)⊒Δ(B,1,2) & Δ(B,1,2)⊒◬_B ==> Δ(B,2,1)⊒Δ(A,2,1)"""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        # Δ(B,1,2) ⊒ ◬_B  (use same-level for zero-diff)
        mgr.set_rel("B", "1", "2", "B", "1", "1", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        # dc=Δ(B,2,1), ba=Δ(A,2,1)
        self.assertEqual(rel(closure, "B", "2", "1", "A", "2", "1"), TRUE)

    def test_invp_l(self):
        """◬_A⊒Δ(A,2,1) & Δ(A,2,1)⊒Δ(B,2,1) ==> Δ(B,1,2)⊒Δ(A,1,2)"""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        # ◬_A ⊒ Δ(A,2,1): zero-diff ≥ Δ(A,2,1), i.e. Δ(A,2,1) is non-positive
        mgr.set_rel("A", "1", "1", "A", "2", "1", GTE)
        mgr.set_rel("A", "2", "1", "B", "2", "1", GTE)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        # fe=Δ(B,1,2), dc=Δ(A,1,2)
        self.assertEqual(rel(closure, "B", "1", "2", "A", "1", "2"), TRUE)


# ── NegInvP_L / NegInvP_R ────────────────────────────────────────────────────

class TestClosureNegInvP(unittest.TestCase):
    """NegInvP_L: xx⋣cd & cd⋣ef ==> fe⋣dc
       NegInvP_R: ab⋣cd & cd⋣xx ==> dc⋣ba"""

    def test_neginvp_l(self):
        """◬_A⋣Δ(A,1,2) & Δ(A,1,2)⋣Δ(B,1,2) ==> Δ(B,2,1)⋣Δ(A,2,1)"""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        # ◬_A ⋣ Δ(A,1,2): GT sets Δ(A,1,2)⊒◬_A and ◬_A⋣Δ(A,1,2)
        mgr.set_rel("A", "1", "2", "A", "1", "1", GT)
        # Δ(A,1,2) ⋣ Δ(B,1,2): LT sets Δ(B,1,2)⊒Δ(A,1,2) and Δ(A,1,2)⋣Δ(B,1,2)
        mgr.set_rel("A", "1", "2", "B", "1", "2", LT)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        # fe=Δ(B,2,1), dc=Δ(A,2,1)
        self.assertEqual(rel(closure, "B", "2", "1", "A", "2", "1"), FALSE)

    def test_neginvp_r(self):
        """Δ(A,2,1)⋣Δ(B,2,1) & Δ(B,2,1)⋣◬_B ==> Δ(B,1,2)⋣Δ(A,1,2)"""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        mgr.set_rel("A", "2", "1", "B", "2", "1", LT)
        # Δ(B,2,1) ⋣ ◬_B: LT sets ◬_B⊒Δ(B,2,1) and Δ(B,2,1)⋣◬_B
        mgr.set_rel("B", "2", "1", "B", "1", "1", LT)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        # dc=Δ(B,1,2), ba=Δ(A,1,2)
        self.assertEqual(rel(closure, "B", "1", "2", "A", "1", "2"), FALSE)


# ── NegTransP_DEQ_L / NegTransP_DEQ_R ────────────────────────────────────────

class TestClosureNegTransPDEQ(unittest.TestCase):
    """NegTransP_DEQ_L: ab≜cd & cd⋣ef ==> ab⋣ef
       NegTransP_DEQ_R: ab⋣cd & cd≜ef ==> ab⋣ef"""

    def test_negtransp_deq_l(self):
        """Δ(A,1,2)≜Δ(B,1,2) & Δ(B,1,2)⋣Δ(C,1,2) ==> Δ(A,1,2)⋣Δ(C,1,2)"""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", DEQ)
        mgr.set_rel("B", "1", "2", "C", "1", "2", LT)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "C", "1", "2"), FALSE)

    def test_negtransp_deq_r(self):
        """Δ(A,1,2)⋣Δ(B,1,2) & Δ(B,1,2)≜Δ(C,1,2) ==> Δ(A,1,2)⋣Δ(C,1,2)"""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", LT)
        mgr.set_rel("B", "1", "2", "C", "1", "2", DEQ)
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "C", "1", "2"), FALSE)

    def test_negtransp_deq_l_not_spurious(self):
        """DEQ alone (without a ⋣ premise) must not produce a ⋣ conclusion."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", DEQ)
        mgr.set_rel("B", "1", "2", "C", "1", "2", GTE)   # ⊒, not ⋣
        closure, _, colls = mgr.closure()
        self.assertEqual(colls, [])
        # Only TransP should fire: Δ(A,1,2)⊒Δ(C,1,2)
        self.assertEqual(rel(closure, "A", "1", "2", "C", "1", "2"), TRUE)
        # No ⋣ in this direction
        self.assertNotEqual(rel(closure, "A", "1", "2", "C", "1", "2"), FALSE)


# ── Collision detection ───────────────────────────────────────────────────────

class TestClosureCollisions(unittest.TestCase):

    def test_set_vdiff_relation_detects_direct_collision(self):
        """set_vdiff_relation itself detects TRUE/FALSE clashes immediately.
        GT sets (A12,B12)=TRUE and (B12,A12)=FALSE; trying to then set
        (B12,A12)=TRUE must return a non-None collision tuple."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GT)
        _, coll = mgr.set_vdiff_relation(VDiff("B","1","2"), VDiff("A","1","2"), TRUE)
        self.assertIsNotNone(coll)

    def test_collision_via_transp(self):
        """TransP derives Δ(A,1,2)⊒Δ(C,1,2); asserting ⋣ at that cell collides."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        mgr.set_rel("B", "1", "2", "C", "1", "2", GTE)
        mgr.set_vdiff_relation(VDiff("A","1","2"), VDiff("C","1","2"), FALSE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_collision_via_negtransp(self):
        """NegTransP derives Δ(A,1,2)⋣Δ(C,1,2); asserting ⊒ at that cell collides."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"], "C": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", LT)
        mgr.set_rel("B", "1", "2", "C", "1", "2", LT)
        mgr.set_vdiff_relation(VDiff("A","1","2"), VDiff("C","1","2"), TRUE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_collision_via_diffp(self):
        """DiffP derives Δ(A,1,2)⊒Δ(A,3,4); asserting ⋣ at that cell collides."""
        mgr = make_mgr({"A": ["1","2","3","4"]})
        mgr.set_rel("A", "1", "3", "A", "2", "4", GTE)
        mgr.set_vdiff_relation(VDiff("A","1","2"), VDiff("A","3","4"), FALSE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_collision_via_negdiffp(self):
        """NegDiffP derives Δ(A,4,3)⋣Δ(A,2,1); asserting ⊒ at that cell collides."""
        mgr = make_mgr({"A": ["1","2","3","4"]})
        mgr.set_rel("A", "1", "3", "A", "2", "4", LT)
        mgr.set_vdiff_relation(VDiff("A","4","3"), VDiff("A","2","1"), TRUE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_collision_via_invp_r(self):
        """InvP_R derives Δ(B,2,1)⊒Δ(A,2,1); asserting ⋣ at that cell collides."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        mgr.set_rel("B", "1", "2", "B", "1", "1", GTE)  # Δ(B,1,2) ⊒ ◬_B
        mgr.set_vdiff_relation(VDiff("B","2","1"), VDiff("A","2","1"), FALSE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_collision_via_invp_l(self):
        """InvP_L derives Δ(B,1,2)⊒Δ(A,1,2); asserting ⋣ at that cell collides."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"]})
        mgr.set_rel("A", "1", "1", "A", "2", "1", GTE)  # ◬_A ⊒ Δ(A,2,1)
        mgr.set_rel("A", "2", "1", "B", "2", "1", GTE)
        mgr.set_vdiff_relation(VDiff("B","1","2"), VDiff("A","1","2"), FALSE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_collision_via_neginvp_l(self):
        """NegInvP_L derives Δ(B,2,1)⋣Δ(A,2,1); asserting ⊒ at that cell collides."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"]})
        mgr.set_rel("A", "1", "2", "A", "1", "1", GT)   # ◬_A ⋣ Δ(A,1,2)
        mgr.set_rel("A", "1", "2", "B", "1", "2", LT)   # Δ(A,1,2) ⋣ Δ(B,1,2)
        mgr.set_vdiff_relation(VDiff("B","2","1"), VDiff("A","2","1"), TRUE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_collision_via_neginvp_r(self):
        """NegInvP_R derives Δ(B,1,2)⋣Δ(A,1,2); asserting ⊒ at that cell collides."""
        mgr = make_mgr({"A": ["1","2"], "B": ["1","2"]})
        mgr.set_rel("A", "2", "1", "B", "2", "1", LT)
        mgr.set_rel("B", "2", "1", "B", "1", "1", LT)   # Δ(B,2,1) ⋣ ◬_B
        mgr.set_vdiff_relation(VDiff("B","1","2"), VDiff("A","1","2"), TRUE)
        _, _, colls = mgr.closure()
        self.assertGreater(len(colls), 0)

    def test_consistent_structure_no_collision(self):
        """A well-formed set of consistent relations must produce no collision."""
        mgr = make_mgr({"A": ["1","2","3"], "B": ["1","2"]})
        mgr.set_rel("A", "1", "3", "A", "1", "2", GT)   # Δ(A,1,3) ⊐ Δ(A,1,2)
        mgr.set_rel("A", "1", "2", "B", "1", "2", GT)   # Δ(A,1,2) ⊐ Δ(B,1,2)
        mgr.set_rel("B", "1", "2", "A", "2", "3", GTE)  # Δ(B,1,2) ⊒ Δ(A,2,3)
        _, _, colls = mgr.closure()
        self.assertEqual(colls, [])


# ── Derivation-order sorting of adds ────────────────────────────────────────────

def assert_dependency_ordered(testcase, adds):
    """Every entry must appear after whichever earlier entry (if any, within
    this same list) established one of its premises."""
    from eudoxa import _entry_conclusion_key, _entry_premise_keys
    by_conclusion = {}
    for i, entry in enumerate(adds):
        by_conclusion.setdefault(_entry_conclusion_key(entry), i)
    for i, entry in enumerate(adds):
        for premise_key in _entry_premise_keys(entry):
            j = by_conclusion.get(premise_key)
            if j is not None:
                testcase.assertLess(
                    j, i,
                    f"entry {i} ({entry[0]}) precedes entry {j}, which established one of its premises"
                )


class TestNegDiffPOrigin(unittest.TestCase):
    """origin_detail for a NegDiffP entry must record the premise (cd, ef) that
    triggered it, not (a copy of) the conclusion it produced. Getting this
    backwards makes the entry look dependency-free (its 'premise' can never
    match anything else's conclusion) and makes the explanation tautological
    (X ⋣ Y -> X ⋣ Y instead of showing what X ⋣ Y actually followed from)."""

    def test_negdiffp_origin_is_premise_not_conclusion(self):
        mgr = make_mgr({"A": ["1", "2", "3", "4"]})
        mgr.set_rel("A", "1", "3", "A", "2", "4", LT)
        _, adds, colls = mgr.closure()
        self.assertEqual(colls, [])
        negdiffp = [e for e in adds if e[0] == 'NegDiffP']
        self.assertTrue(negdiffp)
        _, origin_detail, result = negdiffp[0]
        premise_vd1, _premise_rel, premise_vd2 = origin_detail
        result_vd1, _result_rel, result_vd2 = result
        self.assertEqual((premise_vd1, premise_vd2), (VDiff("A", "1", "3"), VDiff("A", "2", "4")))
        self.assertEqual((result_vd1, result_vd2), (VDiff("A", "4", "3"), VDiff("A", "2", "1")))
        self.assertNotEqual((premise_vd1, premise_vd2), (result_vd1, result_vd2))


class TestTopologicalSortAdds(unittest.TestCase):
    """_topological_sort_adds orders a closure() `adds` list so premises always
    precede whatever they were used to derive — even though the closure's
    fixed-point loop doesn't necessarily discover them in that order."""

    def test_dependent_entry_moved_after_its_premise(self):
        from eudoxa import _topological_sort_adds
        f1, f2 = VDiff("X", "a", "b"), VDiff("X", "b", "c")
        f3, f4 = VDiff("X", "a", "c"), VDiff("X", "c", "d")
        f5, f6 = VDiff("X", "a", "d"), VDiff("X", "d", "e")
        establishes_f3_f4 = ['DiffP', [f1, TRUE, f2], [f3, TRUE, f4]]
        depends_on_f3_f4 = ['DiffP', [f3, TRUE, f4], [f5, TRUE, f6]]

        # Deliberately shuffled: the dependent entry listed first.
        sorted_adds = _topological_sort_adds([depends_on_f3_f4, establishes_f3_f4])
        self.assertEqual(sorted_adds, [establishes_f3_f4, depends_on_f3_f4])

    def test_independent_entries_keep_relative_order(self):
        from eudoxa import _topological_sort_adds
        f1, f2 = VDiff("X", "a", "b"), VDiff("X", "b", "c")
        f3, f4 = VDiff("X", "c", "d"), VDiff("X", "d", "e")
        f5, f6 = VDiff("X", "e", "f"), VDiff("X", "f", "g")
        f7, f8 = VDiff("X", "g", "h"), VDiff("X", "h", "i")
        entry_a = ['DiffP', [f1, TRUE, f2], [f5, TRUE, f6]]
        entry_b = ['DiffP', [f3, TRUE, f4], [f7, TRUE, f8]]
        # Neither entry's premise matches the other's conclusion in either
        # direction, so there's no dependency between them: order should be
        # left exactly as given.
        self.assertEqual(_topological_sort_adds([entry_a, entry_b]), [entry_a, entry_b])
        self.assertEqual(_topological_sort_adds([entry_b, entry_a]), [entry_b, entry_a])

    def test_real_closure_output_is_dependency_ordered(self):
        """Integration check: a scenario where DiffP creates a fact that TransP
        then chains through — real closure() output, not a hand-built list —
        is fully dependency-ordered."""
        mgr = make_mgr({"A": ["1", "2", "3", "4", "5"]})
        mgr.set_rel("A", "1", "3", "A", "2", "4", GTE)
        mgr.set_rel("A", "3", "4", "A", "4", "5", GTE)
        _, adds, colls = mgr.closure()
        self.assertEqual(colls, [])
        self.assertTrue(adds)
        assert_dependency_ordered(self, adds)


class TestSetVdiffRelationOrigin(unittest.TestCase):
    """try_set_vdiff_order_relation's SETVDREL origin_detail must hold the raw
    VDiff objects, not pre-formatted repr() strings. VDiff.__repr__ omits the
    aspect name (by design — it's the right call for a same-aspect display),
    so pre-formatting here would make two different-aspect VDiffs that share
    level names (e.g. Δ(A,"1","2") and Δ(B,"1","2")) indistinguishable in the
    'Set ...' message. Formatting with the aspect included belongs at display
    time (app.py's _fmt_vdiff), not baked in here."""

    def test_setvdrel_origin_holds_vdiff_objects_not_strings(self):
        # SETVDREL is only used on the unset (order_rel=UNDEFINED) path — the
        # 'set' path routes through set_rel's own SETREL origin instead. So
        # set a relation first, then unset it, to get a real SETVDREL add.
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"]})
        vd1, vd2 = VDiff("A", "1", "2"), VDiff("B", "1", "2")
        _, colls0, _ = mgr.try_set_vdiff_order_relation(vd1, vd2, GTE)
        self.assertEqual(colls0, [])
        adds, colls, _ = mgr.try_set_vdiff_order_relation(vd1, vd2, UNDEFINED)
        self.assertEqual(colls, [])
        setvdrel = [e for e in adds if e[0] == 'SETVDREL']
        self.assertTrue(setvdrel)
        _, origin_detail, _ = setvdrel[0]
        stored_vd1, _rel, stored_vd2 = origin_detail
        self.assertIsInstance(stored_vd1, VDiff)
        self.assertIsInstance(stored_vd2, VDiff)
        self.assertEqual(stored_vd1.aspect_name, "A")
        self.assertEqual(stored_vd2.aspect_name, "B")


class TestClosureRuleLabelsComplete(unittest.TestCase):
    """Every rule label closure() can produce must have a readable name in
    app.py's _CLOSURE_RULE_LABELS — otherwise it silently falls through to
    the unlabelled 'RuleName(...)' display (e.g. 'InvP_R(...)' instead of
    'Inverse difference property (right): ...'). _RULE_PREMISE_VD_PAIRS
    (eudoxa.py) enumerates every non-axiom rule label closure() uses, so
    diffing it against app.py's label dict catches any future rule that's
    added to one but not the other."""

    def test_every_closure_rule_has_a_readable_label(self):
        from eudoxa import _RULE_PREMISE_VD_PAIRS
        import app as flaskapp
        missing = set(_RULE_PREMISE_VD_PAIRS) - set(flaskapp._CLOSURE_RULE_LABELS)
        self.assertEqual(missing, set(), f"rule labels with no readable name: {missing}")


# ── Restricted closure (closure(restrict_to_aspect=...)) ───────────────────────

class TestClosureRestricted(unittest.TestCase):
    """closure(restrict_to_aspect=...) skips cross-aspect propagation: it should
    still fully infer intra-aspect chains, miss inferences that require pivoting
    through another aspect's VDiff (the accepted incompleteness trade-off), and
    still catch a genuine intra-aspect collision (restriction only removes
    inference paths, so it can never produce a false negative on collisions)."""

    def test_intra_aspect_chain_still_inferred(self):
        """Δ(A,1,2)⊒Δ(A,2,3) & Δ(A,2,3)⊒Δ(A,3,4) ==> Δ(A,1,2)⊒Δ(A,3,4),
        even when the closure is restricted to aspect A."""
        mgr = make_mgr({"A": ["1", "2", "3", "4"]})
        mgr.set_rel("A", "1", "2", "A", "2", "3", GTE)
        mgr.set_rel("A", "2", "3", "A", "3", "4", GTE)
        closure, _, colls = mgr.closure(restrict_to_aspect="A")
        self.assertEqual(colls, [])
        self.assertEqual(rel(closure, "A", "1", "2", "A", "3", "4"), TRUE)

    def test_cross_aspect_pivot_not_inferred_when_restricted(self):
        """Δ(A,1,2)⊒Δ(B,1,2) & Δ(B,1,2)⊒Δ(C,1,2) ==> Δ(A,1,2)⊒Δ(C,1,2) requires
        pivoting through B's VDiff. The unrestricted closure infers it; a
        closure restricted to A does not."""
        mgr = make_mgr({"A": ["1", "2"], "B": ["1", "2"], "C": ["1", "2"]})
        mgr.set_rel("A", "1", "2", "B", "1", "2", GTE)
        mgr.set_rel("B", "1", "2", "C", "1", "2", GTE)

        full_closure, _, full_colls = mgr.closure()
        self.assertEqual(full_colls, [])
        self.assertEqual(rel(full_closure, "A", "1", "2", "C", "1", "2"), TRUE)

        restricted_closure, _, restricted_colls = mgr.closure(restrict_to_aspect="A")
        self.assertEqual(restricted_colls, [])
        self.assertEqual(rel(restricted_closure, "A", "1", "2", "C", "1", "2"), UNDEFINED)

    def test_restricted_closure_still_catches_intra_aspect_collision(self):
        """A collision from a purely intra-aspect TransP chain is still caught
        when the closure is restricted to that aspect."""
        mgr = make_mgr({"A": ["1", "2", "3", "4"]})
        mgr.set_rel("A", "1", "2", "A", "2", "3", GTE)
        mgr.set_rel("A", "2", "3", "A", "3", "4", GTE)
        # TransP derives Δ(A,1,2)⊒Δ(A,3,4); assert the opposite directly.
        mgr.set_vdiff_relation(VDiff("A", "1", "2"), VDiff("A", "3", "4"), FALSE)
        _, _, colls = mgr.closure(restrict_to_aspect="A")
        self.assertGreater(len(colls), 0)


# ── try_stage_aspect_level_relations (preview-only staging) ────────────────────

class TestTryStageAspectLevelRelations(unittest.TestCase):
    """try_stage_aspect_level_relations previews a list of AL-relation changes
    without ever writing to self.vdiff_comparison_matrix."""

    def test_clean_staging_returns_inferred_cells(self):
        mgr = make_mgr({"A": ["1", "2", "3"]})
        adds, colls, _ = mgr.try_set_aspect_level_relation("A", "1", "2", BT)
        self.assertEqual(colls, [])
        before = {vd: dict(row) for vd, row in mgr.vdiff_comparison_matrix.items()}

        cells, adds, inferred_adds, colls = mgr.try_stage_aspect_level_relations(
            "A", [("2", "3", BT)], restrict_to_aspect=True
        )
        self.assertEqual(colls, [])
        self.assertIn({"la": "1", "lb": "3", "relation": BT}, cells)
        # adds/inferred_adds explain the result: the raw write for the
        # proposed change, and the closure-derived consequence behind the cell.
        self.assertTrue(adds)
        self.assertTrue(inferred_adds)
        # Preview only — nothing committed.
        self.assertEqual(mgr.vdiff_comparison_matrix, before)
        self.assertEqual(mgr.get_aspect_level_relation("A", "2", "3"), UNDEFINED)

    def test_colliding_staging_returns_colls_and_no_cells(self):
        mgr = make_mgr({"A": ["1", "2", "3"]})
        mgr.try_set_aspect_level_relation("A", "1", "2", BT)
        mgr.try_set_aspect_level_relation("A", "2", "3", BT)
        before = {vd: dict(row) for vd, row in mgr.vdiff_comparison_matrix.items()}

        # 1≻3 is already implied; asserting 3≻1 must collide.
        cells, adds, inferred_adds, colls = mgr.try_stage_aspect_level_relations(
            "A", [("3", "1", BT)], restrict_to_aspect=True
        )
        self.assertEqual(cells, [])
        self.assertEqual(adds, [])
        self.assertEqual(inferred_adds, [])
        self.assertGreater(len(colls), 0)
        # Preview only — nothing committed, even on collision.
        self.assertEqual(mgr.vdiff_comparison_matrix, before)


if __name__ == "__main__":
    unittest.main()
