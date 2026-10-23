"""Checks of the OpenDota results source with a stand-in for the API:  python -m unittest pipeline.test_opendota -v"""
import unittest
from unittest import mock
from .sources import opendota as O


def game(mid, t, rad_win, kills=(5, 5, 5, 5, 5), dire=(3, 3, 3, 3, 3)):
    return dict(match_id=mid, start_time=t, radiant_name="Alpha", dire_name="Beta", radiant_win=rad_win, series_id=7, series_type=1, radiant_score=sum(kills), dire_score=sum(dire))


def match(row, kills=(5, 5, 5, 5, 5), dire=(3, 3, 3, 3, 3)):
    ps = [dict(account_id=100 + i, name=f"A{i}", personaname=f"a{i}", kills=kills[i], deaths=dire[i], player_slot=i, isRadiant=True) for i in range(5)]
    ps += [dict(account_id=200 + i, name=f"B{i}", personaname=f"b{i}", kills=dire[i], deaths=kills[i], player_slot=128 + i, isRadiant=False) for i in range(5)]
    return dict(radiant_team=dict(name="Alpha"), dire_team=dict(name="Beta"), radiant_score=row["radiant_score"], dire_score=row["dire_score"], radiant_win=row["radiant_win"], players=ps, duration=2000)


class Series(unittest.TestCase):
    def test_finished_needs_the_wins_for_the_series_type(self):
        s = dict(bo=3, games=[game(1, 1, True)])
        self.assertFalse(O.finished(s))                                       # 1-0 of a best of 3
        s["games"].append(game(2, 2, True))
        self.assertTrue(O.finished(s))                                        # 2-0
        s5 = dict(bo=5, games=[game(1, 1, True), game(2, 2, True), game(3, 3, False)])
        self.assertFalse(O.finished(s5))

    def test_pro_series_groups_games_by_series_oldest_first(self):
        rows = [game(3, 30, True), game(2, 20, False), dict(game(9, 5, True), series_id=8, series_type=0)]
        with mock.patch.object(O, "get_json", return_value=rows):
            out = {s["series_id"]: s for s in O.pro_series(0, max_pages=1)}
        self.assertEqual([g["match_id"] for g in out[7]["games"]], [2, 3])
        self.assertEqual((out[7]["bo"], out[8]["bo"]), (3, 1))

    def _maps(self, recent, rows):
        def fake(url, **kw):
            if "/matches/" in url:
                row = next(r for r in rows if str(r["match_id"]) in url)
                return match(row)
            aid = int(url.split("/players/")[1].split("/")[0])
            return [dict(r, kills=r["kills"] if aid < 200 else r["kills"] - 2) for r in recent]          # Alpha players got 5, Beta players 3
        with mock.patch.object(O, "get_json", side_effect=fake):
            return O.series_maps(dict(bo=3, games=rows))

    def test_clean_series_passes_every_check_and_route_two_agrees(self):
        rows = [game(1, 1, True), game(2, 2, True)]
        r = self._maps([dict(match_id=1, kills=5), dict(match_id=2, kills=5)], rows)
        self.assertTrue(all(c["players_ok"] and c["kills_vs_deaths_ok"] and c["rounds_ok"] for c in r["checks"]))
        self.assertEqual(r["route2"]["mismatched"], 0)
        self.assertGreater(r["route2"]["players"], 0)
        self.assertEqual(r["maps"][0]["players"][0]["name"], "A0")

    def test_a_player_whose_own_history_disagrees_fails_the_game(self):
        rows = [game(1, 1, True)]
        r = self._maps([dict(match_id=1, kills=9)], rows)
        self.assertFalse(r["checks"][0]["players_ok"])
        self.assertGreater(r["route2"]["mismatched"], 0)

    def test_team_score_far_from_the_players_sum_fails_the_header_check(self):
        row = dict(game(1, 1, True), radiant_score=40)                         # players sum to 25
        r = self._maps([], [row])
        self.assertFalse(r["checks"][0]["rounds_ok"])


if __name__ == "__main__":
    unittest.main()
