"use strict";
// What is captured each slate and the ways each source has produced a wrong number that looked right.
// Condensed from the "Esports Data Dictionary" doc (field lists read from the 10-16 capture and 10-15 settlement files).
const DICT = [
  {name: "Board and lines — PickFinder raw API", blurb: "One record per prop, about 300 a day, captured once before the first lock. The POP test reads it.",
   fields: [
     ["Prop", "player, team, opponent, stat, line, alt-line flag, start time, league, tournament, position", "Stats: Maps 1-2 Kills, Maps 1-2 HS, Map 1 Kills, Map 1 HS, Maps 1-3 Kills"],
     ["Other apps", "over/under price and line on each app, with a timestamped line history", "PrizePicks (the census), Underdog, Sleeper, Betr, ParlayPlay, DK Pick6"],
     ["Hit rates", "L5, L10, L15, season, H2H hits and games, average of the last 10, difference vs line, streak", "PickFinder's own counts, 15 series deep at most"],
     ["Market", "team and opponent moneyline and implied %, the book it came from", "Often missing for Bo1s and small events"],
     ["Popularity", "favourite counts over and under, most-favoured side", "Used by the POP test"],
     ["Other", "defence rank, consensus implied probability", "Consensus was 0 on the legs checked"]],
   warn: ["It under-counts the PrizePicks board on some fixtures. PrizePicks itself is the census.", "The 20-row page cap has reset itself in the middle of a pass.",
          "The tab has hard-reloaded in the middle of a pass. The capture now saves after each player and resumes.", "Lines have sometimes differed from the card by 0.5.",
          "In Bo1 groups one player appears in several matches a day, so every join has to key on the team pair."]},
  {name: "Player stats — PickFinder player pages", blurb: "One page per board player, captured at build time.",
   fields: [
     ["CS2", "Overview (maps, kills per map, K/D, HLTV rating, HS %, HS per map), the same per round, a per-map table, and a Map Picks panel (pick, ban and win % per map)", "Last 30 days on Map Picks"],
     ["LoL, Dota, Valorant", "Game log, one row per series: date, opponent, then kills, assists, deaths, first pick, CS, damage and HS for map 1, 2, 3, maps 1-2 and maps 1-3", "15 series"]],
   warn: ["M1 + M2 = M1-2 is a free check on every row. It has passed every time it has been run.", "Some Valorant players show an average of the last 10 with every hit-rate column empty: a sample too thin to use.",
          "Old games can sit inside the window (BerLIN's 15 rows ran back 19 months), so the recency check has to be run.", "Yesterday's games show up in today's L5 when the same teams play again."]},
  {name: "Team and match data — HLTV (CS2 only)", blurb: "One analytics record per CS2 match on the board, plus announced lineups.",
   fields: [
     ["Per team", "two summary round-margin figures; for each of the seven maps, the average round margin in maps won and in maps lost", ""],
     ["Per team, per map", "pick %, ban %, win % and maps played", ""],
     ["Lineups", "the five announced players per team", "A flag, not a check"]],
   warn: ["Announced lineups are a flag, not a check: wrong three times out of three on 10-14; on 10-15 they missed both real no-shows. Starters are verified from the map roster tables at settlement.",
          "Name aliases differ by site (MartinezSa and Martinez).", "The site sits behind Cloudflare; it is read in a browser tab that is allowed to clear on its own, never routed around."]},
  {name: "Odds — Thunderpick", blurb: "One sportsbook, captured once before lock with decimal odds on every selection: about 860 distinct market names.",
   fields: [
     ["Match", "match winner, match handicap, total maps over/under, correct match score, maps odd/even", "Winner on every match, handicap on about half"],
     ["Map winner", "Map N winner, 1X2 per map, match-and-map combos, team wins at least one map", ""],
     ["Round totals (CS2, Valorant)", "total rounds per map, per-team total rounds, overtime yes/no, rounds odd/even, combos", ""],
     ["Round margin (CS2, Valorant)", "round handicap per map, winning margin, correct round score, first-half and second-half handicaps", ""],
     ["In-map props", "pistol rounds, CT and T round totals, first to N, utility-kill yes/no; Roshan, runes, barons, dragons, inhibitors, multi-kills", "Varies"],
     ["Player props", "per-map kills and headshot kills, player-vs-player kill duels", "A handful of matches a day"]],
   warn: ["Sign conventions vary: the market-level handicap field meant the away side on some CS2 fixtures and the home side on Valorant. Key the ladder on each selection's own handicap.",
          "Round Handicap (Incl. Overtimes) is match level; Round Handicap (Incl. Overtime) - Map 1 is map 1. The wrong one gives clean-looking ladders.",
          "Bo1s and qualifiers often post the winner only, and some matches aren't priced at all; check every match.", "Different fixtures sometimes carry identical round ladders to three decimals.",
          "Posted round totals have failed as a forecast twice (08-13 and 08-25).", "The capture tab has frozen and been replaced with a fresh one."]},
  {name: "Results sources", blurb: "Every title settles from per-map box scores the next day, with a second route or an internal identity check.",
   table: {head: ["Title", "Primary source", "Check", "Known failure"], rows: [
     ["CS2", "bo3.gg per-map tables", "HLTV match page totals (81 of 82 legs exact on 10-15)", "No player stats for some qualifiers; double-headers; aliases"],
     ["CS2, fallback", "HLTV mapstats", "CT + T must equal the map total", "The first parser read the T half as the total"],
     ["Valorant", "vlr.gg", "The all-maps tab must equal the sum of the maps", "Empty cells parsed as 0"],
     ["LoL", "gol.gg per game", "Team header must equal the sum of the players; Leaguepedia as a second source", "Pages exist before stats post and read as 0 players"],
     ["Dota", "OpenDota", "Sum of player kills must equal the team score, within 1", "One Bo3 can be split across two series ids"]]}},
  {name: "Known gaps", blurb: "The biggest are odds history and draft context.",
   table: {head: ["Gap", "Status", "Possible source"], rows: [
     ["Closing lines and line movement at the book", "Missing: Thunderpick is one snapshot before lock", "Re-capture near lock"],
     ["A second sportsbook", "Missing", "—"],
     ["LoL champion and draft data", "Available, not captured", "gol.gg champion list"],
     ["Valorant team map stats", "Available, not captured", "vlr.gg team stats page"],
     ["Dota hero and role context", "Missing beyond position", "OpenDota match data (not checked)"],
     ["Player history beyond 15 series", "Missing on PickFinder", "Settlement sites' player pages (gol.gg has 51-143 games a season)"]]}},
];
