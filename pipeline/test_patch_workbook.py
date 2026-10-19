"""The PROJ_MODE workbook patch, recalculated in LibreOffice (skipped where it is not installed):  python -m unittest pipeline.test_patch_workbook -v
Mode 0 must reproduce the workbook exactly; mode 1 must equal the kills-per-map projection in pipeline/kpm.py (and the browser port, via the parity test on a patched import)."""
import shutil, tempfile, unittest
from . import import_xlsx as I
from . import kpm as K
from . import patch_workbook as PW
from . import recalc as RC

FPS = "data/imports/2026-10-16/fps.xlsx"


@unittest.skipUnless(shutil.which("soffice") or shutil.which("libreoffice"), "LibreOffice not installed")
class Patch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        for mode in (0, 1):
            PW.patch(FPS, f"{cls.tmp}/m{mode}.xlsx", mode)
            RC.recalc(f"{cls.tmp}/m{mode}.xlsx")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_mode_0_reproduces_the_workbook(self):
        _, _, ex0, _ = I.import_fps(FPS)
        _, d, ex1, _ = I.import_fps(f"{self.tmp}/m0.xlsx")
        self.assertEqual(d["config"]["PROJ_MODE"], 0)
        for a, b in zip(ex0, ex1):
            for k in ("proj", "sigma", "p_over", "proj_adj", "p_over_adj"):
                self.assertTrue((a[k] is None and b[k] is None) or abs(a[k] - b[k]) < 1e-6, (k, a[k], b[k]))

    def test_mode_1_is_kills_per_map(self):
        _, orig, _, _ = I.import_fps(FPS)
        _, d, ex, _ = I.import_fps(f"{self.tmp}/m1.xlsx")
        self.assertEqual(d["config"]["PROJ_MODE"], 1)
        sh, n = K.project(orig), 0
        for leg, e in zip(d["legs"], ex):
            v = sh.get((leg["match"], leg["player"], leg["market"]))
            if v is None or e["proj"] is None:
                continue
            n += 1
            self.assertAlmostEqual(v["proj"], e["proj"], places=9)
            self.assertAlmostEqual(v["p_over"], e["p_over"], places=9)
        self.assertGreater(n, 100)

    def test_patching_twice_changes_nothing_more(self):
        PW.patch(f"{self.tmp}/m1.xlsx", f"{self.tmp}/again.xlsx", 1)
        import openpyxl
        a, b = openpyxl.load_workbook(f"{self.tmp}/m1.xlsx")["Calc"], openpyxl.load_workbook(f"{self.tmp}/again.xlsx")["Calc"]
        self.assertEqual([c.value for c in a["V"]], [c.value for c in b["V"]])


if __name__ == "__main__":
    unittest.main()
