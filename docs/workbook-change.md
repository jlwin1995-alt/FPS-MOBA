# Workbook change: kills per map (PROJ_MODE)

**Why.** KPR × expected rounds ties every projection to a rounds guess, and per-map KPR to map names, which the vetoes get wrong (4 of 24 maps right on 2026-10-17, 1 of 14 earlier). On 430 settled CS2 legs (2026-10-16 to -18), career **kills per map × the maps that count** has the same error and ranking as the published projection (MAE 4.41 vs 4.47, AUC 0.549 vs 0.551, side hit 52.9% vs 53.7%), so the extra machinery is not earning its keep. Neither beats the posted line's own error (4.43). This is a simplification, not an improvement.

**What it does.** Map 1 = Players "Kills/Map"; Maps 1-2 = 2 ×; Maps 1-3 = (2 + P(map 3)) ×; headshots = that × the player's overall HS%. Spread, probabilities and the round-differential layer are unchanged.

## Apply

```
python -m pipeline.patch_workbook in.xlsx out.xlsx --mode 0      # adds the switch, numbers unchanged
python -m pipeline.recalc out.xlsx
```

Set `Config!B16` (`PROJ_MODE`) to 1 for kills per map, 0 for KPR × rounds. The patch only touches Config row 16 and Calc columns V, W, AC, AD, AJ, AK (each becomes `=IF(Config!$B$16=1, kills-per-map version, existing formula)`); it works on both template generations (plain and array formulas) and is idempotent. `test_patch_workbook` checks mode 0 reproduces the workbook and mode 1 equals `pipeline/kpm.py`; the browser port follows the switch (`cfg.PROJ_MODE`) and passes the parity test on a mode-1 workbook.

To make it permanent in your template instead, copy the same formulas by hand: for map slot 1, `Calc!V2 = IF($G2="","",IFERROR(INDEX(Players!$G$2:$G$<last>,MATCH($F2,Players!$A$2:$A$<last>,0)),""))` and `Calc!W2 = IF(OR(V2="",$P2=""),"",V2*$P2)`; slots 2 and 3 are the same with `$H2`/`AC`/`AD` and `$I2`/`AJ`/`AK`.

## Not switched on yet

The shadow version is already logged beside every published projection (`Proj KPM`, `P(over) KPM`, on the Projections tab and in the Log), so the two are scored side by side without changing the published number. Hypothesis **H9** (AUC of kills per map minus AUC of KPR × rounds, > 0) counts slates after 2026-10-18. Turn `PROJ_MODE` on when you decide the simpler model is the one to publish; do not switch it and then judge the result on the same slates.

## Rounds

With `PROJ_MODE = 1` no rounds assumption feeds the projection. The rounds-bias check stays in the Scorecard (played vs assumed vs the long-run mean of 21.96 over 1,199 CS2 maps, and the share of maps over 21.5, 49% in the history and in the market). The assumed 21.4-21.6 sits about 0.5 below the mean (right-skewed by overtime), which only matters while `PROJ_MODE = 0`.
