"use strict";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const num = (x, d = 1) => x == null || x === "" || Number.isNaN(+x) ? "" : Number(x).toFixed(d);
const pct = (x, d = 1) => x == null || Number.isNaN(+x) ? "" : (x * 100).toFixed(d) + "%";
const store = {
  get(k, d) { try { const v = localStorage.getItem("em_" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("em_" + k, JSON.stringify(v)); } catch (e) {} },
};

// ---------- generic sortable table: cols [{k, h, l, t, v(row)->sortKey, f(row)->html}] ----------
function table(cols, rows, {sort = null, id = "t", rowClass = null} = {}) {
  const st = table.state[id] || (table.state[id] = {key: sort?.key, asc: sort?.asc ?? false});
  const sorted = [...rows];
  const col = cols.find(c => c.k === st.key);
  if (col) {
    const g = col.v || (r => r[col.k]);
    sorted.sort((a, b) => {
      const x = g(a), y = g(b);
      if (x == null || x === "") return 1;
      if (y == null || y === "") return -1;
      return (typeof x === "string" ? x.localeCompare(y) : x - y) * (st.asc ? 1 : -1);
    });
  }
  const head = cols.map(c => `<th class="${c.l ? "l" : ""} ${c.k === st.key ? "s " + (st.asc ? "asc" : "") : ""}" data-k="${c.k}" title="${esc(c.t || "")}">${c.h}</th>`).join("");
  const body = sorted.map(r => `<tr class="${rowClass ? rowClass(r) : ""}">` + cols.map(c => `<td class="${c.l ? "l" : ""}">${c.f ? c.f(r) : esc(r[c.k])}</td>`).join("") + "</tr>").join("");
  return `<div class="tw" data-tid="${id}"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
table.state = {};
document.addEventListener("click", e => {
  const th = e.target.closest("th[data-k]");
  if (!th) return;
  const id = th.closest("[data-tid]").dataset.tid, st = table.state[id], k = th.dataset.k;
  st.asc = st.key === k ? !st.asc : false; st.key = k;
  render(true);
});

function spark(a) {
  if (!a || a.length < 2) return "";
  const w = 70, h = 18, mx = Math.max(...a, 1), mn = Math.min(...a, 0), step = w / (a.length - 1);
  const pts = a.map((v, i) => `${(i * step).toFixed(1)},${(h - 1 - (v - mn) / (mx - mn || 1) * (h - 2)).toFixed(1)}`).join(" ");
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>`;
}
const signed = (x, d = 1) => x == null || x === "" ? "" : `<span class="${x > 0 ? "good" : x < 0 ? "bad" : "mut"}">${x > 0 ? "+" : ""}${num(x, d)}</span>`;
const pc1 = (h, n) => n ? `${(h / n * 100).toFixed(1)}% <span class="mut">(${h}/${n})</span>` : "—";
const card = (v, label) => `<div class="card"><b>${v}</b><span>${label}</span></div>`;
