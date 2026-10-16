"use strict";
// Browser twin of pipeline/prob.py (site/test/parity.mjs keeps them equal): the projection is fixed by the pipeline; overrides and lines are applied here.
const EM = {
  normCdf(z) {                                   // Abramowitz-Stegun 7.1.26 via erf: |error| < 1.5e-7
    const x = Math.abs(z) / Math.SQRT2, t = 1 / (1 + 0.3275911 * x);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return z >= 0 ? 0.5 * (1 + y) : 0.5 * (1 - y);
  },
  sigma(meta, stat, m, sd) { return Math.max(sd || 0, meta.sd_floor[stat], meta.sd_rel_floor * Math.abs(m)); },
  // [P(over), P(under)], push renormalised away (kills are integers; a whole-number line has a push band)
  sides(line, m, sd) {
    line = +line;
    let o, u;
    if (Number.isInteger(line)) { o = 1 - EM.normCdf((line + 0.5 - m) / sd); u = EM.normCdf((line - 0.5 - m) / sd); }
    else { o = 1 - EM.normCdf((line - m) / sd); u = 1 - o; }
    const t = o + u;
    return t > 0 ? [o / t, u / t] : [0.5, 0.5];
  },
  implied: d => d > 1 ? 1 / d : null,
  devig2(a, b) { const x = EM.implied(a), y = EM.implied(b); if (x == null || y == null) return [null, null]; const t = x + y; return [x / t, y / t]; },
};
if (typeof module !== "undefined") module.exports = EM;
