"use strict";
const TABS = ["Projections", "Board", "Matches", "Intel", "Log", "Scorecard", "Data", "Config", "Methodology"];
const D = {logs: {}};
const F = {q: "", title: "", market: "", match: "", side: "", flagged: false, rule: false, slate: "", bmatch: "", imatch: ""};
let CFGO = store.get("cfg", {fps: {}, moba: {}});                // your edits to the Config constants only
let OVR = store.get("ovr", {fps: {}, moba: {}});                 // your edits to Matches: {kind: {matchId: {...}}}
let ACT = store.get("act", {});                                  // Actuals you typed on this device
let V = 0, MEMO = null;
const view = () => document.getElementById("view");
const cfg = k => ({...D[k].config, ...CFGO[k]});
const pct1 = x => x == null || Number.isNaN(x) ? "" : (x * 100).toFixed(1) + "%";
const pct0 = x => x == null || Number.isNaN(x) ? "" : Math.round(x * 100) + "%";
const bump = () => { V++; MEMO = null; };

// ---------- the models, run in the browser on the workbook's own inputs + your edits ----------
function compute() {
  if (MEMO) return MEMO;
  const f = FPS.calcAll(D.fps, cfg("fps"), OVR.fps), m = MOBA.calcAll(D.moba, cfg("moba"), OVR.moba);
  const rows = [];
  for (const g of f.legs) rows.push(norm("FPS", g, g.title));
  for (const g of m.legs) rows.push(norm("MOBA", g, g.match.startsWith("DOTA") ? "DOTA" : "LOL"));
  return MEMO = {f, m, rows};
}
function norm(kind, g, title) {
  const o = g.out || {};
  return {id: `${kind}|${g.key}|${g.code}`, kind, title, match: g.match, key: g.key, code: g.code, player: g.player, team: g.team, market: g.market, line: g.line, tp: g.tp,
    avg10: g.avg10, l5: g.l5, l10: g.l10, l15: g.l15, h2h: g.h2h, streak: g.streak, proj: o.proj, adj: o.proj_adj, naive: o.naive, sigma: o.sigma, po: o.p_over, pu: o.p_under, pp: o.p_push,
    poAdj: o.p_over_adj, side: o.side || "", sideAdj: o.side_adj || "", kpm: o.proj_kpm, poKpm: o.p_over_kpm, poNaive: o.p_over_naive, maps: o.maps, rounds: o.rounds, diff: o.diff, q: o.q,
    flags: kind === "FPS" ? (g.calc ? g.calc.flags : []) : (o.flags || []), exact: g.exact};
}
const sidePill = (side, p) => side && side !== "—" ? `<span class="pill ${side === "OVER" ? "lean-strong" : "lean-lean"}" title="PAPER: an ordering, not an edge, until the Log says otherwise">${side} ${pct0(side === "OVER" ? p : 1 - p)}</span>` : `<span class="mut">—</span>`;
const flagPills = fl => (fl || []).map(t => `<span class="pill q" title="${esc(t)}">${esc(t.length > 26 ? t.slice(0, 24) + "…" : t)}</span>`).join(" ");

