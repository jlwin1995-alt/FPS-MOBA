// Run in the browser console (or paste as a bookmarklet body) on an HLTV MATCH page, e.g. https://www.hltv.org/matches/<id>/<teams>
// after the match has finished. It opens each map's stats page from your own tab, reads the player tables, and prints one JSON capture.
// Copy the printed JSON. Nothing is sent anywhere; this reads pages the way you would.
// HLTV changes its layout now and then: if a table is missing or a number does not parse, this stops and says so instead of guessing.
(async () => {
  const num = s => { const n = parseInt(String(s).replace(/[^0-9-]/g, ""), 10); if (Number.isNaN(n)) throw new Error("not a number: " + s); return n; };
  const links = [...new Set([...document.querySelectorAll('a[href*="/stats/matches/mapstatsid/"]')].map(a => a.href))];
  if (!links.length) throw new Error("no map-stats links on this page: is the match finished?");
  const teams = [...document.querySelectorAll(".team .teamName")].slice(0, 2).map(e => e.textContent.trim());
  if (teams.length !== 2) throw new Error("could not read the two team names");
  const maps = [];
  for (const [i, url] of links.entries()) {
    const doc = new DOMParser().parseFromString(await (await fetch(url, {credentials: "same-origin"})).text(), "text/html");
    const tables = [...doc.querySelectorAll("table.stats-table.totalstats")];
    if (tables.length !== 2) throw new Error("map " + (i + 1) + ": expected 2 player tables, found " + tables.length);
    const scores = [...doc.querySelectorAll(".match-info-box .team-left .bold, .match-info-box .team-right .bold")].map(e => num(e.textContent));
    if (scores.length !== 2) throw new Error("map " + (i + 1) + ": could not read the map score");
    const mapName = (doc.querySelector(".match-info-box .small-text")?.previousSibling?.textContent || doc.querySelector(".match-info-box")?.textContent.match(/\b(Ancient|Anubis|Dust2|Inferno|Mirage|Nuke|Overpass|Train|Vertigo|Cache|Cobblestone)\b/)?.[1] || "").trim();
    if (!mapName) throw new Error("map " + (i + 1) + ": could not read the map name");
    const players = [];
    for (const t of tables) {
      const team = t.querySelector("th .teamName, th.st-teamname")?.textContent.trim();
      if (!team) throw new Error("map " + (i + 1) + ": no team name on a player table");
      for (const r of t.querySelectorAll("tbody tr")) {
        const name = r.querySelector(".st-player a")?.textContent.trim();
        const k = r.querySelector(".st-kills")?.textContent;        // "19 (3)" = kills (headshots)
        const d = r.querySelector(".st-deaths")?.textContent;
        if (!name || !k || !d) throw new Error("map " + (i + 1) + ": a player row is missing a cell");
        const m = k.match(/(\d+)\s*\((\d+)\)/);
        if (!m) throw new Error("map " + (i + 1) + ": kills (hs) did not parse: " + k);
        players.push({name, team, kills: +m[1], hs: +m[2], deaths: num(d)});
      }
    }
    maps.push({n: i + 1, map: mapName, score: scores, players});
  }
  const cap = {schema: 1, source: "hltv.org", url: location.href, captured_utc: new Date().toISOString(), teams, maps};
  console.log(JSON.stringify(cap));
  return cap;
})().catch(e => console.error("CAPTURE STOPPED:", e.message));
