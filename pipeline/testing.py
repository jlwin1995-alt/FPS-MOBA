"""Shared test fixtures. The suite must never depend on which slate happens to be live on the site, so the 2026-10-16 slate is imported once, from its own
workbooks in data/imports (an immutable record), into a temporary site directory."""
import atexit, math, shutil, sys, tempfile

FRIDAY = "2026-10-16"
_cache = {}


def friday_site():
    """Path of a temporary site directory holding the 2026-10-16 slate."""
    if "site" not in _cache:
        from . import import_xlsx
        tmp = tempfile.mkdtemp(prefix="friday_")
        atexit.register(shutil.rmtree, tmp, ignore_errors=True)
        argv, sys.argv = sys.argv, ["import", "--fps", f"data/imports/{FRIDAY}/fps.xlsx", "--moba", f"data/imports/{FRIDAY}/moba.xlsx", "--site", f"{tmp}/site", "--imports", f"{tmp}/imports"]
        try:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                import_xlsx.main()
        finally:
            sys.argv = argv
        _cache["site"] = f"{tmp}/site"
    return _cache["site"]


def same(a, b, tol=1e-9):
    """Deep equality where floats match to a tolerance (a re-saved workbook rounds to 15 digits)."""
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=tol, abs_tol=tol)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
    return a == b