// ---------- filters ----------
const sel = (id, label, opts, cur) => `<label>${label} <select id="${id}">${opts.map(([v, t]) => `<option value="${esc(v)}" ${cur === v ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
const MARKETS = ["Map 1 Kills", "Map 1 HS", "Maps 1-2 Kills", "Maps 1-2 HS", "Maps 1-3 Kills"];
function filters(extra = "") {
  return `<div class="bar"><input id="q" placeholder="Search player / team / match" value="${esc(F.q)}">
    ${sel("title", "Title", [["", "All"], ["CS2", "CS2"], ["VAL", "Valorant"], ["LOL", "LoL"], ["DOTA", "Dota 2"]], F.title)}
    ${sel("market", "Market", [["", "All"], ...MARKETS.map(m => [m, m])], F.market)}${extra}</div>`;
}
// play rule "agree10": the base and the round-differential models call the same side and both lean at least 10 points (declared before 2026-10-18; mirrors pipeline/evaluate.py)
const isPlay = r => r.po != null && r.poAdj != null && (r.po >= 0.5) === (r.poAdj >= 0.5) && Math.min(Math.abs(r.po - 0.5), Math.abs(r.poAdj - 0.5)) >= 0.10;
const passes = r => (!F.rule || isPlay(r)) && (!F.title || r.title === F.title) && (!F.market || r.market === F.market) && (!F.match || r.match === F.match) &&
  (!F.side || (F.side === "any" ? r.side === "OVER" || r.side === "UNDER" : r.side === F.side)) && (!F.flagged || r.flags.length) &&
  (!F.q.trim() || (r.player + " " + r.team + " " + r.match).toLowerCase().includes(F.q.trim().toLowerCase()));
document.addEventListener("input", e => { if (e.target.id === "q") { F.q = e.target.value; render(true, "q"); } });
document.addEventListener("change", e => {
  const t = e.target, id = t.id;
  if (["title", "market", "match", "side", "slate", "bmatch", "imatch"].includes(id)) { F[id] = t.value; render(); }
  else if (id === "flagged") { F.flagged = t.checked; render(); }
  else if (id === "rule") { F.rule = t.checked; render(); }
  else if (t.dataset.cfg) {                                        // Config constant
    const [k, name] = t.dataset.cfg.split(":"), v = parseFloat(t.value);
    if (Number.isNaN(v) || v === D[k].config[name]) delete CFGO[k][name]; else CFGO[k][name] = v;
    store.set("cfg", CFGO); bump(); render(true);
  } else if (t.dataset.mo) {                                       // Matches edit
    const kind = t.dataset.mo, mid = t.dataset.id, f = t.dataset.f, m = D[kind].matches.find(x => x.id === mid), o = OVR[kind][mid] || (OVR[kind][mid] = {});
    if (kind === "fps") {
      const i = +f.slice(1), arr = f[0] === "m" ? (o.maps || (o.maps = [...m.default.maps])) : (o.rounds || (o.rounds = [...m.default.rounds]));
      arr[i] = f[0] === "m" ? (t.value || null) : (t.value === "" ? null : parseFloat(t.value));
    } else if (f[0] === "p" && f.length === 2 && f !== "p2" && f !== "p3") { const arr = o.pm || (o.pm = [...m.default.pm]); arr[+f[1]] = t.value === "" ? null : parseFloat(t.value); }
    else o[f] = t.value === "" ? null : parseFloat(t.value);
    const d = m.default;                                           // drop the entry when nothing differs from the workbook
    if (kind === "fps" ? JSON.stringify([o.maps || d.maps, o.rounds || d.rounds]) === JSON.stringify([d.maps, d.rounds]) :
        JSON.stringify([o.pm || d.pm, o.p2 ?? d.p2, o.p3 ?? d.p3, o.env ?? d.env]) === JSON.stringify([d.pm, d.p2, d.p3, d.env])) delete OVR[kind][mid];
    store.set("ovr", OVR); bump(); render(true);
  } else if (t.dataset.act) { const v = t.value.trim(); if (v === "" || isNaN(+v)) delete ACT[t.dataset.act]; else ACT[t.dataset.act] = +v; store.set("act", ACT); render(true); }
});
document.addEventListener("click", e => {
  const b = e.target.closest("button[data-reset]");
  if (b) { const [kind, id] = b.dataset.reset.split("|"); if (id) delete OVR[kind][id]; else OVR[kind] = {}; store.set("ovr", OVR); bump(); render(true); }
  if (e.target.id === "cfgreset") { CFGO = {fps: {}, moba: {}}; store.set("cfg", CFGO); bump(); render(true); }
  if (e.target.id === "actclear") { ACT = {}; store.set("act", ACT); render(true); }
  const a = e.target.closest("a[data-go]"); if (a) { e.preventDefault(); F[a.dataset.f] = a.dataset.go; location.hash = a.dataset.tab; }
});

// ---------- Projections ----------
const L = (x, d = 1) => x == null || x === "" ? "" : num(x, d);
const hrCell = x => x == null || x === "" ? "" : pct0(x);
const Pages = {};
Pages["Projections"] = () => {
  const rs = compute().rows.filter(passes);
  const cols = [{k: "player", h: "Player", l: 1}, {k: "title", h: "Title", l: 1}, {k: "team", h: "Team", l: 1}, {k: "match", h: "Match", l: 1}, {k: "market", h: "Market", l: 1},
    {k: "line", h: "Line", f: r => L(r.line)}, {k: "proj", h: "Proj", t: "Model projection", f: r => L(r.proj)},
    {k: "adj", h: "Proj adj", t: "CS2 round-differential layer (HLTV conditional round margins). PAPER, never scored forward.", f: r => L(r.adj)},
    {k: "kpm", h: "Proj KPM", t: "SHADOW: career kills per map x the maps that count (no map names, no rounds). Scored side by side with the projection (hypothesis H9); not the published number.", f: r => L(r.kpm)}, {k: "poKpm", h: "P(over) KPM", f: r => pct1(r.poKpm)},
    {k: "naive", h: "Naive", t: "MOBA: his plain average per map, for comparison", f: r => L(r.naive)},
    {k: "dl", h: "Δ", t: "Projection minus line", v: r => r.proj != null && r.line != null ? r.proj - r.line : null, f: r => r.proj != null && r.line != null ? signed(r.proj - r.line) : ""},
    {k: "po", h: "P(over)", f: r => pct1(r.po)}, {k: "pu", h: "P(under)", f: r => pct1(r.pu)}, {k: "pp", h: "P(push)", t: "A whole-number line shows its push probability separately", f: r => r.pp ? pct1(r.pp) : ""},
    {k: "side", h: "Side (paper)", l: 1, v: r => r.po != null ? Math.abs(r.po - 0.5) : null, f: r => sidePill(r.side, r.po)},
    {k: "poAdj", h: "P(over) adj", f: r => pct1(r.poAdj)}, {k: "sideAdj", h: "Side adj", l: 1, f: r => sidePill(r.sideAdj, r.poAdj)},
    {k: "play", h: "Rule", t: "agree10: both models call the same side and both lean at least 10 points. Declared before the 2026-10-18 games; judged only on slates from then on.", v: r => isPlay(r) ? 1 : 0, f: r => isPlay(r) ? `<span class="pill lean-strong">PLAY ${r.po >= 0.5 ? "OVER" : "UNDER"}</span>` : ""},
    {k: "tp", h: "TP book", t: "Thunderpick's own kill-line median for this player", f: r => L(r.tp)},
    {k: "avg10", h: "PF avg L10", f: r => L(r.avg10)}, {k: "l5", h: "L5", f: r => hrCell(r.l5)}, {k: "l10", h: "L10", f: r => hrCell(r.l10)}, {k: "l15", h: "L15", f: r => hrCell(r.l15)},
    {k: "h2h", h: "H2H", f: r => esc(r.h2h ?? "")}, {k: "streak", h: "Streak", f: r => r.streak ?? ""},
    {k: "maps", h: "Maps used", l: 1}, {k: "rounds", h: "Rounds used", l: 1}, {k: "flags", h: "Flags", l: 1, f: r => flagPills(r.flags)}];
  return `<h2>Projections</h2><p class="sub">${D.meta.slate} slate · ${rs.length} of ${compute().rows.length} legs. Change maps, rounds, win probabilities or constants on the <a href="#Matches">Matches</a> and <a href="#Config">Config</a> tabs and every number follows.
    ${hasEdits() ? `<b class="warn">Showing your edits, not the workbook defaults.</b>` : ""}</p>
    ${filters(sel("side", "Side", [["", "All"], ["any", "Any side"], ["OVER", "OVER"], ["UNDER", "UNDER"]], F.side) + `<label><input type="checkbox" id="flagged" ${F.flagged ? "checked" : ""}> flagged only</label> <label><input type="checkbox" id="rule" ${F.rule ? "checked" : ""}> rule plays only</label>`)}
    ${table(cols, rs, {id: "proj", sort: {key: "side", asc: false}})}`;
};
const hasEdits = () => Object.keys(OVR.fps).length || Object.keys(OVR.moba).length || Object.keys(CFGO.fps).length || Object.keys(CFGO.moba).length;

// ---------- Board: one match, both rosters ----------
const allMatches = () => [...D.fps.matches.map(m => ({...m, kind: "fps"})), ...D.moba.matches.map(m => ({...m, kind: "moba"}))];
Pages["Board"] = () => {
  const ms = allMatches(), mid = F.bmatch && ms.find(m => m.id === F.bmatch) ? F.bmatch : ms[0].id, m = ms.find(x => x.id === mid), C = compute();
  const pick = sel("bmatch", "Match", ms.map(x => [x.id, `${x.id} · ${x.start}`]), mid);
  if (m.kind === "fps") {
    const st = C.f.states[mid] || FPS.matchState(C.f.I, D.fps, mid, OVR.fps), legs = C.f.legs.filter(g => g.match === mid);
    const byKey = {};
    for (const g of legs) (byKey[g.key] || (byKey[g.key] = {})) [g.code] = g;
    const rows = Object.keys(byKey).map(k => ({k, c: C.f.calcs[k], g: byKey[k], p: C.f.I.players[k.split("|")[0]]})).filter(r => r.c).sort((a, b) => b.c.K12 - a.c.K12);
    const mp = (x, y) => x == null ? "" : y(x);
    const cols = [{k: "team", h: "Team", l: 1, f: r => esc(r.p.team)}, {k: "player", h: "Player", l: 1, f: r => esc(r.p.player)},
      {k: "k1", h: "KPR M1", f: r => L(r.c.k[0].kpr, 3)}, {k: "k2", h: "KPR M2", f: r => L(r.c.k[1].kpr, 3)}, {k: "e1", h: "Kills M1", f: r => L(r.c.K1)}, {k: "e2", h: "Kills M2", f: r => L(r.c.K2)},
      {k: "e12", h: "Kills 1-2", v: r => r.c.K12, f: r => L(r.c.K12)}, {k: "dm", h: "Diff mult", f: r => L(r.c.diffMult12, 3)}, {k: "a12", h: "Adj K 1-2", f: r => L(r.c.adj.K12)},
      {k: "pp", h: "PP line", f: r => L(r.g.K12?.line)}, {k: "po", h: "P(over)", f: r => pct1(r.g.K12?.out?.p_over)}, {k: "pa", h: "Adj P(over)", f: r => pct1(r.g.K12?.out?.p_over_adj)},
      {k: "tp", h: "TP book", f: r => L(r.g.K12?.tp)}, {k: "l10", h: "PF L10", f: r => hrCell(r.g.K12?.l10)},
      {k: "hp", h: "HS% 1-2", f: r => pct1(r.c.hsPct12)}, {k: "h12", h: "HS 1-2", f: r => L(r.c.H12)}, {k: "hl", h: "PP HS line", f: r => L(r.g.H12?.line)}, {k: "hpo", h: "P(over) HS", f: r => pct1(r.g.H12?.out?.p_over)},
      {k: "n", h: "Sample", f: r => r.c.sample}, {k: "fl", h: "Flags", l: 1, f: r => flagPills(r.c.flags)}];
    return `<h2>Board</h2><p class="sub">Pick a match: both rosters, ranked by projected Maps 1-2 kills.</p><div class="bar">${pick}</div>${matchHead(m, st)}
      ${table(cols, rows, {id: "bd", sort: {key: "e12", asc: false}})}`;
  }
  const legs = C.m.legs.filter(g => g.match === mid), keys = [...new Set(legs.map(g => g.key))];
  const rows = keys.map(k => ({k, g: legs.filter(x => x.key === k)})).map(r => ({...r, c: r.g[0].calc, p: C.m.P[r.k.split("|")[0]]})).sort((a, b) => N0(b.c.K1) - N0(a.c.K1));
  const leg = (r, code) => r.g.find(x => x.code === code);
  const ser = r => leg(r, r.c.seriesCode);
  const cols = [{k: "team", h: "Team", l: 1, f: r => esc(r.p?.team)}, {k: "player", h: "Player", l: 1, f: r => esc(r.p?.player)}, {k: "q", h: "Map win q", f: r => L(r.c.q, 2)}, {k: "K", h: "K avg", f: r => L(r.c.K)},
    {k: "kw", h: "k win", f: r => L(r.c.kwin, 2)}, {k: "kl", h: "k loss", f: r => L(r.c.kloss, 2)}, {k: "pw", h: "P(win M1)", f: r => pct1(r.c.maps[0].pw)},
    {k: "p1", h: "Proj M1", v: r => r.c.K1, f: r => L(r.c.K1, 2)}, {k: "n1", h: "Naive M1", f: r => L(r.c.naive.K1)}, {k: "l1", h: "Line M1", f: r => L(leg(r, "K1")?.line)}, {k: "o1", h: "P(over) M1", f: r => pct1(leg(r, "K1")?.out?.p_over)},
    {k: "ps", h: "Proj series", f: r => L(r.c[r.c.seriesCode], 2)}, {k: "ls", h: "Line series", f: r => L(ser(r)?.line)}, {k: "os", h: "P(over) series", f: r => pct1(ser(r)?.out?.p_over)},
    {k: "tp", h: "TP book", f: r => L((leg(r, "K1") || ser(r))?.tp)}, {k: "l10", h: "PF L10", f: r => hrCell((leg(r, "K1") || ser(r))?.l10)}, {k: "n", h: "Sample", f: r => r.c.sample}, {k: "fl", h: "Flags", l: 1, f: r => flagPills(r.c.flags)}];
  const stm = C.m.legs[0] ? MOBA.state(m, OVR.moba) : {};
  return `<h2>Board</h2><p class="sub">Pick a match: both rosters, ranked by projected Map 1 kills.</p><div class="bar">${pick}</div>
    <div class="gamehead"><div><span>Match</span><b>${esc(m.a)} v ${esc(m.b)}</b></div><div><span>Event</span><b>${esc(m.event)} · Bo${m.bo}</b></div><div><span>Starts (CT)</span><b>${esc(m.start)}</b></div>
    <div><span>P(A wins)</span><b>${pct1(m.pA)}</b></div><div><span>P(A wins M1)</span><b>${pct1(stm.pm?.[0])}</b></div><div><span>P(M2 / M3 played)</span><b>${pct0(stm.p2)} / ${pct0(stm.p3)}</b></div>
    <div><span>Kills env ×</span><b>${stm.env ?? ""}</b></div></div>${table(cols, rows, {id: "bdm", sort: {key: "p1", asc: false}})}`;
};
const N0 = x => typeof x === "number" ? x : 0;
function matchHead(m, st) {
  const h = i => st.hltv[i] || {};
  const mapsTxt = st.maps.map((x, i) => x ? `Map ${i + 1}: <b>${esc(x)}</b>` : "").filter(Boolean).join(" · ");
  return `<div class="gamehead"><div><span>Match</span><b>${esc(m.a)} v ${esc(m.b)}</b></div><div><span>Start (CT) · Bo</span><b>${esc(m.start)} · Bo${m.bo}</b></div>
    <div><span>P(A wins)</span><b>${pct1(m.pA)}</b></div><div><span>P(A 2-0) / P(B 2-0)</span><b>${pct0(m.pA20)} / ${pct0(m.pB20)}</b></div><div><span>P(3 maps)</span><b>${pct0(m.p3_used)}</b></div>
    <div><span>Map picks (${esc(m.picks_from)})</span><b>${esc([m.pick1, m.pick2, m.pick3].filter(Boolean).join(", "))}</b></div>
    <div><span>In use</span><b>${mapsTxt}</b></div><div><span>Rounds in use</span><b>${st.rounds.map(x => x == null ? "—" : num(x)).join(" / ")}</b></div>
    <div><span>HLTV A margin M1/M2/M3</span><b>${[0, 1, 2].map(i => h(i).margin == null ? "—" : signed(h(i).margin, 2)).join(" · ")}</b></div>
    <div><span>Hist round share A / B</span><b>${pct0(m.hist_a)} / ${pct0(m.hist_b)}</b></div></div>
    <p class="mut">Change maps or rounds on the <a href="#Matches">Matches</a> tab.</p>`;
}

// ---------- Matches: the shaded cells ----------
Pages["Matches"] = () => {
  const fo = OVR.fps, mo = OVR.moba, C = compute();
  const mapSel = (m, i) => { const cur = (fo[m.id]?.maps || m.default.maps)[i]; return `<select data-mo="fps" data-id="${esc(m.id)}" data-f="m${i}"><option value=""></option>${D.fps.maps[m.title].map(x => `<option ${x === cur ? "selected" : ""}>${x}</option>`).join("")}</select>`; };
  const rnd = (m, i) => `<input class="ovr" data-mo="fps" data-id="${esc(m.id)}" data-f="r${i}" value="${(fo[m.id]?.rounds || m.default.rounds)[i] ?? ""}" size="5">`;
  const fcols = [{k: "id", h: "Match", l: 1, f: m => `<a href="#" data-go="${esc(m.id)}" data-f="bmatch" data-tab="Board">${esc(m.id)}</a>${fo[m.id] ? ` <span class="pill q">edited</span>` : ""}`}, {k: "start", h: "Start (CT)", l: 1}, {k: "bo", h: "Bo"},
    {k: "pA", h: "P(A wins)", f: m => pct0(m.pA)}, {k: "p3", h: "P(3 maps)", f: m => pct0(m.p3_used)},
    ...[0, 1, 2].map(i => ({k: "m" + i, h: `Map ${i + 1}`, l: 1, t: "Prefilled from PickFinder's Map Picks. Confirm after the veto.", f: m => mapSel(m, i)})),
    ...[0, 1, 2].map(i => ({k: "r" + i, h: `Rounds M${i + 1}`, t: "Prefilled from Thunderpick's Total Rounds ladder (or the Config default). The posted total has failed as a forecast: this is where your view goes.", f: m => rnd(m, i)})),
    {k: "tp", h: "TP rounds M1/M2", f: m => [m.tp_r1, m.tp_r2].map(x => x == null ? "—" : num(x, 1)).join(" / ")}, {k: "ps", h: "Picks from", l: 1, f: m => esc(m.picks_from)},
    {k: "rs", h: "", f: m => fo[m.id] ? `<button data-reset="fps|${esc(m.id)}">reset</button>` : ""}];
  const mnum = (m, f, v, w = 5) => `<input class="ovr" data-mo="moba" data-id="${esc(m.id)}" data-f="${f}" value="${v ?? ""}" size="${w}">`;
  const mcols = [{k: "id", h: "Match", l: 1, f: m => `<a href="#" data-go="${esc(m.id)}" data-f="bmatch" data-tab="Board">${esc(m.id)}</a>${mo[m.id] ? ` <span class="pill q">edited</span>` : ""}`}, {k: "event", h: "Event", l: 1}, {k: "start", h: "Start (CT)", l: 1}, {k: "bo", h: "Bo"},
    {k: "pA", h: "P(A wins)", f: m => pct0(m.pA)},
    ...[0, 1, 2].map(i => ({k: "pm" + i, h: `P(A wins M${i + 1})`, t: "Thunderpick Map k Winner, devigged", f: m => mnum(m, "p" + i, (mo[m.id]?.pm || m.default.pm)[i])})),
    {k: "p2", h: "P(M2 played)", f: m => mnum(m, "p2", mo[m.id]?.p2 ?? m.default.p2)}, {k: "p3", h: "P(M3 played)", f: m => mnum(m, "p3", mo[m.id]?.p3 ?? m.default.p3)},
    {k: "env", h: "Kills env ×", t: "1 = the players' own history; 1.10 = a game 10% bloodier", f: m => mnum(m, "env", mo[m.id]?.env ?? m.default.env)},
    {k: "rs", h: "", f: m => mo[m.id] ? `<button data-reset="moba|${esc(m.id)}">reset</button>` : ""}];
  return `<h2>Matches</h2><p class="sub">The shaded cells are yours. FPS: the maps and the rounds expected on each (every projection in the match recalculates). MOBA: P(win) per map, whether maps 2 and 3 get played, and a kill-environment multiplier.
    Edits are saved on this device and never touch the workbook. <button data-reset="fps">reset all FPS</button> <button data-reset="moba">reset all MOBA</button></p>
    <h3>FPS — CS2 and Valorant</h3>${table(fcols, D.fps.matches, {id: "mf"})}<h3>MOBA — LoL and Dota 2</h3>${table(mcols, D.moba.matches, {id: "mm"})}${marketCheck()}`;
};

// the bookmakers' view of each match next to the model's inputs (OddsPapi, de-vigged, median across books; pulled by pipeline/odds.py)
function marketCheck() {
  const O = D.odds;
  if (!O || O.slate !== D.meta.slate) return `<h3>Market check</h3><p class="sub">No bookmaker odds pulled for this slate yet (run the <b>Odds</b> workflow once the board is built). Nothing here is a bet signal: it is a second opinion on the inputs.</p>`;
  const rows = Object.entries(O.matches).map(([id, v]) => ({id, ...v}));
  if (!rows.length) return "";
  const mp = (x) => x ? `${pct0(x.p)} <span class="mut">[${pct0(x.lo)}–${pct0(x.hi)}, ${x.n} books]</span>` : "—";
  const diff = (a, b) => a == null || b == null ? "" : signed((b - a) * 100, 0);
  const cols = [{k: "id", h: "Match", l: 1}, {k: "mA", h: "Model P(A wins)", f: r => pct0(r.model.pA)}, {k: "kA", h: "Market P(A wins)", t: "Median of the bookmakers' de-vigged prices, team A = the board's first team", f: r => mp(r.series.p1)},
    {k: "sh", h: "Pinnacle", f: r => r.series.sharp_p1 == null ? "—" : pct0(r.series.sharp_p1)}, {k: "d", h: "Mkt − model (pts)", f: r => diff(r.model.pA, r.series.p1?.p)},
    {k: "m3", h: "P(map 3 played) model / market", t: "Best of 3: from the 2.5 total-maps line. Best of 5: always played.", f: r => (r.model.bo === 5 ? "100% / 100%" : `${pct0(r.model.p3)} / ${r.p_map3?.market ? pct0(r.p_map3.market.p) : "—"}`)},
    ...[1, 2, 3].map(i => ({k: "r" + i, h: `Rounds M${i}: model / market line (P over)`, t: "The market's consensus total-rounds line for the map and the chance of the over", f: r => { const x = r.rounds?.[i]; return `${num(r.model.rounds[i - 1], 1)} / ${x ? `${x.line} (${pct0(x.p_over)})` : "—"}`; }})),
    {k: "tkm", h: "Team kills per map: model ≈ / market ladder", t: "Model ≈ = the Maps 1-2 kills projections for that team's players, summed and halved (players with a line; n in brackets). Market = the books' team-kills ladder for maps 1 and 2: line (P over). Not yet tested as a forecast: compare with the result after the games.",
      f: r => ["A", "B"].map(sd => { const m = D.fps.matches.find(x => x.id === r.id), tag = m && (sd === "A" ? m.tag_a : m.tag_b); const ps = compute().rows.filter(x => x.match === r.id && x.team === tag && x.market === "Maps 1-2 Kills");
        const lad = [1, 2].map(i => r.team_kills?.[i]?.[sd]?.ladder).filter(Boolean); if (!ps.length && !lad.length) return "";
        const sum = ps.reduce((t, x) => t + (x.proj || 0), 0);
        return `${sd}: ${ps.length ? `${num(sum / 2, 1)} (${ps.length}) / ` : ""}${lad.map(l => l.map(([ln, p]) => `${ln} (${pct0(p)})`).join(" · ")).join(" | ") || "—"}`; }).filter(Boolean).join("<br>")},
    {k: "ot", h: "Overtime M1", f: r => r.overtime?.["1"]?.yes ? pct0(r.overtime["1"].yes.p) : "—"},
    {k: "pp", h: "Player markets priced", t: "Kill and headshot lines per player, when a bookmaker has posted them (none had on 2026-10-17)", f: r => Object.keys(r.player || {}).length}];
  return `<h3>Market check</h3><p class="sub">Bookmakers via OddsPapi, pulled ${esc(rows[0].captured_utc)}. A second opinion on series strength, how many maps and how long they run; not a bet signal.</p>${table(cols, rows, {id: "mk"})}`;
}

// ---------- Intel: HLTV, vetoes, Thunderpick ladders and book ----------
function intelBlocks() {
  const rows = D.fps.intel, out = {};
  let cur = null;
  for (const r of rows) {
    const a = r[0] == null ? "" : String(r[0]);
    const m = a.match(/^((?:CS2|VAL) · .+?)\s+\|\s+/);
    if (m) { cur = m[1]; out[cur] = [r]; } else if (cur && r.some(x => x != null)) out[cur].push(r);
  }
  return out;
}
Pages["Intel"] = () => {
  const ms = D.fps.matches, mid = F.imatch && ms.find(m => m.id === F.imatch) ? F.imatch : ms[0].id, m = ms.find(x => x.id === mid), blocks = intelBlocks(), blk = blocks[mid] || [];
  const tbl = (head, rows) => `<div class="tw"><table><thead><tr>${head.map(h => `<th class="l">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(x => `<td class="l" style="white-space:normal">${esc(x ?? "")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const mt = D.fps.hltv_teams.filter(t => t.match === mid), vt = D.fps.veto.filter(t => t.match === mid), ld = D.fps.ladders.filter(t => t.match === mid), bk = D.fps.book.filter(t => t.match === mid);
  const intel = blk.slice(1).map(r => r.map(x => x == null ? "" : String(x)).filter((x, i, a) => x !== "" || i < 3));
  return `<h2>Intel</h2><p class="sub">Recent form, margins, ranks, map pools and vetoes per match (HLTV 3 months to the day before the slate; vlr last 10 series). Margins are rounds: + won by, − lost by. Bucket probabilities are the frozen v2 model (PAPER, not a pick).</p>
    <div class="bar">${sel("imatch", "Match", ms.map(x => [x.id, x.id]), mid)}</div>
    ${intel.length ? `<h3>Match intel</h3>${tbl([], intel).replace("<thead><tr></tr></thead>", "")}` : `<p class="mut">No match-intel block for this match.</p>`}
    ${mt.length ? `<h3>HLTV team analytics</h3>${tbl(["Side", "Team", "Rounds lost in wins", "Rounds won in losses", "P(2-0)", "P(2-1)", "P(0-2)", "P(1-2)", "OT %", "Map win rate", "Hist round share"], mt.map(t => [t.side, t.team, t.lw, t.wl, t.p20, t.p21, t.p02, t.p12, t.ot, num(t.win, 3), num(t.share, 3)]))}` : ""}
    ${vt.length ? `<h3>HLTV veto</h3>${tbl(["Map", "Team", "First pick %", "First ban %", "Win %", "Played (3 mo)"], vt.map(t => [t.map, t.team, t.first_pick, t.first_ban, t.win, t.played]))}` : ""}
    ${ld.length ? `<h3>Thunderpick total-rounds ladders</h3>${tbl(["Map", "Total", "Over", "Under", "P(over) devigged", "50% crossing"], ld.map(t => [t.map, t.total, t.over, t.under, num(t.p_over, 3), num(t.cross, 2)]))}` : ""}
    ${bk.length ? `<h3>Thunderpick player kill ladders</h3>${tbl(["Player", "Map 1 median", "Map 2 median", "Maps 1-2 median"], bk.map(t => [t.name, t.m1, t.m2, t.m12]))}` : ""}
    <h3>MOBA — Thunderpick kill ladders</h3>${tbl(["Match", "Player", "Map 1 median", "Map 2 median", "Map 3 median", "Rungs (M1)"], D.moba.book.map(t => [t.match, t.name, t.m1, t.m2, t.m3, t.rungs]))}`;
};

// ---------- Log: the frozen projections, with Actuals ----------
const actKey = (slate, kind, r) => `${slate}|${kind}|${r.Match}|${r.Player}|${r.Market}`;
function logRows() {
  const out = [];
  for (const s of D.meta.slates) {
    const L = D.logs[s];
    if (!L) continue;
    for (const [kind, rows] of [["FPS", L.fps], ["MOBA", L.moba]]) for (const r of rows) {
      const k = actKey(s, kind, r), a = ACT[k] != null ? ACT[k] : (typeof r.Actual === "number" ? r.Actual : null);
      const line = r.Line, res = a == null ? "" : a > line ? "OVER" : a < line ? "UNDER" : "PUSH";
      out.push({kind, slate: s, k, match: r.Match, player: r.Player, market: r.Market, line, proj: r.Proj, po: r["P(over)"], adj: r["Proj adj"], poAdj: r["P(over) adj"], mapfree: r["Proj map-free"],
        mapfreeAdj: r["Proj map-free adj"], source: r.Source, note: r.Note, naive: r["Naive proj"], poNaive: r["P(over) naive"], tp: r["TP book median"], l10: r["PF L10"], maps: r["Maps used"], rounds: r["Rounds used"], actual: a, result: res, local: ACT[k] != null});
    }
  }
  return out;
}
const sideOf = (po, edge) => po == null ? "" : po >= 0.5 + edge ? "OVER" : po <= 0.5 - edge ? "UNDER" : "—";
Pages["Log"] = () => {
  const slates = D.meta.slates, s = F.slate && slates.includes(F.slate) ? F.slate : slates[slates.length - 1];
  const live = {};
  for (const r of compute().rows) live[`${r.kind}|${r.match}|${r.player}|${r.market}`] = r;
  const rs = logRows().filter(r => r.slate === s && (!F.title || (r.match.split(" ")[0] === F.title)) && (!F.market || r.market === F.market) && (!F.q.trim() || (r.player + r.match).toLowerCase().includes(F.q.trim().toLowerCase())));
  rs.forEach(r => { const l = s === D.meta.slate ? live[`${r.kind}|${r.match}|${r.player}|${r.market}`] : null; r.live = l ? l.proj : null; });   // an older slate is never judged against today's inputs
  const E = cfg("fps").EDGE_MIN;
  const cols = [{k: "player", h: "Player", l: 1}, {k: "match", h: "Match", l: 1}, {k: "market", h: "Market", l: 1}, {k: "line", h: "Line", f: r => L(r.line)}, {k: "proj", h: "Proj (frozen)", f: r => L(r.proj, 2)},
    {k: "live", h: "Proj (live)", t: "What the model says now, with your edits. Equal to the frozen value at the workbook's defaults. Shown for the live slate only.", f: r => r.live == null ? "" : Math.abs(r.live - r.proj) > 0.006 ? `<span class="warn">${L(r.live, 2)}</span>` : L(r.live, 2)},
    {k: "po", h: "P(over)", f: r => pct1(r.po)}, {k: "side", h: "Side (paper)", l: 1, v: r => Math.abs(N0(r.po) - 0.5), f: r => sidePill(sideOf(r.po, E) === "—" ? "" : sideOf(r.po, E), r.po)},
    {k: "adj", h: "Proj adj", f: r => L(r.adj, 2)}, {k: "naive", h: "Naive", f: r => L(r.naive, 2)}, {k: "tp", h: "TP book", f: r => L(r.tp)}, {k: "l10", h: "PF L10", f: r => hrCell(r.l10)},
    {k: "maps", h: "Maps", l: 1}, {k: "act", h: "Actual", t: "Type the result after settlement. Saved on this device; the permanent route is the workbook's Log, re-imported.",
      f: r => `<input class="ovr" data-act="${esc(r.k)}" value="${r.actual ?? ""}" size="5">${r.local ? "" : ""}`}, {k: "result", h: "Result", l: 1, f: r => r.result},
    {k: "note", h: "Settlement", l: 1, t: "Where the Actual came from, or why this leg is not settled", v: r => r.actual != null ? "" : (r.note || ""), f: r => r.actual != null ? `<span class="mut">${esc(r.source || (r.local ? "typed here" : ""))}</span>` : `<span class="mut">${esc(r.note || "")}</span>`}];
  const settled = rs.filter(r => r.actual != null).length;
  return `<h2>Log</h2><p class="sub">The projections frozen as values at default settings when each workbook was built — the forward record. ${settled} of ${rs.length} legs settled for ${s}. Type an Actual and the Scorecard picks it up.
    <button id="actclear">clear my typed actuals</button></p>
    <div class="bar">${sel("slate", "Slate", slates.map(x => [x, x]), s)}<input id="q" placeholder="Search" value="${esc(F.q)}">${sel("title", "Title", [["", "All"], ["CS2", "CS2"], ["VAL", "Valorant"], ["LOL", "LoL"], ["DOTA", "Dota 2"]], F.title)}</div>
    ${table(cols, rs, {id: "log", sort: {key: "player", asc: true}})}`;
};

// ---------- Scorecard ----------
function summarise(rows, kind) {
  const set = rows.filter(r => r.actual != null);
  const mae = f => { const x = set.filter(r => r[f] != null); return x.length ? x.reduce((t, r) => t + Math.abs(r[f] - r.actual), 0) / x.length : null; };
  const bias = f => { const x = set.filter(r => r[f] != null); return x.length ? x.reduce((t, r) => t + (r[f] - r.actual), 0) / x.length : null; };
  const E = cfg("fps").EDGE_MIN, graded = r => r.result !== "PUSH";
  const sided = set.filter(r => graded(r) && sideOf(r.po, E) !== "" && sideOf(r.po, E) !== "—"), all = set.filter(r => graded(r) && r.po != null);
  return {n: set.length, total: rows.length, sided: sided.length, sidedHits: sided.filter(r => sideOf(r.po, E) === r.result).length, picks: all.length, pickHits: all.filter(r => (r.po >= 0.5 ? "OVER" : "UNDER") === r.result).length,
    mae: mae("proj"), bias: bias("proj"), maeAdj: mae("adj"), maeMapfree: mae("mapfree"), maeMapfreeAdj: mae("mapfreeAdj"), maeNaive: mae("naive")};
}
// ---------- Evaluation (written by pipeline/evaluate.py after each settle) ----------
function evalSection() {
  const E = D.eval;
  if (!E || !E.slates || !E.slates.length) return "";
  const ci = (e, d = 3) => !e || e.value == null ? "" : `${num(e.value, d)}${e.ci ? ` <span class="mut">[${num(e.ci[0], d)}, ${num(e.ci[1], d)}]</span>` : ""}`;
  const stat = {supported: "good", contradicted: "bad"};
  const block = (title, ev, note) => {
    if (!ev || !ev.summary) return `<h4>${title}</h4><p class="sub">${note}</p>`;
    const S = ev.summary, a = S.auc || {}, all = (S.error || {}).all || {}, cf = S.counterfactual, rd = S.rounds, mp = S.map_picks;
    const aucRows = Object.keys(a).map(k => [k, a[k]]);
    const lean = (S.lean_bins || []).map(b => `<tr><td class="l">${esc(b.label)}</td><td>${b.n}</td><td>${pct1(b.rate)} <span class="mut">[${pct0(b.wilson[0])}, ${pct0(b.wilson[1])}]</span></td></tr>`).join("");
    const cal = (S.calibration || []).map(b => `<tr><td class="l">${pct0(b.lo)}–${pct0(b.hi)}</td><td>${b.n}</td><td>${pct1(b.mean_p)}</td><td>${pct1(b.over_rate)}</td></tr>`).join("");
    return `<h4>${title}</h4><p class="sub">Slates: ${ev.slates.join(", ")}. ${S.n_settled} settled legs, ${S.n_matches} matches; over-rate ${pct1(S.over_rate)} (always-under would hit ${pct1(S.always_under_hit)}).</p>
      <div class="two"><div><h5>Ranking (AUC, 0.5 = no skill; match-clustered 95% interval)</h5><div class="tw"><table><tbody>${aucRows.map(([k, v]) => `<tr><td class="l">${esc(k)}</td><td>${ci(v)}</td><td class="mut">n=${v.n}</td></tr>`).join("")}</tbody></table></div>
      <h5>Error vs the posted line</h5><div class="tw"><table><tbody><tr><td class="l">MAE · posted line</td><td>${num(all.mae_line, 3)}</td></tr><tr><td class="l">MAE · projection</td><td>${num(all.mae_proj, 3)}</td></tr><tr><td class="l">MAE · map-free</td><td>${num(all.mae_map_free, 3)}</td></tr><tr><td class="l">MAE · adj</td><td>${num(all.mae_adj, 3)}</td></tr><tr><td class="l">MAE · kills per map (shadow)</td><td>${num(all.mae_kpm, 3)}</td></tr>
      <tr><td class="l">Bias · projection / line</td><td>${signed(all.bias_proj, 2)} / ${signed(all.bias_line, 2)}</td></tr><tr><td class="l">Gap slope (1 = fully informative)</td><td>${ci(S.gap_slope)}</td></tr><tr><td class="l">Brier (coin = 0.25)</td><td>${num(S.brier, 4)}</td></tr></tbody></table></div></div>
      <div><h5>Hit rate by size of lean</h5><div class="tw"><table><thead><tr><th class="l">Lean</th><th>Legs</th><th>Hit rate</th></tr></thead><tbody>${lean}</tbody></table></div>
      <h5>Calibration</h5><div class="tw"><table><thead><tr><th class="l">P(over)</th><th>Legs</th><th>Mean P</th><th>Went over</th></tr></thead><tbody>${cal}</tbody></table></div></div></div>
      ${cf ? `<h5>Inputs, not the model</h5><p class="sub">Re-running the model with the maps and rounds actually played (${cf.n} legs): MAE ${num(cf.mae_published, 3)} → ${num(cf.mae_actual_inputs, 3)}, bias ${signed(cf.bias_published, 2)} → ${signed(cf.bias_actual_inputs, 2)}.${
        rd ? ` Rounds per map assumed ${num(rd.assumed_mean, 1)} (sd ${num(rd.assumed_sd, 2)}) vs played ${num(rd.played_mean, 1)} (sd ${num(rd.played_sd, 1)}), ${rd.n_maps} maps. Rounds-bias check: the long-run mean is ${num(rd.history_mean, 2)} (1,199 maps), so the assumption sits ${signed(rd.assumed_minus_history, 2)} from it and this sample ${signed(rd.played_minus_history, 2)}; ${pct0(rd.share_over_21_5)} of these maps went over 21.5 (history ${pct0(rd.history_share_over_21_5)}).` : ""}${mp ? ` Map picks right: ${mp.hit}/${mp.total}.` : ""}</p>` : ""}`;
  };
  const last = E.slates[E.slates.length - 1], hyp = (E.by_slate[last] || {}).hypotheses || [];
  const pooled = (E.confirmatory && E.confirmatory.summary ? E.confirmatory : E.exploratory);
  const hs = (pooled && pooled.summary ? pooled.summary.hypotheses : hyp) || [];
  const SD = E.side, sideRow = (label, d) => !d ? `<tr><td class="l">${label}</td><td colspan="4" class="mut">no slate yet</td></tr>` : `<tr><td class="l">${label}</td><td>${d.hits}/${d.n} = <b>${pct1(d.rate)}</b></td><td class="mut">[${pct1(d.clustered_ci && d.clustered_ci[0])}, ${pct1(d.clustered_ci && d.clustered_ci[1])}]</td><td>${signed(d.headroom * 100, 1)} pts</td><td class="mut">${d.legs_to_confirm ? "≈" + d.legs_to_confirm + " legs to be sure" : "not above breakeven"}</td></tr>`;
  const sideBlock = SD ? `<h4>Side calls vs breakeven</h4><p class="sub">The goal: P(over) ≥ 50% calls over, below calls under, and the hit rate clears the flex breakeven (${Object.entries(SD.breakeven).map(([k, v]) => `${k} ${pct1(v)}`).join(", ")}; payouts to confirm in the app). Size of the win does not matter here. The interval resamples whole matches. The forward test counts only slates after ${SD.declared_after}, when this goal was written down.</p>
    <div class="tw"><table><thead><tr><th class="l">Record</th><th>Hit rate</th><th>95% interval</th><th>vs breakeven</th><th class="l">Sample</th></tr></thead><tbody>${sideRow("Forward test (after " + SD.declared_after + ")", SD.forward && SD.forward.summary && SD.forward.summary.side)}${sideRow("All settled slates (descriptive)", SD.all)}${sideRow("Rule agree10, forward test", SD.forward && SD.forward.summary && SD.forward.summary.rules && SD.forward.summary.rules.agree10)}${sideRow("Rule agree10, all slates (descriptive: found after seeing 10-16 and 10-17)", SD.rules_all && SD.rules_all.agree10)}${sideRow("Every leg UNDER (H10), forward test (after " + (SD.under_after || "2026-10-19") + ")", SD.under_forward && SD.under_forward.summary && SD.under_forward.summary.rules && SD.under_forward.summary.rules.all_under)}${sideRow("Every leg UNDER, all slates (descriptive: found after seeing them)", SD.rules_all && SD.rules_all.all_under)}${sideRow("Under shortlist (H11), forward test (after " + (SD.core_after || "2026-10-21") + ")", SD.core_forward && SD.core_forward.summary && SD.core_forward.summary.rules && SD.core_forward.summary.rules.under_core)}${sideRow("Under shortlist, all slates (descriptive: cut-offs read off 10-16..19)", SD.rules_all && SD.rules_all.under_core)}${sideRow("Last-10 0.8+ OVER (H12), forward test (after " + (SD.l10_after || "2026-10-24") + ")", SD.l10_forward && SD.l10_forward.summary && SD.l10_forward.summary.rules && SD.l10_forward.summary.rules.l10_over)}${sideRow("Last-10 0.8+ OVER, all slates (descriptive: read off 10-16..24)", SD.rules_all && SD.rules_all.l10_over)}${sideRow("Both models agree, lean 20+ (H13), forward test (after " + (SD.lean20_after || "2026-10-26") + ")", SD.lean20_forward && SD.lean20_forward.summary && SD.lean20_forward.summary.rules && SD.lean20_forward.summary.rules.agree20)}${sideRow("Both models agree, lean 20+, all slates (descriptive: cut-off read off 10-18..25)", SD.rules_all && SD.rules_all.agree20)}</tbody></table></div>` : "";
  return `<h3>Evaluation</h3>${sideBlock}<p class="sub">Predictive-quality checks, rebuilt by <code>python -m pipeline.evaluate</code> after each settle. Hypotheses H1–H6 were written down after looking at ${E.exploratory_through}, so that slate can only suggest; slates after it are the test. Wide intervals mean “don't know yet”, not “no effect”.</p>
    <div class="tw"><table><thead><tr><th class="l">Hypothesis</th><th class="l">Metric</th><th>Estimate</th><th>n</th><th class="l">Status</th></tr></thead><tbody>${hs.map(h => `<tr><td class="l">${h.id} ${esc(h.name)}</td><td class="l" style="white-space:normal">${esc(h.metric)}</td><td>${ci({value: h.estimate, ci: h.ci})}</td><td>${h.n}</td><td class="l ${stat[h.status] || "mut"}">${h.status}</td></tr>`).join("")}</tbody></table></div>
    <p class="sub">Showing ${E.confirmatory && E.confirmatory.summary ? "the confirmatory pool" : "the exploratory slate only — no confirmatory slate has settled yet"}.</p>
    ${block("Confirmatory (after " + E.exploratory_through + ")", E.confirmatory, "No slate after the exploratory one has settled yet.")}
    ${block("Exploratory (through " + E.exploratory_through + ")", E.exploratory, "Nothing settled.")}`;
}

Pages["Scorecard"] = () => {
  const rows = logRows(), S = summarise(rows);
  if (!S.n) return `<h2>Scorecard</h2><div class="banner"><b>No settled legs yet.</b> The Log holds ${rows.length} frozen projections from ${D.meta.slates.length} slate(s) with no Actual. Type results on the <a href="#Log">Log</a> tab (saved on this device), or re-import a workbook whose Log has Actual filled in. Both models are PAPER: this record is how they get scored.</div>`;
  const grp = (name, f, vals) => vals.map(v => ({k: v, ...summarise(rows.filter(r => f(r) === v))})).filter(x => x.n);
  const cols = first => [{k: "k", h: first, l: 1}, {k: "n", h: "Settled"}, {k: "side", h: "Model side (paper)", v: r => r.sided ? r.sidedHits / r.sided : null, f: r => pc1(r.sidedHits, r.sided)},
    {k: "pick", h: "Every leg, P≥50%", v: r => r.picks ? r.pickHits / r.picks : null, f: r => pc1(r.pickHits, r.picks)}, {k: "mae", h: "MAE proj", f: r => L(r.mae, 2)}, {k: "bias", h: "Bias", f: r => signed(r.bias, 2)},
    {k: "adj", h: "MAE adj", f: r => L(r.maeAdj, 2)}, {k: "mf", h: "MAE map-free", f: r => L(r.maeMapfree, 2)}, {k: "nv", h: "MAE naive", f: r => L(r.maeNaive, 2)}];
  return `<h2>Scorecard</h2><p class="sub">Every settled leg of the frozen Log. “Model side” counts only legs where P(over) cleared 50% ± EDGE_MIN; pushes are excluded. A paper ordering, not an edge, until this record says otherwise.</p>
    <div class="cards">${card(S.n, "legs settled")}${card(pc1(S.sidedHits, S.sided), "model side")}${card(pc1(S.pickHits, S.picks), "every leg, P≥50%")}${card(L(S.mae, 2), "MAE · projection")}${card(L(S.maeAdj, 2), "MAE · adj")}</div>
    <div class="two"><div><h3>By market</h3>${table(cols("Market"), grp("m", r => r.market, MARKETS), {id: "sc1"})}</div><div><h3>By slate</h3>${table(cols("Slate"), grp("s", r => r.slate, D.meta.slates), {id: "sc2"})}</div></div>
    <h3>By title</h3>${table(cols("Title"), grp("t", r => r.match.split(" ")[0], ["CS2", "VAL", "LOL", "DOTA"]), {id: "sc3"})}${evalSection()}`;
};

// ---------- Data ----------
Pages["Data"] = () => {
  const C = compute(), live = [];
  const nofit = C.rows.filter(r => r.line != null && r.proj == null).length, errs = C.rows.filter(r => [r.proj, r.po].some(x => typeof x === "number" && !Number.isFinite(x))).length;
  const drift = (() => { let w = 0; const idx = {}; for (const r of C.rows) idx[`${r.kind}|${r.match}|${r.player}|${r.market}`] = r; for (const r of logRows().filter(r => r.slate === D.meta.slate)) { const l = idx[`${r.kind}|${r.match}|${r.player}|${r.market}`]; if (l && l.proj != null && r.proj != null) w = Math.max(w, Math.abs(l.proj - r.proj)); } return w; })();
  live.push(["Legs with no projection (should be 0)", nofit], ["Non-finite projections or probabilities (should be 0)", errs], ["Largest |live Proj − frozen Log Proj| (≈0 at default settings; grows as you edit Matches/Config)", num(drift, 3)]);
  const ck = (name, d) => `<h3>${name}</h3><div class="tw"><table><tbody>${d.checks.filter(c => !c.live).map(c => c.name === "Issue" ? `<tr><td class="l warn">Issue</td><td class="l">${esc(c.value)}</td></tr>` : `<tr><td class="l">${esc(c.name)}</td><td class="l">${esc(c.value ?? "")}</td></tr>`).join("")}</tbody></table></div>`;
  const sect = s => `<h3>${esc(s.name)}</h3><p class="sub">${esc(s.blurb)}</p>` + (s.fields ? `<div class="tw"><table><thead><tr><th class="l">Group</th><th class="l">Fields</th><th class="l">Notes</th></tr></thead><tbody>${
    s.fields.map(f => `<tr>${f.map(x => `<td class="l" style="white-space:normal">${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : "") +
    (s.table ? `<div class="tw"><table><thead><tr>${s.table.head.map(h => `<th class="l">${esc(h)}</th>`).join("")}</tr></thead><tbody>${s.table.rows.map(r => `<tr>${r.map(x => `<td class="l" style="white-space:normal">${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : "") +
    (s.warn ? `<p><b>Reliability.</b></p><ul>${s.warn.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : "");
  return `<h2>Data</h2><p class="sub">The integrity checks run on this slate's captures, live checks on the model in your browser, and the data dictionary.</p>
    <h3>Live checks</h3><div class="tw"><table><tbody>${live.map(([a, b]) => `<tr><td class="l">${esc(a)}</td><td class="l">${esc(b)}</td></tr>`).join("")}</tbody></table></div>
    <div class="two"><div>${ck("FPS workbook · Data_Checks", D.fps)}</div><div>${ck("MOBA workbook · Data_Checks", D.moba)}</div></div><div class="doc">${DICT.map(sect).join("")}</div>`;
};

// ---------- Config ----------
const CFGNOTE = {
  fps: {SHRINK_MAPS: "Maps of the player's OWN overall KPR mixed into each per-map KPR. 0 = trust the per-map number fully; 20 = nearly ignore maps. Judgment, not measured (per-map samples are 3–9 maps).",
    KILLS_DISPERSION: "Variance ÷ mean for a kills total; sets the spread behind P(over). 1.0 = Poisson. 1.4 from the Kill_Share_Decomposition test. Headshots inherit it through binomial thinning.",
    EDGE_MIN: "Model side shows OVER/UNDER only past 50% + this. A PAPER column.", DEFAULT_ROUNDS_CS2: "Rounds per CS2 map when Thunderpick posts no ladder (used when the workbook was built).", DEFAULT_ROUNDS_VAL: "Same for Valorant.",
    KPR_ROUND_ELASTICITY: "Kills-per-round dilution on long maps: projection × (rounds ÷ REF)^this. Ships off (0): the slope did not replicate.", REF_ROUNDS_CS2: "Reference CS2 map length for the elasticity.", REF_ROUNDS_VAL: "Same for Valorant.",
    THIN_SAMPLE_MAPS: "Flag a player whose PickFinder sample is below this many maps.", DIFF_WEIGHT: "Round-differential layer (CS2): adjusted kills = base × multiplier^this. 1 = full, 0 = off. Never scored forward.",
    PROJ_MODE: "0 = the published KPR x rounds projection. 1 = career kills per map (no map names, no rounds; HS through his overall HS%). Added 2026-10-19; the kills-per-map version is also logged beside the projection as Proj KPM whatever this says.",
    KILLS_PER_ROUND_WON: "Team kills per round WON (CS2), from team_kills = a·won + b·lost, R² 0.970 on 47 team-maps.", KILLS_PER_ROUND_LOST: "Team kills per round LOST (CS2). The 2.6× ratio is the whole differential effect."},
  moba: {WL_RATIO_LOL: "LoL kills in map WINS ÷ LOSSES. Median 2.21 on 25 players (range 1.20–4.16).", WL_RATIO_DOTA: "Dota: same quantity, median 1.77 on 28 players (OpenDota, last 40 CM games each).",
    KILLS_DISPERSION_LOL: "Variance ÷ mean of kills WITHIN a known map result (LoL); the win/loss mixture variance is added on top. Judgment, not measured.", KILLS_DISPERSION_DOTA: "Same for Dota, measured: 1.84.",
    EDGE_MIN: "Model side shows OVER/UNDER only past 50% + this. PAPER.", THIN_SAMPLE_MAPS: "Flag players whose PickFinder sample is below this many maps."}};
Pages["Config"] = () => {
  const blk = (k, title) => `<h3>${title}</h3><div class="tw"><table><thead><tr><th class="l">Setting</th><th>Value</th><th>Workbook</th><th class="l">Notes</th></tr></thead><tbody>${Object.keys(D[k].config).map(n =>
    `<tr><td class="l">${n}</td><td><input class="ovr" data-cfg="${k}:${n}" value="${cfg(k)[n]}" size="7"></td><td class="mut">${D[k].config[n]}</td><td class="l" style="white-space:normal;min-width:420px">${esc(CFGNOTE[k][n] || "")}</td></tr>`).join("")}</tbody></table></div>`;
  return `<h2>Config</h2><p class="sub">The workbooks' shaded Config cells. Edits recalculate every projection and are saved on this device only. <button id="cfgreset">reset all to workbook values</button></p>${blk("fps", "FPS — CS2 + Valorant")}${blk("moba", "MOBA — LoL + Dota 2")}`;
};

Pages["Methodology"] = () => `<div class="doc"><h2>Methodology</h2>
  <div class="banner"><b>Both models are PAPER.</b> Model side and P(over) are an ordering, not an edge, until the Log says otherwise. The Log (frozen at build) is the forward record neither model had before.</div>
  <h3>FPS — CS2 and Valorant</h3>
  <p>Kills and headshots, built map by map: per-map KPR × the rounds you expect on that map.</p>
  <p><b>Per-map KPR</b> = (n × map KPR + SHRINK_MAPS × overall KPR) ÷ (n + SHRINK_MAPS), with n the maps he has on that map in PickFinder's sample. A map he has never played uses his overall KPR. <b>Kills on map k</b> = per-map KPR × rounds on map k; Maps 1-2 = map 1 + map 2; Maps 1-3 = maps 1-2 + P(map 3) × map 3.
  <b>HS on map k</b> = kills × per-map HS%, shrunk the same way (CS2 only: PickFinder posts no Valorant HS%). <b>P(over)</b> = a normal approximation with variance = KILLS_DISPERSION × projection, continuity-corrected, so a whole-number line shows its push probability separately.</p>
  <p>Valorant: PickFinder gives per-map kills but not per-map KPR, so the sheet converts with the player's average map length (kills/map ÷ kills/round), assuming his maps run equally long.</p>
  <p><b>Maps and rounds.</b> Maps come from PickFinder's Map Picks (a likelihood of a map appearing, not the veto: confirm Map 1 and Map 2 before lock). Rounds come from Thunderpick's Total Rounds ladder for that map, read at its 50% crossing. The posted per-map total is the default because it is the market's number, not because it forecasts well: in this project's record it is 0-for-3 forward and ran ~16% short of realised on slate 33.</p>
  <p><b>Round-differential layer (CS2), the “adj” columns.</b> A team scores ~4.76 kills per round it WINS and ~1.82 per round it LOSES. A player's KPR was earned at his team's historical round share; tonight he plays at a different one. Adj kills = kills × (a·s + b·(1−s)) ÷ (a·s_hist + b·(1−s_hist)), with s from HLTV's conditional margins weighted by Thunderpick's map-winner odds. Round differential is the largest effect in the record (+34 points over-rate gap); this is the first, untested, pre-game handle on it.</p>
  <h3>MOBA — LoL and Dota 2</h3>
  <p>One measured effect: players score about twice as many kills in map wins as in losses (25 of 25 LoL players, median 2.2×). With K̄ his kills per map, q his map win rate and r = WL_RATIO: k_win = K̄·r ÷ (q·r + 1 − q), k_loss = K̄ ÷ (q·r + 1 − q) — these reproduce K̄ exactly at his own win rate.
  <b>Map kills</b> = env × (P(win)·k_win + (1 − P(win))·k_loss); Maps 1-3 sums over maps × P(map played). <b>Spread</b> = within-result variance DISPERSION × mean, plus the win/loss mixture P(1−P)(k_win − k_loss)² — which is why a LoL leg is wider than its average suggests.</p>
  <p>Dota uses its own ratio (1.77) and dispersion (1.84), both measured on OpenDota. Players flagged “new roster” played most of their recent games with other teammates: their K̄ and q were earned elsewhere. A likely sweep does NOT suppress LoL kills (6.60 vs 6.64, p = 0.69): do not cut a leg on sweep risk. Price alone predicted almost nothing (dog 43.1% over, fav 53.7%); if the adjustment carries information it is through each player's own q, which is exactly what Naive vs Proj isolates.</p>
  <h3>How this site relates to the workbooks</h3>
  <p>The browser runs a line-for-line port of each workbook's Calc and Projections tabs on the workbook's own inputs. A test reproduces every projection, sigma, P(over), P(under), P(push), side and adj value the workbooks computed (299 legs, 3,500+ numbers, to 1e-8). Each slate the workbooks are rebuilt from fresh captures and imported here; your Matches and Config edits are per device and never change the record.</p></div>`;

// ---------- shell ----------
let page = "Projections";
function render(keep, focusId) {
  const y = window.scrollY, act = document.activeElement, keepAct = keep && act && act.dataset && (act.dataset.act || act.dataset.cfg) ? act : null;
  view().innerHTML = Pages[page]();
  if (keep) {
    window.scrollTo(0, y);
    let el = focusId ? document.getElementById(focusId) : null;
    if (!el && keepAct) el = document.querySelector(keepAct.dataset.act ? `[data-act="${CSS.escape(keepAct.dataset.act)}"]` : `[data-cfg="${CSS.escape(keepAct.dataset.cfg)}"]`);
    if (el) { el.focus(); const v = el.value; el.setSelectionRange?.(v.length, v.length); }
  }
}
function nav() { document.getElementById("nav").innerHTML = TABS.map(t => `<a href="#${t}" class="${t === page ? "on" : ""}">${t}</a>`).join(""); }
function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  const next = TABS.includes(h) ? h : "Projections";
  if (next !== page) window.scrollTo(0, 0);
  page = next; nav(); render();
}
window.addEventListener("hashchange", route);
(async function init() {
  const get = async f => (await fetch(`data/${f}.json`, {cache: "no-cache"})).json();
  try {
    [D.meta, D.fps, D.moba] = await Promise.all(["meta", "fps", "moba"].map(get));
    await Promise.all(D.meta.slates.map(async s => { D.logs[s] = await get(`log/${s}`); }));
    try { D.eval = await get("evaluation"); } catch (e) { D.eval = null; }
    try { D.odds = await get("odds"); } catch (e) { D.odds = null; }
  } catch (e) { view().innerHTML = `<p class="bad">Could not load data (${esc(e.message)}). Run <code>python -m pipeline.import_xlsx</code>.</p>`; return; }
  document.getElementById("asof").textContent = `${D.meta.slate} slate · FPS built ${D.meta.fps_built} UTC · ${D.meta.moba_legs ? `MOBA built ${D.meta.moba_built} UTC` : "no LoL/Dota workbook today"}`;
  const b = document.getElementById("banner");
  b.innerHTML = `<b>PAPER.</b> ${D.meta.fps_legs} FPS legs (${D.meta.fps_matches} matches)${D.meta.moba_legs ? ` and ${D.meta.moba_legs} MOBA legs (${D.meta.moba_matches} matches)` : ""}. Model side and P(over) are an ordering, not an edge, until the Log has a record.`;
  b.hidden = false;
  route();
})();
