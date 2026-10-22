"""Checks of the HLTV capture importer (synthetic captures on Friday's board):  python -m unittest pipeline.test_hltv -v"""
import copy, json, os, re, shutil, tempfile, unittest
from . import hltv as H
from .testing import FRIDAY, friday_site

def dump(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


KILLS = {"A": [15] * 5, "B": [12] * 5}
DEATHS = {"A": [13, 13, 13, 12, 12], "B": [16, 16, 16, 15, 15]}      # A's deaths = B's kills + 3; B's deaths = A's kills + 3


def capture(board_match, legs, maps=(1, 2)):
    teams = [re.sub(r"\s*\(.*?\)", "", board_match["a"]), re.sub(r"\s*\(.*?\)", "", board_match["b"])]      # HLTV writes plain names
    names = {t: [] for t in "AB"}
    for g in legs:
        side = "A" if g["team"] and board_match["a"].endswith(f"({g['team']})") or g["team"] == board_match["a"] else "B"
        if g["player"] not in names[side] and len(names[side]) < 5:
            names[side].append(g["player"])
    for t in "AB":
        names[t] += [f"filler{t}{i}" for i in range(5 - len(names[t]))]
    mp = []
    for n in maps:
        pl = [dict(name=names[t][i], team=teams[0] if t == "A" else teams[1], kills=KILLS[t][i], hs=5, deaths=DEATHS[t][i]) for t in "AB" for i in range(5)]
        mp.append(dict(n=n, map="Mirage", score=[13, 11], players=pl))
    return dict(schema=1, source="hltv.org", url="https://hltv.test/m", captured_utc="2026-10-17T20:00:00Z", teams=teams, maps=mp), names


class Pure(unittest.TestCase):
    def good(self):
        return capture(dict(a="Alpha (AA)", b="Beta (BB)"), [])[0]

    def test_a_good_capture_has_no_problems_and_passes_checks(self):
        c = self.good()
        self.assertEqual(H.problems(c), [])
        self.assertTrue(all(H.checks(m)["players_ok"] and H.checks(m)["kills_vs_deaths_ok"] and H.checks(m)["hs_le_kills"] for m in c["maps"]))

    def test_structural_problems(self):
        c = self.good()
        c["maps"][1]["n"] = 1
        c["maps"][0]["players"][0]["kills"] = "x"
        self.assertTrue(any("repeated" in p for p in H.problems(c)))
        self.assertTrue(any("bad player row" in p for p in H.problems(c)))

    def test_identity_checks_catch_each_failure(self):
        m = self.good()["maps"][0]
        bad = copy.deepcopy(m); bad["players"][0]["kills"] += 20
        self.assertFalse(H.checks(bad)["kills_vs_deaths_ok"])
        bad = copy.deepcopy(m); bad["players"][0]["hs"] = 99
        self.assertFalse(H.checks(bad)["hs_le_kills"])
        bad = copy.deepcopy(m); bad["players"].pop()
        self.assertFalse(H.checks(bad)["players_ok"])
        bad = copy.deepcopy(m); bad["players"][1]["team"] = bad["players"][9]["team"]
        self.assertFalse(H.checks(bad)["players_ok"])

    def test_bo3_numbers_are_never_replaced_and_disagreement_is_flagged(self):
        cap = self.good()
        keep = dict(n=1, map="de_mirage", rounds=24, winner="x", score=[13, 11], state="done", players=[dict(name="p", kills=1, hs=0, deaths=1, team="t", alias="p")])
        empty = dict(n=2, map="de_inferno", rounds=None, winner="x", score=[13, 5], state=None, players=[])
        old = dict(status="finished", maps=[keep, empty], checks=[dict(map=1, players_ok=True, kills_vs_deaths_ok=True, hs_le_kills=True, rounds_ok=True),
                                           dict(map=2, players_ok=False, kills_vs_deaths_ok=False, hs_le_kills=True, rounds_ok=False)])
        rec, notes = H.merge_match(old, cap, "x.json")
        self.assertIs(rec["maps"][0], keep)
        self.assertEqual(rec["maps"][1]["site"], "hltv.org")
        self.assertEqual(len(notes), 2)                                # wrong map name and wrong score on map 2
        c2 = {c["map"]: c for c in rec["checks"]}[2]
        self.assertFalse(c2["players_ok"])
        self.assertFalse(c2["rounds_ok"])


    def test_a_bo3_map_that_failed_its_checks_is_replaced_only_by_a_clean_capture(self):
        cap = self.good()
        bad = dict(n=1, map="de_mirage", rounds=24, winner="x", score=[13, 11], state="done", players=[dict(name="p", kills=10, hs=11, deaths=1, team="t", alias="p")])
        old = dict(status="finished", maps=[bad], checks=[dict(map=1, players_ok=True, kills_vs_deaths_ok=True, hs_le_kills=False, rounds_ok=True)])
        rec, notes = H.merge_match(old, cap, "x.json")
        self.assertEqual(rec["maps"][0]["site"], "hltv.org")
        self.assertTrue(any("bo3.gg failed hs_le_kills" in n for n in notes))
        wrong = dict(cap, maps=[dict(cap["maps"][0], score=[13, 9])])        # disagrees with bo3.gg on the score: bo3.gg's record stays
        rec2, _ = H.merge_match(old, wrong, "x.json")
        self.assertIs(rec2["maps"][0], bad)
        dirty = copy.deepcopy(cap)
        dirty["maps"][0]["players"][0]["hs"] = 99                             # the capture itself fails hs <= kills
        rec3, _ = H.merge_match(old, dirty, "x.json")
        self.assertIs(rec3["maps"][0], bad)


class Merge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = friday_site()
        cls.fps = load(f"{cls.site}/data/fps.json")
        cls.cs2 = [m for m in cls.fps["matches"] if m["title"] == "CS2"]

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.imports = os.path.join(os.path.dirname(self.site), "imports")
        self.m = self.cs2[0]
        self.legs = [g for g in self.fps["legs"] if g["match"] == self.m["id"]]
        empty = lambda n: dict(n=n, map="de_mirage", rounds=None, winner="x", score=[13, 11], state=None, players=[])
        res = dict(slate=FRIDAY, titles={"CS2": {self.m["id"]: dict(status="finished", maps=[empty(1), empty(2)], checks=[dict(map=n, players_ok=False, kills_vs_deaths_ok=False, hs_le_kills=True, rounds_ok=True) for n in (1, 2)])}},
                   legs=[dict(match=self.m["id"], code="K12", status="no player stats at source")])
        os.makedirs(f"{self.tmp}/results"); os.makedirs(f"{self.imports}/{FRIDAY}/hltv", exist_ok=True)
        dump(res, f"{self.tmp}/results/{FRIDAY}.json")
        self.dir = f"{self.imports}/{FRIDAY}/hltv"
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def run_apply(self):
        r = H.apply(FRIDAY, imports=self.imports, results_dir=f"{self.tmp}/results", site=self.site)
        return r, load(f"{self.tmp}/results/{FRIDAY}.json")

    def test_settles_legs_from_a_capture(self):
        cap, names = capture(self.m, self.legs)
        dump(cap, f"{self.dir}/m.json")
        r, res = self.run_apply()
        self.assertEqual(r["linked"], [self.m["id"]])
        k12 = [l for l in res["legs"] if l["match"] == self.m["id"] and l["code"] == "K12" and l["status"] == "ok"]
        self.assertTrue(k12)
        self.assertTrue(all(l["actual"] in (30, 24) and l["source"] == "hltv.org" for l in k12))
        h12 = [l for l in res["legs"] if l["code"] == "H12" and l["status"] == "ok"]
        self.assertTrue(all(l["actual"] == 10 for l in h12))
        self.assertEqual(sum(1 for l in res["legs"] if l["match"] == self.m["id"]), len(self.legs))

    def test_one_map_captures_are_joined_and_numbered(self):
        cap, _ = capture(self.m, self.legs)
        for i, m in enumerate(reversed(cap["maps"])):                  # saved out of order; the higher map-stats id is the later map
            one = dict(schema=1, kind="map", source="hltv.org", url="u", mapstatsid=100 + (1 - i), captured_utc="2026-10-17T20:00:00Z", teams=cap["teams"], map=m["map"], score=m["score"], players=m["players"])
            dump(one, f"{self.dir}/map{i}.json")
        r, res = self.run_apply()
        self.assertEqual((r["linked"], r["rejected"]), ([self.m["id"]], []))
        self.assertTrue(any(l["status"] == "ok" and l["code"] == "K12" for l in res["legs"]))
        maps = res["titles"]["CS2"][self.m["id"]]["maps"]
        self.assertEqual([x["n"] for x in maps], [1, 2])
        self.assertTrue(all(x["players"] for x in maps))

    def test_a_map_capture_without_a_map_name_is_numbered_by_id(self):
        cap, _ = capture(self.m, self.legs)
        for i, m in enumerate(cap["maps"]):
            dump(dict(schema=1, kind="map", url="u", mapstatsid=10 + i, teams=cap["teams"], map=None, score=m["score"], players=m["players"]), f"{self.dir}/n{i}.json")
        r, res = self.run_apply()
        self.assertEqual((r["linked"], r["rejected"]), ([self.m["id"]], []))
        self.assertEqual([x["n"] for x in res["titles"]["CS2"][self.m["id"]]["maps"]], [1, 2])

    def test_alias_file_links_a_renamed_team(self):
        cap, _ = capture(self.m, self.legs)
        renamed = cap["teams"][0]
        cap["teams"][0] = "Wholly Different"
        for mp in cap["maps"]:
            for pl in mp["players"]:
                if pl["team"] == renamed:
                    pl["team"] = "Wholly Different"
        dump(cap, f"{self.dir}/m.json")
        r, _ = self.run_apply()
        self.assertEqual(r["linked"], [])                                # without an alias the name does not link
        dump({"Wholly Different": renamed}, f"{self.dir}/_aliases.json")
        r, res = self.run_apply()
        self.assertEqual(r["linked"], [self.m["id"]])
        self.assertTrue(any(l["status"] == "ok" for l in res["legs"]))

    def test_a_map_capture_for_no_board_match_is_rejected(self):
        cap, _ = capture(self.m, self.legs)
        m = cap["maps"][0]
        dump(dict(schema=1, kind="map", url="u", mapstatsid=1, teams=["Nobody", "Else"], map="Mirage", score=m["score"], players=m["players"]), f"{self.dir}/x.json")
        r, _ = self.run_apply()
        self.assertEqual((r["linked"], len(r["rejected"])), ([], 1))

    def test_a_failed_check_leaves_legs_unsettled(self):
        cap, _ = capture(self.m, self.legs)
        cap["maps"][0]["players"][0]["kills"] += 25
        dump(cap, f"{self.dir}/m.json")
        r, res = self.run_apply()
        st = {l["status"] for l in res["legs"] if l["match"] == self.m["id"] and l["code"] in ("K12", "H12")}
        self.assertEqual(st, {"identity check failed"})
        self.assertFalse(any("actual" in l for l in res["legs"]))

    def test_rejected_and_unmatched_captures_change_nothing(self):
        cap, _ = capture(self.m, self.legs)
        bad = copy.deepcopy(cap); bad["maps"] = []
        other = copy.deepcopy(cap); other["teams"] = ["Nobody", "Else"]
        dump(bad, f"{self.dir}/a.json"); dump(other, f"{self.dir}/b.json")
        r, res = self.run_apply()
        self.assertEqual((r["linked"], len(r["rejected"]), r["unmatched"]), ([], 1, [["Nobody", "Else"]]))
        self.assertEqual([l["status"] for l in res["legs"]], ["no player stats at source"])


if __name__ == "__main__":
    unittest.main()
