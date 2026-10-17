"""Give a workbook stored results by recalculating it with LibreOffice.

    python -m pipeline.recalc data/imports/2026-10-17/fps.xlsx data/imports/2026-10-17/moba.xlsx      # in place
    python -m pipeline.recalc FILE --check                                                          # report only; exit 1 if it has no stored results

A workbook saved by a script (not by Sheets or Excel) holds formulas but no results, and the importer reads results. Imported as it stands it would lose
everything that is calculated in the sheet: the round-differential layer, the rounds on some matches, the expected values the model is tested against.
The importer refuses such a file; this makes one that it accepts. Checked on Friday's workbooks: stripping their stored results and recalculating reproduced
29,133 FPS cells and 1,734 MOBA cells (worst difference 5e-9). The one difference is Valorant's HS-share cell, which Sheets fills with 0 and LibreOffice leaves blank.
"""
import argparse, os, shutil, subprocess, sys, tempfile
import openpyxl


def stored_share(path):
    """Share of the Projections rows whose Proj cell holds a number (1.0 for a calculated workbook, 0.0 for one saved without results)."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["Projections"]
    rows = list(ws.iter_rows(values_only=True))
    col = rows[0].index("Proj")
    body = [r for r in rows[1:] if r and r[0] not in (None, "")]
    wb.close()
    return sum(1 for r in body if isinstance(r[col], (int, float)) and not isinstance(r[col], bool)) / len(body) if body else 1.0


def recalc(path):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise SystemExit("LibreOffice (soffice) is not installed here; recalculate the workbook by opening and re-saving it in Sheets or Excel")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([soffice, "--headless", "--norestore", "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", tmp, path], check=True, capture_output=True, timeout=600)
        out = os.path.join(tmp, os.path.basename(path))
        share = stored_share(out)
        if share < 0.99:
            raise SystemExit(f"{path}: recalculation left {1 - share:.0%} of the projections empty; not replacing the file")
        shutil.copyfile(out, path)
    return share


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    bad = 0
    for f in a.files:
        before = stored_share(f)
        if a.check:
            print(f"{f}: {before:.0%} of projections have a stored result")
            bad += before < 0.5
        elif before >= 0.99:
            print(f"{f}: already calculated ({before:.0%}); left as it is")
        else:
            print(f"{f}: {before:.0%} stored -> {recalc(f):.0%} after recalculation")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
