"use strict";
const TABS = ["Projections", "Match Board", "Lines", "Results", "Scorecard", "Backtest", "Data", "Config", "Methodology"];
const D = {};
const RES = {};
let CFG = store.get("cfg", {be: 57.7, hideStarted: false});
let OVR = store.get("ovr", {});                                  // {legId: projection typed by you}
const F = {q: "", title: "", stat: "", match: "", side: "", strong: false, rdate: "", ldiff: false};
const view = () => document.getElementById("view");
const started = iso => iso && new Date(iso).getTime() <= Date.now();
const koLabel = iso => iso ? new Date(iso).toLocaleString(undefined, {weekday: "short", hour: "numeric", minute: "2-digit"}) : "";
const APP_NAME = {ud: "Underdog", sl: "Sleeper", betr: "Betr", pplay: "ParlayPlay", dk: "DK Pick6"};

// ---------- the model as the browser sees it: pipeline projection (or your override) -> sd -> P(over) ----------
function calc(p) {
  const m = OVR[p.id] != null ? +OVR[p.id] : p.proj;
  if (m == null || p.line == null) return {};
  const sd = EM.sigma(D.meta, p.stat, m, p.sd);
  return withLine(p, m, sd, p.line);
}
function withLine(p, m, sd, line) {
  const [po, pu] = EM.sides(line, m, sd), over = po >= pu, ps = over ? po : pu;
  return {m, sd, po, pu, side: over ? "O" : "U", ps, z: (m - line) / sd, edge: ps * 100 - CFG.be};
}
const rows = () => D.proj.map(p => ({...p, c: calc(p)}));
const tierOf = z => Math.abs(z) >= D.meta.strong ? "strong" : Math.abs(z) >= D.meta.lean ? "lean" : "";
const sidePill = c => c.m == null ? "" : `<span class="pill ${tierOf(c.z) ? "lean-" + tierOf(c.z) : ""}" title="Model side. ${tierOf(c.z) === "strong" ? "STRONG" : tierOf(c.z) === "lean" ? "LEAN" : "No lean"}: z = (projection - line) / sd = ${num(c.z, 2)}">${c.side === "O" ? "OVER" : "UNDER"} ${pct(c.ps, 0)}</span>`;
const flagPills = fl => (fl || []).map(f => ({thin: ["THIN", "Fewer than 8 usable series: the projection leans on the title average."], nohist: ["NO HIST", "Too few usable series to project."],
  lineup: ["NOT IN LINEUP", "Not in the announced lineup. Announced lineups are a flag, not a check: they have been wrong."]}[f] || [f, ""])).map(([t, tip]) => `<span class="pill q" title="${esc(tip)}">${t}</span>`).join(" ");
const warn = e => e != null && Math.abs(e) >= 15 ? ` <span title="An edge this large is usually the model missing something (a role or lineup change, a stand-in, a thin or stale sample), not a bargain. Check before trusting it." style="cursor:help">⚠</span>` : "";
const ovrCell = r => `<input class="ovr" data-id="${esc(r.id)}" value="${OVR[r.id] ?? ""}" placeholder="${num(r.proj)}">`;

