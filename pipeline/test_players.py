"""Checks of the player over/under-performer log:  python -m unittest pipeline.test_players -v"""
import unittest
from . import players as P


def leg(slate, key, act, line=10.0, proj=10.0, match="m", kind="K"):
    return dict(slate=slate, title="CS2", player=key, key="CS2|" + key, kind=kind, match=slate + match, line=line, proj=proj, act=act,
                result="OVER" if act > line else "UNDER" if act < line else "PUSH")


LEGS = [leg(f"2026-10-{d:02d}", "hot", 15) for d in range(1, 11)] + [leg(f"2026-10-{d:02d}", "cold", 6) for d in range(1, 11)] + \
       [leg(f"2026-10-{d:02d}", p, a) for d in range(1, 11) for p, a in (("a", 9), ("b", 11), ("c", 12), ("d", 8))]


class Players(unittest.TestCase):
    def setUp(self):
        self.obs = P.observations(LEGS)
        rows, self.par = P.player_table(self.obs, min_n=8)
        self.rows = {r["player"]: r for r in rows}

    def test_one_observation_per_player_match_and_type(self):
        self.assertEqual(len(self.obs), 60)

    def test_legs_of_one_player_and_match_are_merged(self):
        two = P.observations([leg("2026-10-01", "x", 12, match="g"), leg("2026-10-01", "x", 14, match="g", line=20.0)])
        self.assertEqual(len(two), 1)
        self.assertAlmostEqual(two[0]["e_line"], (0.2 + (14 / 20 - 1)) / 2)

    def test_consistent_over_and_under_performers_are_flagged(self):
        self.assertEqual(self.rows["hot"]["flag"], "OVER")
        self.assertEqual(self.rows["cold"]["flag"], "UNDER")

    def test_shrunk_estimate_is_nearer_zero_than_the_raw_mean(self):
        self.assertLess(abs(self.rows["hot"]["shrunk_vs_line"]), abs(self.rows["hot"]["err_vs_line"]))

    def test_too_few_matches_is_never_flagged(self):
        rows, _ = P.player_table([o for o in self.obs if o["slate"] < "2026-10-05"], min_n=8)
        self.assertTrue(all(r["flag"] is None for r in rows))

    def test_walk_forward_scores_only_later_legs_of_flagged_players(self):
        wf = P.walk_forward(self.obs, LEGS, min_n=5)["over_rate_of_legs"]
        self.assertEqual(wf["OVER"]["rate"], 1.0)
        self.assertEqual(wf["UNDER"]["rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
