"""Checks of the gol.gg match-list parse (a stand-in page):  python -m unittest pipeline.test_gol -v"""
import unittest
from unittest import mock
from .sources import gol

ROW = "<tr><td class='text-left'><a href='../game/stats/{id}/page-{kind}/' title='x'>x</a></td><td class='text-right text_victory'>{a}</td><td class='text-center'>1 - 0</td><td class='text_defeat'>{b}</td><td class='text-center'>ROUND1</td><td class='text-center'>16.20</td><td class='text-center'>2026-10-23</td></tr>"


class MatchList(unittest.TestCase):
    def test_a_best_of_one_listed_by_its_game_page_is_a_played_single(self):
        page = "<table><tbody>" + ROW.format(id=83645, kind="game", a="Movistar KOI", b="Bilibili Gaming") + ROW.format(id=900, kind="summary", a="X", b="Y") + ROW.format(id=901, kind="preview", a="P", b="Q") + "</tbody></table>"
        with mock.patch.object(gol, "get_text", return_value=page):
            out = {s["id"]: s for s in gol.series_list("Worlds 2026 Main Event")}
        self.assertTrue(out[83645]["played"] and out[83645]["single"])
        self.assertTrue(out[900]["played"] and not out[900]["single"])
        self.assertFalse(out[901]["played"])                                  # a preview page: not played yet


if __name__ == "__main__":
    unittest.main()
