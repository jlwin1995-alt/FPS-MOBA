"""The kills-per-map shadow projection:  python -m unittest pipeline.test_kpm -v"""
import json, math, subprocess, unittest
from . import kpm as K
from .testing import friday_site


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class Units(unittest.TestCase):
    def fps(self, code="K12", p3=0.5, hs=0.4):
        return dict(config=dict(KILLS_DISPERSION=1.4), players=[dict(pid="p", kills_map=16.0, hs=hs)], matches=[dict(id="m", p3_used=p3)],
                    legs=[dict(key="p|m", match="m", player="x", market="mk", code=code, line=30.5)])

    def test_maps_that_count(self):
        for code, n in (("K1", 1), ("K12", 2), ("K13", 2.5)):
            self.assertAlmostEqual(K.project(self.fps(code))[("m", "x", "mk")]["proj"], 16 * n)

    def test_headshots_scale_by_overall_hs_pct_and_thin_the_spread(self):
        v = K.project(self.fps("H12", hs=0.4))[("m", "x", "mk")]
        self.assertAlmostEqual(v["proj"], 16 * 2 * 0.4)
        self.assertAlmostEqual(v["sigma"], math.sqrt(v["proj"] * (0.4 * 1.4 + 0.6)))

    def test_probabilities_are_a_normal_with_a_separate_push(self):
        v = K.project(self.fps("K12"))[("m", "x", "mk")]                      # mean 32, sd sqrt(44.8), line 30.5 (half line: no push)
        self.assertAlmostEqual(v["p_over"] + v["p_under"], 1, places=9)
        self.assertGreater(v["p_over"], 0.5)
        w = self.fps("K12"); w["legs"][0]["line"] = 32
        o = K.project(w)[("m", "x", "mk")]
        self.assertLess(o["p_over"] + o["p_under"], 1)                       # a whole-number line keeps its push probability

    def test_players_without_kills_per_map_are_skipped_and_log_rows_filled_once(self):
        f = self.fps(); f["players"][0]["kills_map"] = None
        self.assertEqual(K.project(f), {})
        log = [dict(Match="m", Player="x", Market="mk")]
        self.assertEqual(K.add_to_log(log, self.fps()), 1)
        first = dict(log[0])
        self.assertEqual(K.add_to_log(log, self.fps(hs=0.9)), 0)              # frozen: a second pass does not change a row that has the columns
        self.assertEqual(log[0], first)


class AgainstTheSite(unittest.TestCase):
    def test_python_and_javascript_agree_on_friday(self):
        site = friday_site()
        fps = load(f"{site}/data/fps.json")
        js = r'''const FPS=require("./site/fps.js"), fs=require("fs");
        const D=JSON.parse(fs.readFileSync(process.argv[1])); const r=FPS.calcAll(D,D.config,{}); const o={};
        for(const g of r.legs){ if(g.out&&g.out.proj_kpm!=null) o[g.match+"|"+g.player+"|"+g.market]=[g.out.proj_kpm,g.out.p_over_kpm]; }
        console.log(JSON.stringify(o));'''
        res = subprocess.run(["node", "-e", js, f"{site}/data/fps.json"], capture_output=True, text=True, check=True)
        got, py = json.loads(res.stdout), K.project(fps)
        self.assertTrue(got)
        self.assertEqual(len(got), len(py))
        for k, (proj, po) in got.items():
            v = py[tuple(k.split("|"))]
            self.assertAlmostEqual(v["proj"], proj, places=9)
            self.assertAlmostEqual(v["p_over"] or 0, po or 0, places=9)


if __name__ == "__main__":
    unittest.main()
