"""Receiving-end checks for a PickFinder capture:  python -m unittest pipeline.test_pickfinder -v
The round trip uses the real slate on the site: real numbers go out as a capture and must come back unchanged."""
import copy, json, os, shutil, tempfile, unittest
from . import pickfinder as PF
from .pickfinder_example import from_site, write

SLATE = PF.jload("site/data/meta.json")["slate"]


def codes(cap, level="error"):
    return sorted({i["code"] for i in PF.validate(cap) if i["level"] == level})


def clone(cap):
    return PF.Capture(copy.deepcopy(cap.meta), copy.deepcopy(cap.legs), copy.deepcopy(cap.players))


class RoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cap = from_site("site")
        cls.tmp = tempfile.mkdtemp()
        write(cls.cap, os.path.join(cls.tmp, SLATE))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_the_real_slate_validates_with_no_errors(self):
        self.assertEqual(codes(self.cap), [])
        self.assertEqual((len(self.cap.legs), len(self.cap.players)), (299, 144))

    def test_files_load_back_identically(self):
        again = PF.load(SLATE, self.tmp)
        self.assertEqual(again.legs, self.cap.legs)
        self.assertEqual(again.players, self.cap.players)
        self.assertEqual(again.meta, self.cap.meta)

    def test_converts_back_to_the_workbook_values_exactly(self):
        r = PF.crosscheck(PF.load(SLATE, self.tmp), "site")
        self.assertTrue(r["compared"])
        self.assertEqual((r["differences"], r["missing"], r["extra"]), (0, 0, 0))
        self.assertEqual(r["detail"], [])

    def test_crosscheck_notices_a_different_slate_and_a_changed_number(self):
        other = clone(self.cap)
        other.meta["slate"] = "2000-01-01"
        self.assertFalse(PF.crosscheck(other, "site")["compared"])
        edited = clone(self.cap)
        edited.legs[0]["line"] += 1
        edited.players[edited.legs[3]["pid"]]["overall"]["maps"] += 0                      # untouched on purpose
        r = PF.crosscheck(edited, "site")
        self.assertEqual(r["differences"], 1)
        self.assertIn("line", r["detail"][0])

    def test_a_partial_capture_reports_missing_items_apart_from_value_differences(self):
        part = from_site("site", ["CS2 · AST vs MIBR"])
        r = PF.crosscheck(part, "site")
        self.assertEqual(r["differences"], 0)
        self.assertGreater(r["missing"], 100)
        self.assertEqual(r["extra"], 0)

    def test_pickfinder_only_build_flags_what_it_lacks(self):
        fps, moba = PF.to_site(self.cap, {"DEFAULT_ROUNDS_CS2": 21.5, "DEFAULT_ROUNDS_VAL": 22.5})
        self.assertEqual(fps["inputs"], dict(pickfinder=True, thunderpick=False, hltv=False))
        m = next(x for x in fps["matches"] if x["title"] == "CS2")
        self.assertEqual(m["r1"], 21.5)
        self.assertIsNone(m["pA"])
        self.assertIsNone(m["p3_used"])
        self.assertTrue(all(x["pm1"] is None for x in moba["matches"]))                   # no Thunderpick map odds, so no win probability is invented
        self.assertEqual(len(fps["legs"]) + len(moba["legs"]), 299)


class Docs(unittest.TestCase):
    def test_the_documented_example_validates(self):
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree("docs/pickfinder-capture/example", os.path.join(tmp, "2026-10-16"))
            cap = PF.load("2026-10-16", tmp)
            self.assertEqual(codes(cap), [])
            self.assertEqual(cap.meta["expected_legs"], len(cap.legs))
        finally:
            shutil.rmtree(tmp)


class Rejects(unittest.TestCase):
    def setUp(self):
        self.cap = clone(from_site("site", ["CS2 · AST vs MIBR", "LOL · KC vs MVK"]))
        self.assertEqual(codes(self.cap), [])

    def cs2_player(self):
        return next(p for p in self.cap.players.values() if p["title"] == "CS2")

    def test_page_cap_guard(self):
        self.cap.meta["expected_legs"] += 20
        self.assertEqual(codes(self.cap), ["COUNT"])

    def test_missing_expected_legs(self):
        del self.cap.meta["expected_legs"]
        self.assertIn("SCHEMA", codes(self.cap))

    def test_board_player_with_no_stats_page(self):
        pid = self.cap.legs[0]["pid"]
        del self.cap.players[pid]
        self.assertIn("NO_PLAYER", codes(self.cap))

    def test_duplicate_leg(self):
        self.cap.legs.append(copy.deepcopy(self.cap.legs[0]))
        self.cap.meta["expected_legs"] += 1
        self.assertEqual(codes(self.cap), ["DUP"])

    def test_map_identity(self):
        self.cs2_player()["map_stats"][0]["n"] += 1
        self.assertIn("IDENTITY_MAPS", codes(self.cap))

    def test_kills_identity(self):
        self.cs2_player()["map_stats"][0]["kills"] += 3
        self.assertIn("IDENTITY_KILLS", codes(self.cap))

    def test_gamelog_identity(self):
        p = next(p for p in self.cap.players.values() if p["title"] == "LOL")
        p["gamelog"][0]["m12k"] = (p["gamelog"][0]["m1k"] or 0) + (p["gamelog"][0]["m2k"] or 0) + 1
        self.assertIn("IDENTITY_GAMELOG", codes(self.cap))

    def test_hit_rates(self):
        self.cap.legs[0]["hit"]["l10"] = 1.4
        self.assertIn("HITRATE", codes(self.cap))
        self.cap.legs[0]["hit"]["l10"] = 0.37
        self.assertIn("HITRATE_GRAIN", codes(self.cap, "warning"))

    def test_bad_market_title_and_match_key(self):
        self.cap.legs[0]["market"] = "Map 2 Kills"
        self.cap.legs[1]["title"] = "XYZ"
        self.cap.legs[2]["team"] = "NOPE"
        self.assertTrue({"MARKET", "TITLE", "MATCHKEY"} <= set(codes(self.cap)))

    def test_stale_gamelog_rows_are_a_warning(self):
        p = next(p for p in self.cap.players.values() if p["title"] == "LOL")
        p["gamelog"][-1]["date"] = "2024-01-01"
        self.assertIn("STALE", codes(self.cap, "warning"))
        self.assertEqual(codes(self.cap), [])

    def test_wrong_schema(self):
        self.cap.meta["schema"] = 2
        self.assertEqual(codes(self.cap), ["SCHEMA"])


if __name__ == "__main__":
    unittest.main()
