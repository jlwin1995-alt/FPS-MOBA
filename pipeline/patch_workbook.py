"""Add the PROJ_MODE switch to an FPS workbook: 0 = the published KPR x rounds projection, 1 = career kills per map (no map names, no rounds).

    python -m pipeline.patch_workbook in.xlsx out.xlsx [--mode 0|1]     # then recalculate: python -m pipeline.recalc out.xlsx

What it changes (idempotent; everything else in the workbook is untouched):
  Config   A16 'PROJ_MODE', B16 = mode, C16 = explanation (row 16 is blank in the current template)
  Calc     M1/M2/M3 Kills (V, AC, AJ) and M1/M2/M3 HS (W, AD, AK) become  =IF(Config!$B$16=1, <kills per map version>, <the existing formula>)
           kills per map version:  Kills = Players 'Kills/Map' (when the map slot is in use);  HS = that x the player's overall HS% (Calc P, 'HS% all')
Everything downstream (Kills 1-2, Kills 1-3 with P(map 3), the round-differential layer, sigma, P(over)) is unchanged, so with mode 0 every number is identical to before.
"""
import argparse, copy, re
import openpyxl
from openpyxl.worksheet.formula import ArrayFormula


def text(v):
    """The formula text of a cell (older templates store some Calc cells as array formulas)."""
    return v.text if isinstance(v, ArrayFormula) else v


def put(ws, coord, old, new):
    ws[coord] = ArrayFormula(coord, new) if isinstance(old, ArrayFormula) else new

SLOTS = [("V", "$G2", "W"), ("AC", "$H2", "AD"), ("AJ", "$I2", "AK")]          # (kills col, map-name col it needs, hs col)
KM = 'IFERROR(INDEX(Players!$G$2:$G${end},MATCH($F{r},Players!$A$2:$A${end},0)),"")'     # {end}: the template sizes its ranges to the slate's player count


def wrap(existing, new):
    body = existing[1:] if existing.startswith("=") else existing
    return f'=IF(Config!$B$16=1,{new},{body})'


def patch(src, dst, mode=0):
    wb = openpyxl.load_workbook(src)
    cfg, calc = wb["Config"], wb["Calc"]
    if cfg["A16"].value not in (None, "PROJ_MODE"):
        raise SystemExit(f"Config!A16 already holds {cfg['A16'].value!r}: the template changed, not patching")
    cfg["A16"], cfg["B16"] = "PROJ_MODE", mode
    cfg["C16"] = ("0 = KPR x rounds (published). 1 = career kills per map (Players 'Kills/Map'), no map names, no rounds; headshots through the overall HS%. "
                  "Backtest on 430 CS2 legs: same error and ranking as KPR x rounds; scored forward as H9.")
    for col in "ABC":                                                           # copy the look of the row above
        cfg[f"{col}16"]._style = copy.copy(cfg[f"{col}15"]._style)
    cfg.row_dimensions[16].height = cfg.row_dimensions[15].height
    ref = text(calc["O2"].value)                                                      # 'KPR all': =IFERROR(1/(1/INDEX(Players!$H$2:$H$<end>, ...
    m = re.search(r"Players!\$H\$2:\$H\$(\d+)", ref or "")
    if not m:
        raise SystemExit("could not read the Players range from Calc!O2: the template changed, not patching")
    end = int(m.group(1))
    done = 0
    for kcol, mapcol, hcol in SLOTS:
        for r in range(2, calc.max_row + 1):
            if calc[f"A{r}"].value is None:
                continue
            ko, ho = calc[f"{kcol}{r}"].value, calc[f"{hcol}{r}"].value
            k, h = text(ko), text(ho)
            if isinstance(k, str) and "Config!$B$16" in k:
                continue                                                       # already patched
            mp = mapcol.replace("2", str(r))
            put(calc, f"{kcol}{r}", ko, wrap(k, f'IF({mp}="","",{KM.format(r=r, end=end)})'))
            put(calc, f"{hcol}{r}", ho, wrap(h, f'IF(OR({kcol}{r}="",$P{r}=""),"",{kcol}{r}*$P{r})'))
            done += 1
    wb.save(dst)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--mode", type=int, default=0, choices=[0, 1])
    a = ap.parse_args()
    n = patch(a.src, a.dst, a.mode)
    print(f"{a.dst}: PROJ_MODE={a.mode}, {n} Calc cells patched; recalculate before use (python -m pipeline.recalc {a.dst})")


if __name__ == "__main__":
    main()
