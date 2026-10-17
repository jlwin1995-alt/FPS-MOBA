"""Recalculating a workbook that has no stored results must give back the numbers a calculated one has:  python -m unittest pipeline.test_recalc -v
Skipped where LibreOffice is not installed."""
import shutil, sys, tempfile, unittest
import openpyxl
from . import import_xlsx as I
from . import recalc as RC
from .testing import same

FPS, MOBA = "data/imports/2026-10-16/fps.xlsx", "data/imports/2026-10-16/moba.xlsx"


def strip(src, dst):
    openpyxl.load_workbook(src).save(dst)                               # keeps formulas, drops stored results


@unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
class Recalc(unittest.TestCase):
    def test_a_stripped_workbook_is_recalculated_to_the_same_slate_data(self):
        tmp = tempfile.mkdtemp()
        try:
            f, m = f"{tmp}/fps.xlsx", f"{tmp}/moba.xlsx"
            strip(FPS, f)
            strip(MOBA, m)
            self.assertLess(RC.stored_share(f), 0.5)
            self.assertGreaterEqual(RC.recalc(f), 0.99)
            self.assertGreaterEqual(RC.recalc(m), 0.99)
            s0, fps0, ex0, _ = I.import_fps(FPS)
            s1, fps1, ex1, _ = I.import_fps(f)
            self.assertEqual(s0, s1)
            self.assertTrue(same(fps0["legs"], fps1["legs"]))
            self.assertTrue(same(fps0["players"], fps1["players"]))
            for a, b in zip(fps0["matches"], fps1["matches"]):
                for k in ("m1", "m2", "m3", "r1", "r2", "r3", "p3_used", "hist_a", "hist_b", "pA", "pAm1"):
                    self.assertAlmostEqual(a[k] or 0, b[k] or 0, places=6, msg=f"{a['id']} {k}")
            self.assertEqual(len(ex0), len(ex1))
            for a, b in zip(ex0, ex1):
                for k in ("proj", "sigma", "p_over", "proj_adj", "mult"):
                    if isinstance(a[k], (int, float)):
                        self.assertAlmostEqual(a[k], b[k], places=6, msg=f"{a['key']} {a['code']} {k}")
        finally:
            shutil.rmtree(tmp)

    def test_an_already_calculated_workbook_is_left_alone(self):
        tmp = tempfile.mkdtemp()
        try:
            f = f"{tmp}/moba.xlsx"
            shutil.copyfile(MOBA, f)
            before = open(f, "rb").read()
            argv = sys.argv
            sys.argv = ["recalc", f]
            try:
                with self.assertRaises(SystemExit) as e:
                    RC.main()
            finally:
                sys.argv = argv
            self.assertEqual(e.exception.code, 0)
            self.assertEqual(open(f, "rb").read(), before)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
