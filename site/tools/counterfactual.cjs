// What would the FPS model have projected with the maps and rounds that were actually played?   node site/tools/counterfactual.cjs <fps.json> <overrides.json>
// overrides.json: {matchId: {maps: [m1, m2, m3], rounds: [r1, r2, r3]}}. Prints per-leg projections (as published and with the overrides) and per-match assumptions as JSON.
// Uses the site's own model (site/fps.js), so the evaluation never has a second implementation of it.
const FPS = require("../fps.js"), fs = require("fs");
const [, , fpsPath, ovrPath] = process.argv;
const fps = JSON.parse(fs.readFileSync(fpsPath, "utf8")), ovr = JSON.parse(fs.readFileSync(ovrPath, "utf8"));
const base = FPS.calcAll(fps, fps.config, {}), orc = FPS.calcAll(fps, fps.config, ovr);
const legs = {}, matches = {};
base.legs.forEach((g, i) => {
  const o = orc.legs[i];
  legs[`${g.match}|${g.player}|${g.market}`] = {proj: g.out.proj, p_over: g.out.p_over, proj_or: o.out.proj, p_over_or: o.out.p_over, n1: g.calc.k[0].n, n2: g.calc.k[1].n, sample: g.calc.sample, counterfactual: !!ovr[g.match]};
  if (!matches[g.match]) matches[g.match] = {used_maps: g.calc.maps, used_rounds: g.calc.rounds, or_maps: o.calc.maps, or_rounds: o.calc.rounds};
});
process.stdout.write(JSON.stringify({legs, matches}));
