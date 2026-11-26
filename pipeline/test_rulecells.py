import json, os, tempfile, unittest
from . import rulecells as R


class Cells(unittest.TestCase):
    def test_build(self):
        d = tempfile.mkdtemp()
        os.makedirs(d + "/plays"); os.makedirs(d + "/log")
        mk = lambda p, res: {"Match": "CS2 · A vs B", "Player": p, "Market": "Maps 1-2 HS", "Line": 10, "Result": res}
        json.dump({"fps": [mk("x", "OVER"), mk("y", "UNDER"), mk("z", "PUSH")], "moba": []}, open(d + "/log/2026-11-26.json", "w"))
        leg = lambda p, side: {"match": "CS2 · A vs B", "player": p, "market": "Maps 1-2 HS", "line": 10, "side": side}
        json.dump({"rules": {"l10_over": {"n": 3, "legs": [leg("x", "OVER"), leg("y", "OVER"), leg("z", "OVER")]}, "all_under": {"n": 3}}, "moba_rules": {}}, open(d + "/plays/2026-11-26.json", "w"))
        rep = R.build(d + "/plays", d + "/log")
        cell = {(c["rule"], c["side"], c["prop"]): (c["hits"], c["n"]) for c in rep["cells"]}
        self.assertEqual(cell[("l10_over", "OVER", "HS")], (1, 2))           # x hit, y missed, the push is excluded
        self.assertEqual(cell[("all_under", "UNDER", "HS")], (1, 2))         # y hit, x missed
        self.assertEqual(rep["through"], "2026-11-26")


if __name__ == "__main__":
    unittest.main()