// ---------- filters ----------
const sel = (id, label, opts, cur) => `<label>${label} <select id="${id}">${opts.map(([v, t]) => `<option value="${esc(v)}" ${cur === v ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
function filters(extra = "") {
  return `<div class="bar"><input id="q" placeholder="Search player / team" value="${esc(F.q)}">
    ${sel("title", "Title", [["", "All"], ...D.meta.titles.map(t => [t, t])], F.title)}
    ${sel("stat", "Stat", [["", "All"], ...Object.entries(D.meta.stats).map(([k, v]) => [k, v.label])], F.stat)}${extra}</div>`;
}
const passes = r => (!F.title || r.title === F.title) && (!F.stat || r.stat === F.stat) && (!CFG.hideStarted || !started(r.start)) &&
  (!F.q.trim() || (r.player + " " + r.team + " " + r.opp).toLowerCase().includes(F.q.trim().toLowerCase()));
document.addEventListener("input", e => {
  if (e.target.id === "q") { F.q = e.target.value; render(true, "q"); }
  else if (e.target.classList.contains("ovr")) {
    const v = e.target.value.trim(), id = e.target.dataset.id;
    if (v === "" || isNaN(+v)) delete OVR[id]; else OVR[id] = +v;
    store.set("ovr", OVR); render(true, null, id);
  }
});
document.addEventListener("change", e => {
  const k = {title: "title", stat: "stat", match: "match", side: "side", rdate: "rdate"}[e.target.id];
  if (k) { F[k] = e.target.value; if (k === "rdate") { loadRes(F.rdate).then(() => render()); return; } render(); }
  else if (e.target.id === "strong") { F.strong = e.target.checked; render(); }
  else if (e.target.id === "ldiff") { F.ldiff = e.target.checked; render(); }
  else if (e.target.id === "hide") { CFG.hideStarted = e.target.checked; store.set("cfg", CFG); render(); }
  else if (e.target.id === "be") { CFG.be = +e.target.value || 57.7; store.set("cfg", CFG); render(); }
});

// ---------- tabs ----------
function playerCols() {
  return [{k: "player", h: "Player", l: 1}, {k: "title", h: "Title", l: 1}, {k: "team", h: "Team", l: 1},
    {k: "opp", h: "vs", l: 1, f: r => esc(r.opp)}];
}
const Pages = {};

Pages["Projections"] = () => {
  const rs = rows().filter(passes).filter(r => !F.strong || tierOf(r.c.z ?? 0));
  const cols = [...playerCols(), {k: "label", h: "Stat", l: 1},
    {k: "line", h: "Line", f: r => num(r.line)},
    {k: "ovr", h: "Proj OVR", t: "Type your own projection; the probabilities recalculate. Saved on this device.", v: r => OVR[r.id] ?? null, f: ovrCell},
    {k: "m", h: "Proj", t: "Model projection (or your override)", v: r => r.c.m, f: r => num(r.c.m)},
    {k: "diff", h: "Δ", t: "Projection minus line", v: r => r.c.m != null ? r.c.m - r.line : null, f: r => r.c.m != null ? signed(r.c.m - r.line) : ""},
    {k: "ps", h: "Model side", l: 1, v: r => r.c.z != null ? Math.abs(r.c.z) : null, f: r => sidePill(r.c)},
    {k: "edge", h: "Edge", t: "Model probability of its side minus the break-even in Config", v: r => r.c.edge, f: r => r.c.edge != null ? signed(r.c.edge, 1) + "%" + warn(r.c.edge) : ""},
    {k: "sd", h: "SD", f: r => num(r.c.sd)}, {k: "n", h: "N", t: "usable series", f: r => r.n ?? ""},
    {k: "l5", h: "L5", f: r => num(r.l5)}, {k: "avg10", h: "Avg10", t: "PickFinder's average of the last 10", f: r => num(r.avg10)},
    {k: "hr10", h: "HR L10", t: "PickFinder's hit rate over the last 10 series", v: r => r.hr.l10, f: r => r.hr.l10 == null ? "" : r.hr.l10 + "%"},
    {k: "hist", h: "Last 15", t: "Series totals, oldest to newest", f: r => spark(r.hist)},
    {k: "start", h: "Starts", l: 1, v: r => r.start, f: r => koLabel(r.start)}, {k: "flags", h: "Flags", l: 1, f: r => flagPills(r.flags)}];
  return `<h2>Projections</h2><p class="sub">${D.meta.slate} slate · ${rs.length} of ${D.meta.legs} legs. The projection is fixed by the pipeline before lock; type a <b>Proj OVR</b> to test your own number.</p>
    ${filters(`<label><input type="checkbox" id="strong" ${F.strong ? "checked" : ""}> leans only</label><label><input type="checkbox" id="hide" ${CFG.hideStarted ? "checked" : ""}> hide started</label>`)}
    ${table(cols, rs, {id: "proj", sort: {key: "ps", asc: false}, rowClass: r => (started(r.start) ? "started " : "") + (tierOf(r.c.z ?? 0) ? `lean-${tierOf(r.c.z)}-row` : "")})}`;
};

Pages["Match Board"] = () => {
  const ms = D.matches.filter(m => !F.title || m.title === F.title);
  const mid = F.match && ms.find(m => m.id === F.match) ? F.match : ms[0]?.id;
  const m = ms.find(x => x.id === mid);
  const list = table([{k: "start", h: "Starts", l: 1, f: m => koLabel(m.start)}, {k: "title", h: "Title", l: 1},
    {k: "a", h: "Team A", l: 1, f: m => `<a href="#" data-m="${esc(m.id)}">${esc(m.a)}</a>`}, {k: "b", h: "Team B", l: 1},
    {k: "p_a", h: "A win%", t: "Thunderpick moneyline, vig removed", f: m => pct(m.p_a, 0)}, {k: "legs", h: "Legs"}], ms, {id: "ml", sort: {key: "start", asc: true}});
  if (!m) return `<h2>Match Board</h2><p class="sub">No matches on this slate.</p>`;
  const rs = rows().filter(r => r.match === m.id).sort((a, b) => Math.abs(b.c.z ?? 0) - Math.abs(a.c.z ?? 0));
  const lineup = (names, team) => names.length ? names.map(n => `<span class="pill ${rs.some(r => r.player === n) ? "" : "mut"}">${esc(n)}</span>`).join(" ") : `<span class="mut">none announced</span>`;
  const cols = [{k: "player", h: "Player", l: 1}, {k: "team", h: "Team", l: 1}, {k: "label", h: "Stat", l: 1}, {k: "line", h: "Line", f: r => num(r.line)},
    {k: "m", h: "Proj", v: r => r.c.m, f: r => num(r.c.m)}, {k: "ps", h: "Model side", l: 1, v: r => Math.abs(r.c.z ?? 0), f: r => sidePill(r.c)},
    {k: "hist", h: "Last 15", f: r => spark(r.hist)}, {k: "flags", h: "Flags", l: 1, f: r => flagPills(r.flags)}];
  const mg = x => x == null ? "—" : (x > 0 ? "+" : "") + num(x, 2);
  return `<h2>Match Board</h2><p class="sub">Pick a match; both teams' legs ranked by how far the projection is from the line.</p>
    <div class="bar">${sel("match", "Match", ms.map(x => [x.id, `${x.title}: ${x.a} v ${x.b}`]), mid)}${sel("title", "Title", [["", "All"], ...D.meta.titles.map(t => [t, t])], F.title)}</div>
    <div class="gamehead"><div><span>Match</span><b>${esc(m.a)} v ${esc(m.b)}</b></div><div><span>Title</span><b>${esc(m.title)}${m.bo ? " · Bo" + m.bo : ""}</b></div>
      <div><span>Starts</span><b>${koLabel(m.start)}</b></div><div><span>Moneyline (Thunderpick)</span><b>${m.ml_a ?? "—"} / ${m.ml_b ?? "—"}</b></div>
      <div><span>Win% (vig removed)</span><b>${pct(m.p_a, 0) || "—"} / ${pct(m.p_b, 0) || "—"}</b></div>
      <div><span>HLTV round margin (CS2)</span><b>${mg(m.margin_a)} / ${mg(m.margin_b)}</b></div></div>
    <p class="mut">Announced lineups — a flag, not a check:<br>${esc(m.a)}: ${lineup(m.lineup_a)}<br>${esc(m.b)}: ${lineup(m.lineup_b)}</p>
    ${table(cols, rs, {id: "board", sort: {key: "ps", asc: false}})}<h3>All matches</h3>${list}`;
};

Pages["Lines"] = () => {
  const rs = rows().filter(passes).filter(r => Object.keys(r.apps).length).map(r => {
    const all = [["pp", "PrizePicks", r.line], ...Object.entries(r.apps).map(([k, v]) => [k, APP_NAME[k], v])];
    const lo = all.reduce((a, b) => b[2] < a[2] ? b : a), hi = all.reduce((a, b) => b[2] > a[2] ? b : a);
    const at = l => r.c.m == null ? null : withLine(r, r.c.m, r.c.sd, l);
    return {...r, all, lo, hi, spread: hi[2] - lo[2], eo: r.c.m == null ? null : at(lo[2]).po * 100 - CFG.be, eu: r.c.m == null ? null : at(hi[2]).pu * 100 - CFG.be};
  }).filter(r => !F.ldiff || r.spread > 0);
  const app = k => ({k: "a_" + k, h: APP_NAME[k], t: "Line at " + APP_NAME[k], v: r => r.apps[k] ?? null, f: r => r.apps[k] == null ? "" : `<span class="${r.apps[k] < r.line ? "good" : r.apps[k] > r.line ? "bad" : ""}">${num(r.apps[k])}</span>`});
  const cols = [...playerCols().slice(0, 2), {k: "label", h: "Stat", l: 1}, {k: "line", h: "PrizePicks", f: r => num(r.line)}, ...Object.keys(APP_NAME).map(app),
    {k: "m", h: "Proj", v: r => r.c.m, f: r => num(r.c.m)},
    {k: "lo", h: "Best OVER", t: "Lowest line anywhere: the easiest line to go over", v: r => r.lo[2], f: r => `${num(r.lo[2])} <span class="mut">${esc(r.lo[1])}</span>`},
    {k: "eo", h: "OVER edge", t: "P(over) at that line minus the break-even", v: r => r.eo, f: r => r.eo == null ? "" : signed(r.eo) + "%"},
    {k: "hi", h: "Best UNDER", t: "Highest line anywhere: the easiest line to go under", v: r => r.hi[2], f: r => `${num(r.hi[2])} <span class="mut">${esc(r.hi[1])}</span>`},
    {k: "eu", h: "UNDER edge", v: r => r.eu, f: r => r.eu == null ? "" : signed(r.eu) + "%"},
    {k: "spread", h: "Spread", t: "Highest minus lowest line across apps", f: r => num(r.spread)}];
  return `<h2>Lines</h2><p class="sub">Every leg that more than one app posts. Green = a line below PrizePicks (easier OVER), red = above (easier UNDER). Edge is the model's probability at that line minus the ${CFG.be}% break-even.</p>
    ${filters(`<label><input type="checkbox" id="ldiff" ${F.ldiff ? "checked" : ""}> apps disagree only</label>`)}${table(cols, rs, {id: "lines", sort: {key: "spread", asc: false}})}${calcBox()}`;
};
function calcBox() {
  return `<h3>Try a line</h3><div class="bar"><label>Projection <input id="cp" size="5" value="${F.cp ?? ""}"></label><label>SD <input id="cs" size="5" value="${F.cs ?? ""}"></label><label>Line <input id="cl" size="5" value="${F.cl ?? ""}"></label>
    <span id="cout" class="mut"></span></div>`;
}
document.addEventListener("input", e => {
  if (!["cp", "cs", "cl"].includes(e.target.id)) return;
  F[{cp: "cp", cs: "cs", cl: "cl"}[e.target.id]] = e.target.value;
  const m = +F.cp, sd = +F.cs, l = +F.cl, out = document.getElementById("cout");
  if (F.cp && F.cs && F.cl && sd > 0) { const [o, u] = EM.sides(l, m, sd); out.textContent = `P(over) ${pct(o)} · P(under) ${pct(u)} · over edge ${num(o * 100 - CFG.be)}% · under edge ${num(u * 100 - CFG.be)}%`; } else out.textContent = "";
});

async function loadRes(d) { if (d && !RES[d]) RES[d] = await (await fetch(`data/results/${d}.json`)).json(); }
Pages["Results"] = () => {
  const idx = D.resIndex, d = F.rdate && idx.find(x => x.date === F.rdate) ? F.rdate : idx[0]?.date;
  if (!d) return `<h2>Results</h2><p class="sub">No settled slates yet. A slate settles the next day from the per-map box scores.</p>`;
  if (!RES[d]) { loadRes(d).then(() => render()); return `<h2>Results</h2><p class="mut">Loading…</p>`; }
  const R = RES[d], s = R.summary;
  const rs = R.rows.filter(r => (!F.title || r.title === F.title) && (!F.stat || r.stat === F.stat) && (!F.side || (F.side === "hit" ? r.hit === 1 : r.hit === 0)) && (!F.q.trim() || (r.player).toLowerCase().includes(F.q.trim().toLowerCase())));
  const cols = [{k: "player", h: "Player", l: 1}, {k: "title", h: "Title", l: 1}, {k: "label", h: "Stat", l: 1}, {k: "line", h: "Line", f: r => num(r.line)}, {k: "a", h: "Proj", f: r => num(r.a)},
    {k: "naive", h: "Naive", t: "Average of the last 10", f: r => num(r.naive)}, {k: "actual", h: "Actual", f: r => num(r.actual, 0)},
    {k: "err", h: "Error", t: "Projection minus actual", v: r => r.a - r.actual, f: r => signed(r.a - r.actual)},
    {k: "side", h: "Model side", l: 1, f: r => r.side === "O" ? "OVER" : r.side === "U" ? "UNDER" : ""},
    {k: "result", h: "Result", l: 1, f: r => r.result === "O" ? "OVER" : r.result === "U" ? "UNDER" : "PUSH"},
    {k: "hit", h: "Model", l: 1, v: r => r.hit, f: r => r.hit == null ? "" : r.hit ? `<span class="good">✔ hit</span>` : `<span class="bad">✘ miss</span>`}];
  return `<h2>Results</h2><p class="sub">Projected → actual for every leg of a settled slate, using the board frozen before lock.</p>
    <div class="bar">${sel("rdate", "Slate", idx.map(x => [x.date, x.date]), d)}${sel("side", "Model", [["", "All"], ["hit", "Hits"], ["miss", "Misses"]], F.side)}</div>
    <div class="cards">${card(s.n, "legs scored")}${card(pc1(s.hits, s.graded), "model side")}${card(num(s.mae, 2), "MAE · projection")}${card(num(s.mae_naive, 2), "MAE · naive last-10")}${card(num(s.bias, 2), "mean error (proj − actual)")}</div>
    ${filters()}${table(cols, rs, {id: "res", sort: {key: "err", asc: false}})}`;
};

Pages["Scorecard"] = () => {
  const S = D.score, t = S.total;
  if (!t.n) return `<h2>Scorecard</h2><p class="sub">Nothing settled yet.</p>`;
  const row = (k, s) => ({k, ...s});
  const cols = first => [{k: "k", h: first, l: 1}, {k: "n", h: "Legs"}, {k: "hit", h: "Model side", v: r => r.graded ? r.hits / r.graded : null, f: r => pc1(r.hits, r.graded)},
    {k: "mae", h: "MAE proj", f: r => num(r.mae, 2)}, {k: "mn", h: "MAE naive", f: r => num(r.mae_naive, 2)}, {k: "ms", h: "MAE all-games", f: r => num(r.mae_season, 2)},
    {k: "vs", h: "vs naive", t: "Change in error against the naive last-10 average: negative = smaller misses", v: r => r.mae_naive ? r.mae / r.mae_naive - 1 : null,
     f: r => r.mae_naive ? `<span class="${r.mae < r.mae_naive ? "good" : "bad"}">${num((r.mae / r.mae_naive - 1) * 100, 1)}%</span>` : ""}, {k: "bias", h: "Bias", f: r => signed(r.bias, 2)}];
  const tier = {none: "No lean", lean: `LEAN (z ≥ ${S.lean})`, strong: `STRONG (z ≥ ${S.strong})`};
  return `<h2>Scorecard</h2><p class="sub">Projections are frozen before lock and never rewritten, then scored on the next day's box scores against the naive last-10 average and the all-games mean. ${D.meta.sample ? "<b>These are synthetic.</b>" : ""}</p>
    <div class="cards">${card(t.n, "legs scored")}${card(pc1(t.hits, t.graded), "model side")}${card(num(t.mae, 2), "MAE · projection")}${card(num(t.mae_naive, 2), "MAE · naive")}${card(num(t.mae_season, 2), "MAE · all games")}</div>
    <h3>By slate</h3>${table(cols("Slate"), S.days.map(d => row(d.date, d)), {id: "sc_d", sort: {key: "k", asc: false}})}
    <div class="two"><div><h3>By title</h3>${table(cols("Title"), Object.entries(S.by_title).map(([k, v]) => row(k, v)), {id: "sc_t"})}</div>
    <div><h3>By stat</h3>${table(cols("Stat"), Object.entries(S.by_stat).map(([k, v]) => row(D.meta.stats[k].label, v)), {id: "sc_s"})}</div></div>
    <h3>By lean strength</h3><p class="sub">z = (projection − line) ÷ the stat's typical spread. Small samples: a way to sort, not a promise.</p>${table(cols("Tier"), Object.entries(S.tiers).map(([k, v]) => row(tier[k], v)), {id: "sc_l"})}`;
};

Pages["Backtest"] = () => {
  const B = D.bt;
  const cols = [{k: "title", h: "Title", l: 1}, {k: "label", h: "Stat", l: 1}, {k: "n", h: "Projections"}, {k: "mae", h: "MAE model", f: r => num(r.mae, 2)}, {k: "naive", h: "MAE naive", f: r => num(r.naive, 2)},
    {k: "season", h: "MAE all-games", f: r => num(r.season, 2)}, {k: "titlemean", h: "MAE title avg", t: "Predict the title's average for everyone", f: r => num(r.titlemean, 2)},
    {k: "vs", h: "vs naive", v: r => r.mae / r.naive - 1, f: r => `<span class="${r.mae < r.naive ? "good" : "bad"}">${num((r.mae / r.naive - 1) * 100, 1)}%</span>`}, {k: "bias", h: "Bias", f: r => signed(r.bias, 2)}];
  return `<h2>Backtest</h2><p class="sub">Walk-forward over the last ${B.days} days of series: each projection uses only games before that series. The history carries no posted lines, so this scores the projection itself (error), not betting results.</p>
    <div class="cards">${card(B.n, "projections replayed")}${card(num(B.mae, 3), "MAE · model")}${card(num(B.naive, 3), "MAE · naive last-10")}${card(num(B.season, 3), "MAE · all games")}${card(num(B.titlemean, 3), "MAE · title average")}</div>
    ${table(cols, B.rows, {id: "bt", sort: {key: "title", asc: true}})}`;
};

Pages["Data"] = () => {
  const C = D.cov;
  const chk = C.checks.map(c => `<tr><td class="l">${esc(c.name)}</td><td>${c.rows}</td><td>${c.bad ? `<span class="bad">${c.bad}</span>` : `<span class="good">0</span>`}</td><td class="l mut">${esc(c.note)}</td></tr>`).join("");
  const sect = s => `<h3>${esc(s.name)}</h3><p class="sub">${esc(s.blurb)}</p>` + (s.fields ? `<div class="tw"><table><thead><tr><th class="l">Group</th><th class="l">Fields</th><th class="l">Notes</th></tr></thead><tbody>${
    s.fields.map(f => `<tr>${f.map(x => `<td class="l" style="white-space:normal">${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : "") +
    (s.table ? `<div class="tw"><table><thead><tr>${s.table.head.map(h => `<th class="l">${esc(h)}</th>`).join("")}</tr></thead><tbody>${s.table.rows.map(r => `<tr>${r.map(x => `<td class="l" style="white-space:normal">${esc(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : "") +
    (s.warn ? `<p><b>Reliability.</b></p><ul>${s.warn.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : "");
  return `<h2>Data</h2><p class="sub">What a slate captures, how this build checked it, and the ways each source has produced a wrong number that looked right.</p>
    <h3>Checks on this build</h3><div class="tw"><table><thead><tr><th class="l">Check</th><th>Rows</th><th>Failed</th><th class="l">Note</th></tr></thead><tbody>${chk}</tbody></table></div>
    <div class="two"><div><h3>Legs by title</h3>${table([{k: "title", h: "Title", l: 1}, {k: "players", h: "Players"}, {k: "legs", h: "Legs"}], C.titles, {id: "cv_t"})}</div>
    <div><h3>Lines by app</h3>${table([{k: "app", h: "App", l: 1}, {k: "legs", h: "Legs"}], C.apps, {id: "cv_a"})}</div></div>
    <div class="doc">${DICT.map(sect).join("")}</div>`;
};

Pages["Config"] = () => `<h2>Config</h2><div class="bar"><label>Break-even % per leg <input id="be" type="number" step="0.1" value="${CFG.be}" size="5"></label>
    <label><input type="checkbox" id="hide" ${CFG.hideStarted ? "checked" : ""}> hide started legs</label></div>
  <p class="sub">Break-even is the win probability a leg needs to pay: ${CFG.be}% matches a 2-pick entry at PrizePicks-style payouts. Edge columns are the model's probability minus this. Your projection overrides: <b>${Object.keys(OVR).length}</b>
  <button id="clr">Clear all</button></p>`;
document.addEventListener("click", e => { if (e.target.id === "clr") { OVR = {}; store.set("ovr", OVR); render(); }
  const a = e.target.closest("a[data-m]"); if (a) { e.preventDefault(); F.match = a.dataset.m; render(); window.scrollTo(0, 0); } });

Pages["Methodology"] = () => {
  const m = D.meta.model;
  return `<div class="doc"><h2>Methodology</h2>
  <div class="banner"><b>Placeholder model.</b> This site was assembled without access to the working fps/moba model, so the projection below is a plain stand-in with the same inputs and outputs. Replace <code>project()</code> in <code>pipeline/model.py</code> with the real model and every tab follows.</div>
  <h3>What the baseline does</h3>
  <p>For each board leg it takes the player's own usable series (inside the last ${m.recency_days} days, up to 15) and totals the maps the stat covers: <code>Map 1 Kills</code> is map 1, <code>Maps 1-2 Kills</code> is maps 1 + 2, and so on.
  A series where a needed map was not played (a 2-0 has no map 3) is skipped, not zeroed.</p>
  <p>The projection is a recency-weighted mean of the last 5, the next 5 and the last 5 after that (weights ${m.w.join(" / ")}, renormalised over the groups that exist), then shrunk toward the title's average for that stat as if the player had ${m.shrink_n} extra games of average form. Fewer than ${m.min_games} usable series: no projection.</p>
  <h3>Probabilities</h3>
  <p>P(over) is a normal curve around the projection with the player's own series-to-series spread, never below a per-stat floor or ${pct(D.meta.sd_rel_floor, 0)} of the projection. Kills are whole numbers, so a whole-number line has a push band that is renormalised away, as a book's vig-free price is. The browser and the pipeline share this maths and a test keeps them equal.</p>
  <h3>Leans</h3><p>A lean is the projection disagreeing with the line, in units of spread: z ≥ ${D.meta.lean} is a LEAN, z ≥ ${D.meta.strong} is STRONG. Edge is the probability of the model's side minus the break-even in Config.</p>
  <h3>What the checks guard against</h3><p>See the <a href="#Data">Data</a> tab: kill-sum identities, a recency cut so a 19-month-old row cannot sit inside the window, announced lineups treated as a flag not a check, and joins keyed on the team pair for Bo1 groups.</p>
  <h3>What is not modelled</h3><p>No map-pick, pick/ban, round-margin or draft context, no popularity (POP) test, no pace or blowout adjustment, no line movement. The data dictionary lists which of those are captured and which are still gaps.</p></div>`;
};

// ---------- shell ----------
let page = "Projections";
function render(keep, focusId, ovrId) {
  const y = window.scrollY;
  view().innerHTML = Pages[page]();
  if (keep) {
    window.scrollTo(0, y);
    const el = focusId ? document.getElementById(focusId) : ovrId ? document.querySelector(`input.ovr[data-id="${CSS.escape(ovrId)}"]`) : null;
    if (el) { el.focus(); const v = el.value; el.setSelectionRange?.(v.length, v.length); }
  }
}
function nav() { document.getElementById("nav").innerHTML = TABS.map(t => `<a href="#${t.replace(" ", "-")}" class="${t === page ? "on" : ""}">${t}</a>`).join(""); }
function route() {
  const h = decodeURIComponent(location.hash.slice(1)).replace("-", " ");
  const next = TABS.includes(h) ? h : "Projections";
  if (next !== page) window.scrollTo(0, 0);
  page = next; nav(); render();
}
window.addEventListener("hashchange", route);
(async function init() {
  const get = async f => (await fetch(`data/${f}.json?v=${Date.now()}`)).json();
  try {
    [D.meta, D.proj, D.matches, D.cov, D.score, D.bt, D.resIndex] = await Promise.all(["meta", "projections", "matches", "coverage", "scorecard", "backtest", "results/index"].map(get));
  } catch (e) { view().innerHTML = `<p class="bad">Could not load data/*.json (${esc(e.message)}). Run <code>python -m pipeline.build</code>.</p>`; return; }
  document.getElementById("asof").textContent = `${D.meta.slate} slate · built ${new Date(D.meta.generated).toLocaleString()}`;
  const b = document.getElementById("banner"), msg = [];
  if (D.meta.sample) msg.push("<b>SAMPLE DATA.</b> Every player, team and number here is synthetic — the site is running on a made-up league because no capture is in <code>data/raw</code>.");
  msg.push("<b>Placeholder model</b> — see Methodology.");
  b.innerHTML = msg.join(" "); b.hidden = false;
  route();
})();
