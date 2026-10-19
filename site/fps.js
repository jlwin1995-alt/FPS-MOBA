"use strict";
// FPS Player Model (CS2 + Valorant) — a line-for-line port of the workbook's Calc and Projections tabs.
//   per-map KPR (shrunk toward the player's overall KPR) x rounds expected on that map -> kills; HS% likewise; Maps 1-3 adds P(map 3) x map 3.
//   "adj" = the CS2 round-differential layer (HLTV conditional round margins).  Both are PAPER: no forward record yet.
// D = site/data/fps.json; cfg = D.config (+ your edits); ovr = {matchId: {maps: [m1,m2,m3], rounds: [r1,r2,r3]}}.
const ST_ = typeof require !== "undefined" ? require("./stats.js") : ST;
const FPS = (() => {
  const N = ST_.N, isNum = ST_.isNum;

  function index(D) {
    const I = {players: {}, matches: {}, hl: {}};
    for (const p of D.players) I.players[p.pid] = p;
    for (const m of D.matches) I.matches[m.id] = m;
    // HLTV_Long: SUMIFS / COUNTIFS over keys "match|side|map|stat" (stat lw = rounds lost in wins, wl = rounds won in losses)
    for (const [k, v] of Object.entries(D.hltv_long)) { const e = I.hl[k] || (I.hl[k] = {s: 0, n: 0}); e.s += N(v); e.n += 1; }
    return I;
  }
  const hl = (I, k) => I.hl[k] || {s: 0, n: 0};

  // HLTV conditional margin for one map: if A wins the map B takes (A's rounds-lost-in-wins, B's rounds-won-in-losses); falls back to the all-maps figure.
  function cond(I, id, map, who) {
    const [x, y] = who === "A" ? ["A", "B"] : ["B", "A"];
    const tryMap = mp => {
      const a = hl(I, `${id}|${x}|${mp}|lw`), b = hl(I, `${id}|${y}|${mp}|wl`), n = a.n + b.n;
      return n ? (a.s + b.s) / n : null;
    };
    const v = tryMap(map);
    return v != null ? v : tryMap("ALL");
  }
  function hltvMap(I, m, k, map) {
    const pa = m["pAm" + k];
    if (!map) return {};
    const cA = cond(I, m.id, map, "A"), cB = cond(I, m.id, map, "B");
    const src = ["A|lw", "B|wl", "B|lw", "A|wl"].reduce((t, s) => t + hl(I, `${m.id}|${s.split("|")[0]}|${map}|${s.split("|")[1]}`).n, 0);
    if (cA == null || cB == null || !isNum(pa)) return {cA, cB, src};
    const rounds = 13 + pa * cA + (1 - pa) * cB;
    return {cA, cB, src, rounds, margin: pa * (13 - cA) - (1 - pa) * (13 - cB), share: (pa * 13 + (1 - pa) * cB) / rounds};
  }

  // one player in one match: Calc row
  function calcPlayer(D, I, cfg, pid, m, st) {
    const P = I.players[pid], ms = D.mapstats[pid] || {};
    const S = cfg.SHRINK_MAPS, ref = m.title === "CS2" ? cfg.REF_ROUNDS_CS2 : cfg.REF_ROUNDS_VAL;
    const kprAll = P && P.kpr ? P.kpr : null, hsAll = P && P.hs ? P.hs : null;
    const avgRounds = P && P.kpr ? P.kills_map / P.kpr : null;
    const out = {sample: P ? N(P.maps) : 0, kprAll, hsAll, maps: st.maps, rounds: st.rounds, p3: m.p3_used, k: []};
    for (let i = 0; i < 3; i++) {
      const map = st.maps[i], r = st.rounds[i], rec = map ? ms[map] : null;
      const o = {n: 0, kills: null, hs: null, kpr: null, hsPct: null};
      if (map) {
        o.n = rec ? N(rec.n) : 0;
        const used = rec ? (rec.kpr != null ? rec.kpr : (avgRounds ? rec.kills / avgRounds : null)) : null;   // Map_Stats "KPR used"
        const raw = used ? used : kprAll;                                                                    // 1/(1/x) falls back on x = 0 or blank
        const hsRaw = hsAll == null ? null : (rec && rec.hs ? rec.hs : hsAll);
        if (raw != null) o.kpr = kprAll == null ? raw : (o.n * raw + S * kprAll) / (o.n + S);
        if (hsRaw != null) o.hsPct = (o.n * hsRaw + S * hsAll) / (o.n + S);
        if (o.kpr != null && isNum(r)) o.kills = o.kpr * r * Math.pow(r / ref, cfg.KPR_ROUND_ELASTICITY);
        if (o.kills != null && o.hsPct != null) o.hs = o.kills * o.hsPct;
        if (cfg.PROJ_MODE === 1) {                                       // workbook switch (Config PROJ_MODE): career kills per map, no map names, no rounds; HS through his overall HS%
          o.kills = P && isNum(P.kills_map) && P.kills_map ? P.kills_map : null;
          o.hs = o.kills != null && hsAll != null ? o.kills * hsAll : null;
        }
      }
      out.k.push(o);
    }
    const [a, b, c] = out.k;
    out.K1 = a.kills; out.K2 = b.kills; out.K3 = c.kills;
    out.K12 = N(a.kills) + N(b.kills); out.K13 = out.K12 + N(m.p3_used) * N(c.kills);
    out.H1 = a.hs; out.H2 = b.hs; out.H3 = c.hs;
    out.H12 = a.hs == null ? null : N(a.hs) + N(b.hs);
    out.H13 = out.H12 == null ? null : out.H12 + N(m.p3_used) * N(c.hs);
    out.hsPct12 = out.H12 != null && out.K12 ? out.H12 / out.K12 : null;
    // flags
    const f = [];
    if (out.sample < cfg.THIN_SAMPLE_MAPS) f.push(`thin sample (${out.sample} maps)`);
    if (st.maps[0] && a.n === 0) f.push("M1 unplayed→overall KPR");
    if (st.maps[1] && b.n === 0) f.push("M2 unplayed→overall KPR");
    if (kprAll == null) f.push("no PickFinder stats");
    out.flags = f;
    // round-differential layer
    const side = P && P.team === m.tag_a ? "A" : P && P.team === m.tag_b ? "B" : "";
    out.side = side;
    out.histShare = side ? (side === "A" ? m.hist_a : m.hist_b) : null;
    out.mult = [0, 1, 2].map(i => {
      const h = st.hltv[i], sh = h && isNum(h.share) && side ? (side === "A" ? h.share : 1 - h.share) : null;
      const hs = out.histShare;
      if (sh == null || !isNum(hs)) return 1;
      return Math.pow((cfg.KILLS_PER_ROUND_WON * sh + cfg.KILLS_PER_ROUND_LOST * (1 - sh)) / (cfg.KILLS_PER_ROUND_WON * hs + cfg.KILLS_PER_ROUND_LOST * (1 - hs)), cfg.DIFF_WEIGHT);
    });
    const [m1, m2, m3] = out.mult;
    const ad = (x, mu) => x == null ? null : x * mu;
    out.adj = {K1: ad(a.kills, m1), K2: ad(b.kills, m2), K3: ad(c.kills, m3), H1: ad(a.hs, m1), H2: ad(b.hs, m2), H3: ad(c.hs, m3)};
    out.adj.K12 = N(out.adj.K1) + N(out.adj.K2); out.adj.K13 = out.adj.K12 + N(m.p3_used) * N(out.adj.K3);
    out.adj.H12 = out.adj.H1 == null ? null : N(out.adj.H1) + N(out.adj.H2);
    out.adj.H13 = out.adj.H12 == null ? null : out.adj.H12 + N(m.p3_used) * N(out.adj.H3);
    out.diffMult12 = out.K12 ? out.adj.K12 / out.K12 : 1;
    return out;
  }

  // the state of a match: the workbook's defaults overlaid with the user's edits
  function matchState(I, D, id, ovr) {
    const m = I.matches[id], o = (ovr && ovr[id]) || {};
    const st = {maps: [...(o.maps || m.default.maps)].map(x => x || null), rounds: [...(o.rounds || m.default.rounds)]};
    st.hltv = [0, 1, 2].map(i => hltvMap(I, m, i + 1, st.maps[i]));
    return st;
  }

  function calcAll(D, cfg, ovr) {
    const I = index(D), cache = {}, states = {};
    const legs = D.legs.map(g => {
      const m = I.matches[g.match];
      if (!m) return {...g, out: null};
      const st = states[g.match] || (states[g.match] = matchState(I, D, g.match, ovr));
      const c = cache[g.key] || (cache[g.key] = calcPlayer(D, I, cfg, g.key.split("|")[0], m, st));
      const code = g.code, isH = code[0] === "H";
      const proj = c[code], adj = c.adj[code];
      const ap = c.hsPct12 == null ? 0 : c.hsPct12;
      const sig = x => x == null ? null : isH ? Math.sqrt(x * (ap * cfg.KILLS_DISPERSION + 1 - ap)) : Math.sqrt(x * cfg.KILLS_DISPERSION);
      const r = {proj, sigma: sig(proj), proj_adj: adj, sigma_adj: sig(adj), diff: proj ? adj / proj : null};
      // SHADOW "kills per map" projection (see pipeline/kpm.py): career kills/map x the maps that count; no map names, no rounds
      const Pl = I.players[g.key.split("|")[0]], nm = {K1: 1, H1: 1, K12: 2, H12: 2, K13: 2 + N(m.p3_used), H13: 2 + N(m.p3_used)}[code];
      if (Pl && isNum(Pl.kills_map) && Pl.kills_map && nm != null && !(isH && !isNum(Pl.hs))) {
        const kp = Pl.kills_map * nm * (isH ? Pl.hs : 1), ks = Math.sqrt(kp * (isH ? Pl.hs * cfg.KILLS_DISPERSION + 1 - Pl.hs : cfg.KILLS_DISPERSION)), kq = ST_.over_under(g.line, kp, ks);
        r.proj_kpm = kp; if (kq) r.p_over_kpm = kq.po;
      }
      const p = ST_.over_under(g.line, proj, r.sigma), q = ST_.over_under(g.line, adj, r.sigma_adj);
      Object.assign(r, p ? {p_over: p.po, p_under: p.pu, p_push: p.push} : {}, q ? {p_over_adj: q.po, p_under_adj: q.pu} : {});
      r.side = p ? ST_.side(p.po, p.pu, cfg.EDGE_MIN) : ""; r.side_adj = q ? ST_.side(q.po, q.pu, cfg.EDGE_MIN) : "";
      r.maps = c.maps.filter(Boolean).slice(0, code.endsWith("1") ? 1 : code.endsWith("12") ? 2 : 2).join(" / ");
      r.rounds = c.rounds.map(x => isNum(x) ? x.toFixed(1) : "").slice(0, 2).join(" / ");
      return {...g, out: r, calc: c, state: st};
    });
    return {legs, I, states, calcs: cache};
  }
  return {index, calcAll, calcPlayer, matchState, hltvMap};
})();
if (typeof module !== "undefined") module.exports = FPS;
