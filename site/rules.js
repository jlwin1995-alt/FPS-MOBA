"use strict";
// Which legs fall under which registered play rule: a line-for-line mirror of RULES and MOBA_RULES in pipeline/evaluate.py.
// The plays frozen at import (data/plays/<slate>.json) are the record; this recomputes the same selection from the model's numbers so every row can show it.
// site/test/parity.mjs checks that it picks exactly the legs the frozen file holds. A rule judged "forward" only counts slates after its own declaration date (see Evaluation).
const Rules = (() => {
  const nn = v => v !== null && v !== undefined && !Number.isNaN(v);
  const modelSide = r => (r.po >= 0.5 ? "OVER" : "UNDER");
  const fps = r => r.title === "CS2" || r.title === "VAL";
  // the Log (and so the frozen plays) holds P(over) to 4 decimals; the tests run on those, so a lean of exactly 10 points is decided the same way here
  const q = v => (nn(v) ? Math.round(v * 1e4) / 1e4 : v);
  const view = r => ({...r, po: q(r.po), poAdj: q(r.poAdj)});
  const raw = [
    {id: "agree10", h: "H8", name: "Both models agree on a side, both lean 10+ points", side: modelSide, scope: fps,
      test: r => nn(r.po) && nn(r.poAdj) && (r.po >= 0.5) === (r.poAdj >= 0.5) && Math.min(Math.abs(r.po - 0.5), Math.abs(r.poAdj - 0.5)) >= 0.10},
    {id: "all_under", h: "H10", name: "Every leg, under", side: () => "UNDER", scope: fps, test: r => nn(r.po), pill: false},   // still a registered rule (the parity check covers it), but it is every leg, so it gets no badge
    {id: "under_core", h: "H11", name: "Under shortlist: both models under, P(over) below 40%, line outside 20-25, PF L10 0.3-0.7, not Maps 1-3 kills", side: () => "UNDER", scope: fps,
      test: r => nn(r.po) && nn(r.poAdj) && nn(r.line) && nn(r.l10) && r.po < 0.5 && r.poAdj < 0.5 && r.po < 0.40 && !(r.line >= 20 && r.line < 25) && r.l10 >= 0.3 && r.l10 < 0.7 && r.market !== "Maps 1-3 Kills"},
    {id: "agree20", h: "H13", name: "Both models agree on a side, both lean 20+ points", side: modelSide, scope: fps,
      test: r => nn(r.po) && nn(r.poAdj) && (r.po >= 0.5) === (r.poAdj >= 0.5) && Math.min(Math.abs(r.po - 0.5), Math.abs(r.poAdj - 0.5)) >= 0.20 - 1e-9},
    {id: "l10_over", h: "H12", name: "Over where the PrizePicks last-10 hit rate is 0.8 or more", side: () => "OVER", scope: fps, test: r => nn(r.l10) && r.l10 >= 0.8},
    {id: "hs_side", h: "H15", name: "Headshot leg, the model's own side", side: modelSide, scope: fps, test: r => nn(r.po) && String(r.market || "").includes("HS")},
    {id: "l10_hs_over", h: "H16", name: "Headshot over: the model leans over and the PrizePicks last-10 hit rate is 0.8 or more", side: () => "OVER", scope: fps, test: r => nn(r.po) && r.po >= 0.5 && String(r.market || "").includes("HS") && nn(r.l10) && r.l10 >= 0.8},
    {id: "lean25_l10_over", h: "H17", name: "Over: the model leans over 25+ points, both models agree on over, and the PrizePicks last-10 hit rate is 0.8 or more", side: () => "OVER", scope: fps,
      test: r => nn(r.po) && nn(r.poAdj) && nn(r.l10) && r.po >= 0.75 - 1e-9 && r.poAdj >= 0.5 && r.l10 >= 0.8},
    {id: "moba_lean20", h: "H14", name: "MOBA: the model leans 20+ points, its own side", side: modelSide, scope: r => !fps(r), test: r => nn(r.po) && Math.abs(r.po - 0.5) >= 0.20 - 1e-9},
  ];

  // H18, the daily top-12 shortlist: a slate-level rule, a line-for-line mirror of top12() in pipeline/evaluate.py. Needs the whole board, so it is computed once per list of rows (see top12 below)
  const TOP12_CELLS = {"agree10": {"OVER": {"Kills": 0.5233, "Headshots": 0.5176}, "UNDER": {"Kills": 0.5417, "Headshots": 0.5424}}, "under_core": {"OVER": {"Kills": 0.5243, "Headshots": 0.5248}, "UNDER": {"Kills": 0.5243, "Headshots": 0.5248}}, "l10_over": {"OVER": {"Kills": 0.5043, "Headshots": 0.5612}, "UNDER": {"Kills": 0.5043, "Headshots": 0.5612}}, "agree20": {"OVER": {"Kills": 0.4667, "Headshots": 0.8182}, "UNDER": {"Kills": 0.5439, "Headshots": 0.4694}}, "hs_side": {"OVER": {"Kills": 0.5092, "Headshots": 0.5092}, "UNDER": {"Kills": 0.4926, "Headshots": 0.4926}}, "l10_hs_over": {"OVER": {"Kills": 0.8, "Headshots": 0.8}, "UNDER": {"Kills": 0.8, "Headshots": 0.8}}, "lean25_l10_over": {"OVER": {"Kills": 0.6667, "Headshots": 1.0}, "UNDER": {"Kills": 0.6667, "Headshots": 1.0}}};
  const TOP12_NAME = "Daily top-12 shortlist: H8/H16 legs where every rule agrees on the side, lean 15+, ranked by a fixed score, 2 per match, 1 per player";
  const top12 = rows => {
    const cand = [];
    for (const r of rows) {
      const v = view(r);
      if (!fps(r) || !nn(v.po) || !nn(v.poAdj) || !r.market) continue;
      const rs = list.filter(x => x.scope(r) && x.test(r)).filter(x => x.id !== "all_under");
      const sides = new Set(rs.map(x => x.side(r)));
      if (sides.size !== 1 || !rs.some(x => x.id === "agree10" || x.id === "l10_hs_over")) continue;
      const side = [...sides][0], lean = Math.abs(v.po - 0.5) * 100;
      if ((v.poAdj >= 0.5) !== (v.po >= 0.5) || lean < 15 - 1e-9) continue;
      const kind = String(r.market).includes("HS") ? "Headshots" : "Kills";
      cand.push({r, side, lean, score: lean + 100 * rs.reduce((a, x) => a + TOP12_CELLS[x.id][side][kind] - 0.5, 0)});
    }
    const cmp = (a, b) => b.score - a.score || (a.r.match < b.r.match ? -1 : a.r.match > b.r.match ? 1 : 0) || (a.r.player < b.r.player ? -1 : a.r.player > b.r.player ? 1 : 0) || (a.r.market < b.r.market ? -1 : a.r.market > b.r.market ? 1 : 0);
    cand.sort(cmp);
    const out = [], per = {}, who = new Set();
    for (const c of cand) {
      if ((per[c.r.match] || 0) >= 2 || who.has(c.r.player)) continue;
      out.push(c); per[c.r.match] = (per[c.r.match] || 0) + 1; who.add(c.r.player);
      if (out.length === 12) break;
    }
    return out;
  };
  // -> [{id, h, side, name}] for one row
  const list = raw.map(x => ({...x, test: r => x.test(view(r)), side: r => x.side(view(r))}));
  const perLeg = list.filter(x => x.pill !== false);                                       // the rules decided leg by leg
  const shown = [...perLeg, {id: "top12", h: "H18", name: TOP12_NAME}];                   // what the chips and filter list (H18 is added to rows by the slate-level pass)
  const of = r => perLeg.filter(x => x.scope(r) && x.test(r)).map(x => ({id: x.id, h: x.h, side: x.side(r), name: x.name}));
  return {list, shown, of, top12, TOP12_NAME};
})();
if (typeof module !== "undefined") module.exports = Rules;
