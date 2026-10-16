"""Offline checks of the results logic (no network):  python -m unittest pipeline.test_results -v"""
import datetime as dt, unittest
from . import results as R
from . import settle as S
from .names import same_team, same_player


def game_players(team_a, team_b, k=10):
    return [dict(name=f"{t}{i}", alias=None, team=t, kills=k + i, hs=i, deaths=k + i) for t in (team_a, team_b) for i in range(5)]


CHECK_OK = dict(players_ok=True, kills_vs_deaths_ok=True, hs_le_kills=True, rounds_ok=True)


def match(maps, checks=None, status="finished"):
    return dict(status=status, maps=maps, checks=checks or [dict(map=m["n"], **CHECK_OK) for m in maps])


def mp(n, players, state="done"):
    return dict(n=n, map=f"map{n}", state=state, players=players)


PL = [dict(pid="p1", player="AA1", team="AA")]
LEG = lambda code, key="p1|M": dict(match="CS2 · AA vs BB", player="AA1", market="Maps 1-2 Kills", code=code, key=key, line=20.5)


class Names(unittest.TestCase):
    def test_teams(self):
        self.assertTrue(same_team("Apogee Esports (BCA)", "Betclic Apogee Esports"))
        self.assertTrue(same_team("Eternal Fire (EF)", "Eternal Fire"))
        self.assertFalse(same_team("Team Liquid (TL)", "Team Vitality"))

    def test_players(self):
        self.assertTrue(same_player("MartinezSa", "Martinez"))
        self.assertTrue(same_player("luk xo", "Lukxo"))
        self.assertFalse(same_player("ab", "abc"))                     # too short to be called a match by containment


class Legs(unittest.TestCase):
    def run_leg(self, code, m):
        return R.leg_actuals([LEG(code)], PL, {"CS2 · AA vs BB": m})[0]

    def test_ok_sums_the_maps_needed(self):
        m = match([mp(1, game_players("AA", "BB")), mp(2, game_players("AA", "BB", 5))])
        # player AA1 has kills 11 on map 1 (base 10 + 1) and 6 on map 2 (base 5 + 1), and 1 headshot on each
        self.assertEqual(self.run_leg("K1", m)["actual"], 11)
        self.assertEqual(self.run_leg("K12", m)["actual"], 17)
        self.assertEqual(self.run_leg("H12", m)["actual"], 2)

    def test_bo1_has_no_map_two(self):
        self.assertTrue(self.run_leg("K12", match([mp(1, game_players("AA", "BB"))]))["status"].startswith("void"))

    def test_source_has_the_map_but_no_table(self):
        m = match([mp(1, game_players("AA", "BB")), mp(2, [], state=None)])
        self.assertEqual(self.run_leg("K12", m)["status"], "no player stats at source")

    def test_stand_in_is_a_dnp(self):
        m = match([mp(1, game_players("AA", "BB"))])
        l = R.leg_actuals([dict(LEG("K1"), player="Zed")], [dict(pid="p1", player="Zed", team="AA")], {"CS2 · AA vs BB": m})[0]
        self.assertTrue(l["status"].startswith("did not play"))

    def test_failed_identity_blocks_the_actual(self):
        m = match([mp(1, game_players("AA", "BB"))], checks=[dict(map=1, players_ok=True, kills_vs_deaths_ok=False, hs_le_kills=True, rounds_ok=True)])
        l = self.run_leg("K1", m)
        self.assertEqual(l["status"], "identity check failed")
        self.assertNotIn("actual", l)

    def test_unfinished(self):
        self.assertTrue(R.leg_actuals([LEG("K1")], PL, {})[0]["status"].startswith("match not found"))


class Linking(unittest.TestCase):
    def test_one_team_needs_a_close_start_and_both_teams_does_not(self):
        board = [dict(id="CS2 · EF vs BCA", a="Eternal Fire (EF)", b="Apogee Esports (BCA)", start="Fri 03:00")]
        exp = R.board_start_utc("2026-10-16", "Fri 03:00")
        ok = dict(id=1, t1=["Eternal Fire"], t2=["Betclic Apogee Esports"], start=exp + dt.timedelta(hours=10))
        self.assertIn("CS2 · EF vs BCA", R.link_matches("2026-10-16", board, [ok], None))
        one_far = dict(id=2, t1=["Eternal Fire"], t2=["Someone Else"], start=exp + dt.timedelta(hours=10))
        self.assertNotIn("CS2 · EF vs BCA", R.link_matches("2026-10-16", board, [one_far], None))
        one_near = dict(id=3, t1=["Eternal Fire"], t2=["Someone Else"], start=exp + dt.timedelta(hours=1))
        self.assertIn("CS2 · EF vs BCA", R.link_matches("2026-10-16", board, [one_near], None))

    def test_a_source_match_is_used_once(self):
        board = [dict(id="CS2 · A vs B", a="Alpha (AAA)", b="Beta (BBB)", start="Fri 03:00"), dict(id="CS2 · A vs B 2", a="Alpha (AAA)", b="Beta (BBB)", start="Fri 03:00")]
        c = dict(id=1, t1=["Alpha"], t2=["Beta"], start=R.board_start_utc("2026-10-16", "Fri 03:00"))
        self.assertEqual(len(R.link_matches("2026-10-16", board, [c], None)), 1)


class Settle(unittest.TestCase):
    def test_frozen_values_survive_and_actuals_are_never_overwritten(self):
        log = [dict(Match="CS2 · AA vs BB", Player="A1", Market="Maps 1-2 Kills", Line=20.5, Proj=21.0, Actual=None)]
        legs = [dict(match="CS2 · AA vs BB", player="A1", market="Maps 1-2 Kills", status="ok", actual=25)]
        n = S.apply(log, legs, lambda m: m.split(" ")[0])
        self.assertEqual((log[0]["Actual"], log[0]["Result"], log[0]["Proj"], n["set"]), (25, "OVER", 21.0, 1))
        legs[0]["actual"] = 99                                          # a later, different pull
        n = S.apply(log, legs, lambda m: m.split(" ")[0])
        self.assertEqual((log[0]["Actual"], len(n["conflict"])), (25, 1))

    def test_push_and_note(self):
        log = [dict(Match="VAL · A vs B", Player="x", Market="Maps 1-2 Kills", Line=27, Actual=None), dict(Match="VAL · A vs B", Player="y", Market="Maps 1-2 Kills", Line=20.5, Actual=None)]
        legs = [dict(match="VAL · A vs B", player="x", market="Maps 1-2 Kills", status="ok", actual=27), dict(match="VAL · A vs B", player="y", market="Maps 1-2 Kills", status="did not play / not in the map tables", detail="0 rows")]
        S.apply(log, legs, lambda m: m.split(" ")[0])
        self.assertEqual(log[0]["Result"], "PUSH")
        self.assertIsNone(log[1]["Actual"])
        self.assertIn("did not play", log[1]["Note"])


if __name__ == "__main__":
    unittest.main()
