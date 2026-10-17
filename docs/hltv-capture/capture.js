// Run in the browser console on an HLTV MAP-STATS page (the "Detailed stats" page of one map, URL contains /stats/matches/mapstatsid/).
// It reads the two player tables already on the page and prints one line of JSON for that map. Repeat for each map of the match.
// It does NOT fetch other pages: HLTV answers background requests with 403 (the page you opened yourself loads fine), and that block is not worked around.
// Copy each printed line. Nothing is sent anywhere. If something does not parse it stops and says what, rather than guessing.
(() => {
  try {
    const num = s => { const n = parseInt(String(s).replace(/[^0-9-]/g, ""), 10); if (Number.isNaN(n)) throw new Error("not a number: " + s); return n; };
    const tables = [...document.querySelectorAll("table.stats-table.totalstats")];
    if (tables.length !== 2) throw new Error("expected 2 player tables (class stats-table totalstats), found " + tables.length + ". Is this a map-stats page?");
    const scores = [...document.querySelectorAll(".match-info-box .team-left .bold, .match-info-box .team-right .bold")].map(e => num(e.textContent));
    if (scores.length !== 2) throw new Error("could not read the map score");
    const box = document.querySelector(".match-info-box")?.textContent || "";
    const map = (box.match(/\b(Ancient|Anubis|Dust2|Inferno|Mirage|Nuke|Overpass|Train|Vertigo|Cache|Cobblestone)\b/) || [])[1];
    if (!map) throw new Error("could not read the map name");
    const players = [], teams = [];
    for (const t of tables) {
      const team = t.querySelector("th .teamName, th.st-teamname")?.textContent.trim();
      if (!team) throw new Error("no team name on a player table");
      teams.push(team);
      for (const r of t.querySelectorAll("tbody tr")) {
        const name = r.querySelector(".st-player a")?.textContent.trim();
        const k = r.querySelector(".st-kills")?.textContent;        // "19 (3)" = kills (headshots)
        const d = r.querySelector(".st-deaths")?.textContent;
        if (!name || !k || !d) throw new Error("a player row is missing a cell");
        const m = k.match(/(\d+)\s*\((\d+)\)/);
        if (!m) throw new Error("kills (hs) did not parse: " + k);
        players.push({name, team, kills: +m[1], hs: +m[2], deaths: num(d)});
      }
    }
    const cap = {schema: 1, kind: "map", source: "hltv.org", url: location.href, mapstatsid: +(location.pathname.match(/mapstatsid\/(\d+)/) || [])[1] || null, captured_utc: new Date().toISOString(), teams, map, score: scores, players};
    console.log(JSON.stringify(cap));
  } catch (e) {
    console.error("CAPTURE STOPPED:", e.message);
    console.log("tables on page:", [...document.querySelectorAll("table")].map(t => t.className));
  }
})();
