"""Checks of the odds cross-check parsing (offline; a small real OddsPapi sample, VIT vs LOUD):  python -m unittest pipeline.test_odds -v"""
import json, os, shutil, tempfile, unittest
from . import odds as O
from .testing import FRIDAY, friday_site

SAMPLE = os.path.join(os.path.dirname(__file__), "testdata", "odds_val_vit_loud.json")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class Maths(unittest.TestCase):
    def test_devig(self):
        a, b = O.devig([1.5, 2.5])
        self.assertAlmostEqual(a + b, 1)
        self.assertAlmostEqual(a, (1 / 1.5) / (1 / 1.5 + 1 / 2.5))

    def test_agg_is_the_median(self):
        self.assertEqual(O.agg([0.4, 0.5, 0.9])["p"], 0.5)
        self.assertIsNone(O.agg([None]))

    def test_flip_swaps_sides(self):
        v = dict(p1=dict(p=0.4, n=3, lo=0.35, hi=0.45), p2=dict(p=0.6, n=3, lo=0.55, hi=0.65), sharp_p1=0.41)
        f = O.flip(v)
        self.assertEqual((f["p1"]["p"], f["p2"]["p"], f["sharp_p1"]), (0.6, 0.4, 0.59))
        self.assertEqual(O.flip(None), None)


class Sample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = load(SAMPLE)
        cls.p = O.parse(cls.raw)

    def test_series_and_maps_sum_to_one(self):
        s = self.p["series"]
        self.assertAlmostEqual(s["p1"]["p"] + s["p2"]["p"], 1, places=2)
        self.assertGreaterEqual(s["p1"]["n"], 5)
        for per, v in self.p["maps"].items():
            self.assertAlmostEqual(v["p1"]["p"] + v["p2"]["p"], 1, places=2)

    def test_best_of_five_total_maps_lines(self):
        lines = {e["line"]: e["over"]["p"] for e in self.p["total_maps"]}
        self.assertGreater(lines[3.5], lines[4.5])                     # more than 3 maps is likelier than 5

    def test_rounds_totals_and_overtime(self):
        e = O.main_line(self.p["totals"]["Total Rounds First Map|p1"])
        self.assertEqual(e["line"], 21.5)
        self.assertTrue(0.4 < e["over"]["p"] < 0.6)
        self.assertTrue(0.05 < self.p["overtime"]["1"]["yes"]["p"] < 0.4)

    def test_team_kills_are_oriented_to_the_board(self):
        board = dict(a="Team Vitality (VIT)", b="LOUD (LOUD)", pA=0.4, p3_used=1, bo=5)
        v = O.view(O.parse(self.raw), board, ["Vitality", "LOUD"])
        w = O.view(O.parse(self.raw), board, ["LOUD", "Vitality"])
        self.assertEqual(v["team_kills"].keys(), w["team_kills"].keys())               # present (or both empty for this Valorant sample)
        for per in v["team_kills"]:
            self.assertEqual(v["team_kills"][per]["A"], w["team_kills"][per]["B"])

    def test_no_player_props_were_priced(self):
        self.assertEqual(self.p["player"], {})


class Build(unittest.TestCase):
    def test_view_orients_to_the_board_and_build_writes_files(self):
        site = friday_site()
        board = next(m for m in load(f"{site}/data/fps.json")["matches"] if m["id"] == "VAL · VIT vs LOUD")
        v = O.view(O.parse(load(SAMPLE)), board, ["Vitality", "LOUD"])
        self.assertFalse(v["swapped"])
        w = O.view(O.parse(load(SAMPLE)), board, ["LOUD", "Vitality"])
        self.assertTrue(w["swapped"])
        self.assertAlmostEqual(v["series"]["p1"]["p"] + w["series"]["p1"]["p"], 1, places=3)
        self.assertEqual(v["model"]["pA"], board["pA"])
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        os.makedirs(f"{tmp}/raw/{FRIDAY}")
        shutil.copy(SAMPLE, f"{tmp}/raw/{FRIDAY}/f1.json")
        imports = os.path.join(os.path.dirname(site), "imports")
        os.makedirs(f"{tmp}/site/data")
        shutil.copy(f"{site}/data/meta.json", f"{tmp}/site/data/meta.json")
        for n in ("fps", "moba"):
            shutil.copy(f"{site}/data/{n}.json", f"{tmp}/site/data/{n}.json")
        r = O.build(FRIDAY, site=f"{tmp}/site", imports=imports, raw=f"{tmp}/raw", out=f"{tmp}/out")
        self.assertEqual(list(r["matches"]), ["VAL · VIT vs LOUD"])
        self.assertTrue(os.path.exists(f"{tmp}/out/{FRIDAY}.json") and os.path.exists(f"{tmp}/site/data/odds.json"))


if __name__ == "__main__":
    unittest.main()
