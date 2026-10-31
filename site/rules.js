"use strict";
// Which legs fall under which registered play rule: a line-for-line mirror of RULES and MOBA_RULES in pipeline/evaluate.py.
// The plays frozen at import (data/plays/<slate>.json) are the record; this recomputes the same selection from the model's numbers so every row can show it.
// site/test/parity.mjs checks that it picks exactly the legs the frozen file holds. A rule judged "forward" only counts slates after its own declaration date (see Evaluation).
const Rules = (() => {
  const nn = v => v !== null && v !== undefined && !Number.isNaN(v);
  const modelSide = r => (r.po >= 0.5 ? "OVER" : "UNDER");
  const fps = r => r.title === "CS2" || r.title === "VAL";
  const list = [
    {id: "agree10", h: "H8", name: "Both models agree on a side, both lean 10+ points", side: modelSide, scope: fps,
      test: r => nn(r.po) && nn(r.poAdj) && (r.po >= 0.5) === (r.poAdj >= 0.5) && Math.min(Math.abs(r.po - 0.5), Math.abs(r.poAdj - 0.5)) >= 0.10},
    {id: "all_under", h: "H10", name: "Every leg, under", side: () => "UNDER", scope: fps, test: r => nn(r.po)},
    {id: "under_core", h: "H11", name: "Under shortlist: both models under, P(over) below 40%, line outside 20-25, PF L10 0.3-0.7, not Maps 1-3 kills", side: () => "UNDER", scope: fps,
      test: r => nn(r.po) && nn(r.poAdj) && nn(r.line) && nn(r.l10) && r.po < 0.5 && r.poAdj < 0.5 && r.po < 0.40 && !(r.line >= 20 && r.line < 25) && r.l10 >= 0.3 && r.l10 < 0.7 && r.market !== "Maps 1-3 Kills"},
    {id: "agree20", h: "H13", name: "Both models agree on a side, both lean 20+ points", side: modelSide, scope: fps,
      test: r => nn(r.po) && nn(r.poAdj) && (r.po >= 0.5) === (r.poAdj >= 0.5) && Math.min(Math.abs(r.po - 0.5), Math.abs(r.poAdj - 0.5)) >= 0.20 - 1e-9},
    {id: "l10_over", h: "H12", name: "Over where the PrizePicks last-10 hit rate is 0.8 or more", side: () => "OVER", scope: fps, test: r => nn(r.l10) && r.l10 >= 0.8},
    {id: "hs_side", h: "H15", name: "Headshot leg, the model's own side", side: modelSide, scope: fps, test: r => nn(r.po) && String(r.market || "").includes("HS")},
    {id: "moba_lean20", h: "H14", name: "MOBA: the model leans 20+ points, its own side", side: modelSide, scope: r => !fps(r), test: r => nn(r.po) && Math.abs(r.po - 0.5) >= 0.20 - 1e-9},
  ];
  // -> [{id, h, side, name}] for one row
  const of = r => list.filter(x => x.scope(r) && x.test(r)).map(x => ({id: x.id, h: x.h, side: x.side(r), name: x.name}));
  return {list, of};
})();
if (typeof module !== "undefined") module.exports = Rules;
