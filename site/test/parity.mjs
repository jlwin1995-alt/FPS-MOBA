// The browser model must reproduce the numbers the workbooks computed themselves: node site/test/parity.mjs
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
const req = createRequire(import.meta.url);
const FPS = req("../fps.js"), MOBA = req("../moba.js"), ST = req("../stats.js");
const J = f => JSON.parse(readFileSync(new URL(f, import.meta.url)));
const fps = J("../data/fps.json"), moba = J("../data/moba.json"), exp = J("./expected.json");

let bad = 0, checked = 0, worst = 0;
function cmp(tag, got, want, tol = 1e-6) {
  if (want == null || want === "") { if (got != null && got !== "" && typeof got === "number" && !Number.isNaN(got) && tag.includes("!")) { /* workbook blank, we have a value */ } return; }
  checked++;
  const d = typeof want === "number" ? Math.abs((got ?? NaN) - want) : (got === want ? 0 : Infinity);
  worst = Math.max(worst, Number.isFinite(d) ? d : 0);
  if (!(d <= tol)) { bad++; if (bad <= 15) console.error(`MISMATCH ${tag}: got ${got}, workbook ${want}`); }
}
// normal CDF against known values
cmp("cdf(0)", ST.normCdf(0), 0.5, 1e-15); cmp("cdf(1.96)", ST.normCdf(1.96), 0.9750021048517795, 1e-12); cmp("cdf(-3)", ST.normCdf(-3), 0.0013498980316301, 1e-12);

const F = FPS.calcAll(fps, fps.config, {});
F.legs.forEach((g, i) => {
  const e = exp.fps[i], o = g.out, t = `FPS ${g.key} ${g.code}`;
  if (g.key !== e.key || g.code !== e.code) { bad++; console.error("row order mismatch", i); return; }
  cmp(t + " proj", o.proj, e.proj); cmp(t + " sigma", o.sigma, e.sigma); cmp(t + " p_over", o.p_over, e.p_over); cmp(t + " p_under", o.p_under, e.p_under);
  cmp(t + " p_push", o.p_push, e.p_push); cmp(t + " side", o.side, e.side);
  cmp(t + " proj_adj", o.proj_adj, e.proj_adj); cmp(t + " sigma_adj", o.sigma_adj, e.sigma_adj); cmp(t + " p_over_adj", o.p_over_adj, e.p_over_adj); cmp(t + " p_under_adj", o.p_under_adj, e.p_under_adj);
  cmp(t + " side_adj", o.side_adj, e.side_adj); cmp(t + " mult", o.diff, e.mult);
  if ((e.proj == null || e.proj === "") && o.proj != null) { bad++; console.error(`${t}: workbook has no projection, we do`); }
});
const Mo = MOBA.calcAll(moba, moba.config, {});
Mo.legs.forEach((g, i) => {
  const e = exp.moba[i], o = g.out, t = `MOBA ${g.key} ${g.code}`;
  cmp(t + " proj", o.proj, e.proj); cmp(t + " sigma", o.sigma, e.sigma); cmp(t + " p_over", o.p_over, e.p_over); cmp(t + " p_under", o.p_under, e.p_under);
  cmp(t + " p_push", o.p_push, e.p_push); cmp(t + " side", o.side, e.side); cmp(t + " naive", o.naive, e.naive); cmp(t + " p_over_naive", o.p_over_naive, e.p_over_naive);
});
// The rules the Projections tab shows per leg must be exactly the legs frozen in data/plays/<slate>.json at import.
const RULES = req("../rules.js");
let planned = 0;
try {
  const slate = J("../data/meta.json").slate, plays = J(`../../data/plays/${slate}.json`);
  const key = (m, p, k) => `${m}|${p}|${k}`;
  const rows = [
    ...F.legs.map(g => ({k: key(g.match, g.player, g.market), title: g.title, po: g.out.p_over, poAdj: g.out.p_over_adj, line: g.line, market: g.market, l10: g.l10})),
    ...Mo.legs.map(g => ({k: key(g.match, g.player, g.market), title: g.match.startsWith("DOTA") ? "DOTA" : "LOL", po: g.out.p_over, poAdj: null, line: g.line, market: g.market, l10: g.l10})),
  ];
  for (const rule of RULES.list) {
    const frozen = (plays.rules && plays.rules[rule.id]) || (plays.moba_rules && plays.moba_rules[rule.id]);
    if (!frozen) continue;                                             // a slate frozen before this rule existed
    const want = new Map(frozen.legs.map(l => [key(l.match, l.player, l.market), l.side]));
    const got = new Map(rows.filter(r => rule.scope(r) && rule.test(r)).map(r => [r.k, rule.side(r)]));
    planned += want.size;
    for (const [k, sd] of want) if (got.get(k) !== sd) { bad++; if (bad <= 15) console.error(`RULE ${rule.id}: frozen ${sd} for ${k}, site shows ${got.get(k) ?? "nothing"}`); }
    for (const k of got.keys()) if (!want.has(k)) { bad++; if (bad <= 15) console.error(`RULE ${rule.id}: site shows ${k}, not in the frozen plays`); }
  }
} catch (e) { if (e.code !== "ENOENT") throw e; }
console.log(`parity: ${F.legs.length} FPS legs + ${Mo.legs.length} MOBA legs, ${checked} values compared, worst numeric difference ${worst.toExponential(2)}, ${bad} mismatches, ${planned} frozen play legs matched against the site's rule badges`);
process.exit(bad ? 1 : 0);
