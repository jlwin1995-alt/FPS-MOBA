import json, os, tempfile, unittest
from . import shadow as S


def put(d, rel, obj):
    p = os.path.join(d, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, "w"))


class Shadow(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        row = lambda p, res=None, act=None: {"Match": "CS2 · A vs B", "Player": "x", "Market": "Maps 1-2 Kills", "Line": 20, "Proj": 21, "P(over)": p, "Maps used": "Dust2", "Result": res, "Actual": act}
        put(self.d, "log/2026-11-26.json", {"fps": [row(0.6, "UNDER", 18), dict(row(0.4, "OVER", 25), Player="y")], "moba": []})
        put(self.d, "shadow/vetosim/2026-11-26.json", {"built": "t", "source": "s", "matches": {}, "rows": [
            {"Match": "CS2 · A vs B", "Player": "x", "Market": "Maps 1-2 Kills", "Line": 20, "Proj": 19, "P(over)": 0.4, "Maps used": "Nuke"},
            {"Match": "CS2 · A vs B", "Player": "y", "Market": "Maps 1-2 Kills", "Line": 20, "Proj": 22, "P(over)": 0.45, "Maps used": "Nuke"}]})

    def test_compare(self):
        c = S.compare("vetosim", os.path.join(self.d, "shadow"), os.path.join(self.d, "log"))["2026-11-26"]
        self.assertEqual(c["live"]["hits"], 0)          # live: x over (wrong), y under (wrong)
        self.assertEqual(c["shadow"]["hits"], 1)        # shadow: x under (right), y under (wrong)
        self.assertEqual((c["differ"], c["differ_live_right"], c["differ_shadow_right"]), (1, 0, 1))

    def test_site_rows(self):
        s = S.site_data("vetosim", os.path.join(self.d, "shadow"), os.path.join(self.d, "log"))
        r = s["slates"]["2026-11-26"]["rows"]
        self.assertEqual((r[0]["live_p"], r[0]["sh_p"], r[0]["result"], r[0]["sh_maps"]), (0.6, 0.4, "UNDER", "Nuke"))
        self.assertFalse(s["registered"])
