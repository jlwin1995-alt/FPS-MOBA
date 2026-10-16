"use strict";
// MOBA Player Model (LoL + Dota 2) — a line-for-line port of the workbook's Calc and Projections tabs.
//   Players score ~2x the kills in map wins as in losses.  k_win = K·r / (q·r + 1 − q), k_loss = K / (q·r + 1 − q) reproduce K exactly at his own win rate q;
//   map kills = env x (P(win)·k_win + (1 − P(win))·k_loss); the spread adds the win/loss mixture variance.  PAPER: never scored forward.
// D = site/data/moba.json; cfg = D.config (+ your edits); ovr = {matchId: {pm: [p1,p2,p3], p2, p3, env}}.
const ST_M = typeof require !== "undefined" ? require("./stats.js") : ST;
const MOBA = (() => {
  const N = ST_M.N, isNum = ST_M.isNum;
  const state = (m, ovr) => {
    const o = (ovr && ovr[m.id]) || {}, d = m.default;
    return {pm: o.pm || d.pm, p2: o.p2 != null ? o.p2 : d.p2, p3: o.p3 != null ? o.p3 : d.p3, env: o.env != null ? o.env : d.env};
  };
  function calcAll(D, cfg, ovr) {
    const P = {}, M = {}, cache = {};
    for (const p of D.players) P[p.pid] = p;
    for (const m of D.matches) M[m.id] = m;
    const legs = D.legs.map(g => {
      const m = M[g.match], pid = g.key.split("|")[0], pl = P[pid];
      if (!m) return {...g, out: null};
      const dota = m.id.startsWith("DOTA"), ratio = dota ? cfg.WL_RATIO_DOTA : cfg.WL_RATIO_LOL, disp = dota ? cfg.KILLS_DISPERSION_DOTA : cfg.KILLS_DISPERSION_LOL;
      const st = state(m, ovr), side = pl && pl.team === m.tag_a ? "A" : pl && pl.team === m.tag_b ? "B" : "";
      const q = pl ? pl.q : null, K = pl ? pl.k : null;
      const c = {sample: pl ? N(pl.maps) : 0, q, K, env: st.env, side};
      if (K != null && q != null) { const den = q * ratio + 1 - q; c.kwin = K * ratio / den; c.kloss = K / den; }
      const played = [1, N(st.p2), N(st.p3)];
      c.maps = [0, 1, 2].map(i => {
        const pm = st.pm[i], pw = pm == null || !side ? null : side === "A" ? pm : 1 - pm;
        if (pw == null || c.kwin == null) return {pw, played: played[i]};
        const mean = c.env * (pw * c.kwin + (1 - pw) * c.kloss);
        return {pw, played: played[i], mean, v: disp * mean + c.env * c.env * pw * (1 - pw) * Math.pow(c.kwin - c.kloss, 2)};
      });
      const [a, b, d] = c.maps, has = a.mean != null;
      const mix = x => x.played * x.v + x.played * (1 - x.played) * x.mean * x.mean;           // played-or-not mixture, as in the sheet
      c.K1 = has ? a.mean : null; c.K1v = has ? a.v : null;
      c.K12 = has ? N(a.played) * N(a.mean) + N(b.played) * N(b.mean) : null;
      c.K12v = has ? mix({...a, v: N(a.v), mean: N(a.mean)}) + mix({...b, v: N(b.v), mean: N(b.mean)}) : null;
      c.K13 = has ? c.K12 + N(d.played) * N(d.mean) : null;
      c.K13v = has ? c.K12v + mix({...d, v: N(d.v), mean: N(d.mean)}) : null;
      c.naive = K == null ? {} : {K1: K * c.env, K12: K * c.env * (1 + N(st.p2)), K13: K * c.env * (1 + N(st.p2) + N(st.p3))};
      c.seriesCode = m.bo === 3 ? "K12" : "K13";
      const f = [];
      if (c.sample < cfg.THIN_SAMPLE_MAPS) f.push(`thin sample (${c.sample} maps)`);
      if (K == null) f.push("no PickFinder stats");
      if (pl && isNum(pl.with_team) && pl.with_team < 0.5) f.push(`new roster: ${Math.round(pl.with_team * 100)}% of his recent games with these teammates`);
      c.flags = f;
      const code = g.code, proj = c[code], sigma = proj == null ? null : Math.sqrt(c[code + "v"]);
      const r = {proj, sigma, naive: c.naive[code], q, pwin1: a.pw, flags: f};
      const p = ST_M.over_under(g.line, proj, sigma);
      if (p) { Object.assign(r, {p_over: p.po, p_under: p.pu, p_push: p.push}); r.side = ST_M.side(p.po, p.pu, cfg.EDGE_MIN); } else r.side = "";
      if (isNum(g.line) && r.naive != null && p && N(sigma) > 0) r.p_over_naive = 1 - ST_M.normDist(Math.floor(g.line) + 0.5, r.naive, sigma * Math.sqrt(r.naive / proj));
      return {...g, out: r, calc: c, state: st};
    });
    return {legs, M, P};
  }
  return {calcAll, state};
})();
if (typeof module !== "undefined") module.exports = MOBA;
