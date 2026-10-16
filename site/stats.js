"use strict";
// Shared maths. normCdf is Hart's double-precision algorithm (West 2005), good to ~1e-15, so it matches the sheet's NORMDIST.
const ST = {
  normCdf(x) {
    const z = Math.abs(x);
    let c;
    if (z > 37) c = 0;
    else {
      const e = Math.exp(-z * z / 2);
      if (z < 7.07106781186547) {
        let n = 3.52624965998911e-2 * z + 0.700383064443688;
        n = n * z + 6.37396220353165; n = n * z + 33.912866078383; n = n * z + 112.079291497871; n = n * z + 221.213596169931; n = n * z + 220.206867912376;
        let d = 8.83883476483184e-2 * z + 1.75566716318264;
        d = d * z + 16.064177579207; d = d * z + 86.7807322029461; d = d * z + 296.564248779674; d = d * z + 637.333633378831; d = d * z + 793.826512519948; d = d * z + 440.413735824752;
        c = e * n / d;
      } else {
        let b = z + 0.65; b = z + 4 / b; b = z + 3 / b; b = z + 2 / b; b = z + 1 / b;
        c = e / b / 2.506628274631;
      }
    }
    return x > 0 ? 1 - c : c;
  },
  normDist: (x, mean, sd) => ST.normCdf((x - mean) / sd),
  N: x => typeof x === "number" && !Number.isNaN(x) ? x : 0,                 // the sheet's N(): blanks and text count as 0
  isNum: x => typeof x === "number" && !Number.isNaN(x),
  // P(over), P(under), P(push) for a line given a normal projection: a whole-number line keeps its push probability separate (continuity-corrected)
  over_under(line, mean, sd) {
    if (!ST.isNum(line) || !ST.isNum(mean) || !(ST.N(sd) > 0)) return null;
    const po = 1 - ST.normDist(Math.floor(line) + 0.5, mean, sd), pu = ST.normDist(Math.ceil(line) - 0.5, mean, sd);
    return {po, pu, push: Math.max(0, 1 - po - pu)};
  },
  side: (po, pu, edge) => po == null ? "" : po >= 0.5 + edge ? "OVER" : pu >= 0.5 + edge ? "UNDER" : "—",
};
if (typeof module !== "undefined") module.exports = ST;
