# Over-bias correction test (2026-10-19)

**The bias is real.** Across 599 graded CS2 legs (2026-10-16 to -19) the model called over on 54% of legs but 46% went over; projections ran 0.33 kills above what happened (0.43 on kills, 0.20 on headshots); over calls hit 47%, under calls 56%.

**Correcting it does not raise the hit rate.** Leave-one-slate-out (each correction fitted on the other three slates, applied to the held-out one; `python -m pipeline.overbias`):

| Side rule | Hit | Overs called |
|---|---|---|
| Published (projection vs line) | 299 / 597 = 50.1% | 58% |
| Shift by the mean projection error | 295 / 599 = 49.2% | 51% |
| Shift per market class (kills / HS) | 301 / 599 = 50.3% | 51% |
| Scale by actual / projection | 296 / 599 = 49.4% | 52% |
| Threshold at the actual over-rate | 306 / 598 = 51.2% | 47% |
| Shrink toward the line | 265 / 599 = 44.2% | 56% |

The corrections rebalance overs and unders (58% over calls down to about 50%) and change the hit rate by about a point either way. The standard error on 599 legs is about 2 points, so none of this is distinguishable from 50%. The shrink fit says why: realised-minus-line moves only 0.10 for each 1.0 the projection sits above the line, i.e. the projection's gap to the line carries almost no information. A bias correction fixes calibration, not skill.

**What the same data does show:** the line is set at the mean of the distribution, which is right-skewed, so the median result is below the line (mean actual − line = +0.04, median −0.5). Always taking the under hit 324 of 599 = 54.1% (interval 50-58%), against a 54.2% breakeven; by slate 61%, 49%, 49%, 57%. That is a structural (skew) effect, not a model signal, and it was found after looking at this data, so it counts only if it holds on slates after 2026-10-19.
