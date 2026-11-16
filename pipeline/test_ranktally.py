"""Checks of the daily lean-ranking tally:  python -m unittest pipeline.test_ranktally -v"""
import unittest
from . import ranktally as R


def row(player, po, res, adj=None, match="m"):
    return {"Player": player, "Match": match, "P(over)": po, "P(over) adj": po if adj is None else adj, "Result": res}


ROWS = [row("a", 0.90, "OVER"), row("b", 0.10, "OVER"), row("c", 0.65, "UNDER"), row("d", 0.55, None), row("e", 0.20, "UNDER", adj=0.6), row("f", None, "OVER"), row("g", 0.50, "PUSH")]


class RankTally(unittest.TestCase):
    def test_ranking_is_strongest_lean_first_and_skips_legs_without_a_p(self):
        self.assertEqual([r["Player"] for r in R.ranked(ROWS)], ["a", "b", "e", "c", "d", "g"])

    def test_side_hits_use_the_models_own_side(self):
        t = R.slate_tally(ROWS)
        # graded: a over (model over, hit), b over (model under, miss), e under (model under, hit), c under (model over, miss); d open, g push
        self.assertEqual((t["all"]["hits"], t["all"]["n"]), (2, 4))
        self.assertEqual(t["open"], 1)
        self.assertEqual((t["top"]["10"]["hits"], t["top"]["10"]["n"]), (2, 4))

    def test_buckets_and_h8_definition(self):
        t = R.slate_tally(ROWS)
        self.assertEqual((t["bucket"]["25+"]["hits"], t["bucket"]["25+"]["n"]), (2, 3))        # a (40 pts) hit, b (40 pts) miss, e (30 pts) hit
        self.assertEqual((t["bucket"]["15-20"]["hits"], t["bucket"]["15-20"]["n"]), (0, 1))    # c (15 pts, model over, went under) miss
        self.assertEqual(sum(v["n"] for v in t["bucket"].values()), t["all"]["n"])             # the buckets add up to the whole
        h8 = t["h8_def"]["all"]
        self.assertEqual((h8["hits"], h8["n"]), (1, 3))                                       # e is excluded: the adjusted model disagrees; a (hit), b (miss) and c (miss) have lean >= 10 and agree

    def test_cumulative_adds_slates(self):
        a = R.slate_tally(ROWS)
        c = R.cumulative({"x": a, "y": a})
        self.assertEqual(c["slates"], 2)
        self.assertEqual((c["all"]["hits"], c["all"]["n"]), (4, 8))


if __name__ == "__main__":
    unittest.main()
