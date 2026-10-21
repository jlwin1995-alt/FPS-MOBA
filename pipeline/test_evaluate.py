"""Checks of the evaluation statistics and a Friday run end to end:  python -m unittest pipeline.test_evaluate -v"""
import os, shutil, tempfile, unittest
from . import evaluate as E
from .testing import friday_site


class Stats(unittest.TestCase):
    def test_auc(self):
        self.assertEqual(E.auc([0, 0, 1, 1], [1, 2, 3, 4]), 1.0)
        self.assertEqual(E.auc([1, 1, 0, 0], [1, 2, 3, 4]), 0.0)
        self.assertEqual(E.auc([0, 1, 0, 1], [5, 5, 5, 5]), 0.5)
        self.assertIsNone(E.auc([1, 1], [1, 2]))

    def test_wilson(self):
        lo, hi = E.wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=3)
        self.assertAlmostEqual(hi, 0.7634, places=3)
        self.assertIsNone(E.wilson(0, 0))

    def test_boot_needs_two_clusters_and_is_deterministic(self):
        f = lambda idx: sum(idx) / len(idx)
        self.assertIsNone(E.boot(f, ["a", "a", "a"]))
        cl = list("aabbccdd")
        self.assertEqual(E.boot(f, cl), E.boot(f, cl))

    def test_verdict(self):
        up = dict(value=.2, ci=[.1, .3])
        down = dict(value=-.2, ci=[-.3, -.1])
        mid = dict(value=0, ci=[-.1, .1])
        self.assertEqual(E.verdict(up, ">0", 10, 100, 60), "supported")
        self.assertEqual(E.verdict(down, ">0", 10, 100, 60), "contradicted")
        self.assertEqual(E.verdict(mid, ">0", 10, 100, 60), "inconclusive")
        self.assertEqual(E.verdict(down, "<0", 10, 100, 60), "supported")
        self.assertEqual(E.verdict(up, ">0", 3, 100, 60), "insufficient data")
        self.assertEqual(E.verdict(up, ">0", 10, 10, 60), "insufficient data")
        self.assertEqual(E.verdict(dict(value=None, ci=None), ">0", 10, 100, 60), "insufficient data")

    def test_flex_breakeven(self):
        self.assertAlmostEqual(E.BREAKEVEN["5-pick flex"], 0.5425, places=3)
        self.assertAlmostEqual(E.BREAKEVEN["6-pick flex"], 0.5421, places=3)
        self.assertAlmostEqual(E.breakeven(2, {2: 3}), 0.5774, places=3)            # a 2-pick power play at 3x

    def test_overrides_skips_unfinished_and_roundless(self):
        res = {"titles": {"CS2": {
            "a": dict(status="finished", maps=[dict(n=1, map="Mirage", rounds=21)]),
            "b": dict(status="finished", maps=[dict(n=1, map="Mirage", rounds=None)]),
            "c": dict(status="live", maps=[dict(n=1, map="Mirage", rounds=21)])}}}
        out = E.overrides(res, [dict(title="CS2", id=i) for i in "abc"])
        self.assertEqual(list(out), ["a"])
        self.assertEqual(out["a"]["rounds"][0], 21)


class Friday(unittest.TestCase):
    """Anchored to the numbers reported for the 2026-10-16 slate."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        site = friday_site()
        shutil.copy("site/data/log/2026-10-16.json", os.path.join(site, "data", "log", "2026-10-16.json"))  # the settled Log is the record
        imports = os.path.join(os.path.dirname(site), "imports")
        cls.rep = E.run(["2026-10-16"], site=site, results_dir="data/results", imports=imports, out_dir=os.path.join(cls.tmp, "ev"))
        cls.s = cls.rep["by_slate"]["2026-10-16"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_counts(self):
        self.assertEqual((self.s["n_settled"], self.s["n_matches"]), (183, 13))
        self.assertEqual(self.s["auc"]["model P(over)"]["n"], 176)

    def test_headline_numbers(self):
        self.assertAlmostEqual(self.s["auc"]["model P(over)"]["value"], 0.576, places=3)
        self.assertAlmostEqual(self.s["error"]["all"]["mae_line"], 3.8552, places=3)
        self.assertAlmostEqual(self.s["error"]["all"]["mae_proj"], 3.9904, places=3)
        self.assertAlmostEqual(self.s["counterfactual"]["bias_actual_inputs"], -0.0265, places=3)
        self.assertEqual((self.s["map_picks"]["hit"], self.s["map_picks"]["total"]), (5, 20))

    def test_exploratory_only(self):
        self.assertIsNone(self.rep["confirmatory"])
        st = {h["id"]: h["status"] for h in self.rep["by_slate"]["2026-10-16"]["hypotheses"]}
        self.assertTrue(all(st[k] == "inconclusive" for k in ("H1", "H2", "H3", "H4", "H5", "H6")))
        self.assertTrue(st["H7"].startswith("descriptive"))                  # written after this slate

    def test_agree10_rule_and_h8(self):
        self.assertTrue(E.agree10(0.70, 0.62))
        self.assertTrue(E.agree10(0.30, 0.38))
        self.assertFalse(E.agree10(0.70, 0.55))          # second model leans < 10 pts
        self.assertFalse(E.agree10(0.60, 0.40))          # the models disagree
        self.assertFalse(E.agree10(None, 0.7))
        r = self.s["rules"]["agree10"]
        self.assertEqual((r["hits"], r["n"]), (35, 55))
        h8 = {h["id"]: h["status"] for h in self.rep["by_slate"]["2026-10-16"]["hypotheses"]}["H8"]
        self.assertTrue(h8.startswith("descriptive"))

    def test_all_under_rule_and_h10(self):
        r = self.s["rules"]["all_under"]
        self.assertEqual((r["hits"], r["n"]), (107, 176))                      # Friday: 107 of the 176 graded legs finished under
        h10 = {h["id"]: h["status"] for h in self.rep["by_slate"]["2026-10-16"]["hypotheses"]}["H10"]
        self.assertTrue(h10.startswith("descriptive"))                          # declared after 2026-10-19

    def test_under_core_rule_and_h11(self):
        ok = dict(line=28.5, market="Maps 1-2 Kills", pf=0.5)
        self.assertTrue(E.under_core(0.30, 0.35, **ok))
        self.assertFalse(E.under_core(0.30, 0.55, **ok))                        # the second model leans over
        self.assertFalse(E.under_core(0.45, 0.40, **ok))                        # base P(over) not below 40%
        self.assertFalse(E.under_core(0.30, 0.35, **dict(ok, line=22.5)))       # line 20-25
        self.assertFalse(E.under_core(0.30, 0.35, **dict(ok, pf=0.2)))          # PF L10 too low
        self.assertFalse(E.under_core(0.30, 0.35, **dict(ok, pf=0.7)))          # ... or 0.7 and up
        self.assertFalse(E.under_core(0.30, 0.35, **dict(ok, pf=None)))
        self.assertFalse(E.under_core(0.30, 0.35, **dict(ok, market="Maps 1-3 Kills")))
        h11 = {h["id"]: h["status"] for h in self.rep["by_slate"]["2026-10-16"]["hypotheses"]}["H11"]
        self.assertTrue(h11.startswith("descriptive"))                          # declared after 2026-10-21

    def test_side_record(self):
        d = self.s["side"]
        self.assertEqual((d["hits"], d["n"]), (93, 176))
        self.assertAlmostEqual(d["rate"], 0.5284, places=3)
        self.assertLess(d["headroom"], 0)
        self.assertIsNone(d["legs_to_confirm"])


if __name__ == "__main__":
    unittest.main()
