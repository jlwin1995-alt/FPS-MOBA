"""What does OddsPapi actually offer for the four titles?  Run by .github/workflows/odds-probe.yml with the ODDSPAPI_KEY secret.

    ODDSPAPI_KEY=... python -m pipeline.odds_probe [--out odds_probe.json]

Read-only and polite (a pause between calls, nothing retried past a 429). Prints and saves a structural summary: the sports list, the markets seen on upcoming
fixtures for CS2 / Valorant / LoL / Dota 2, and whether any market name mentions kills, headshots or players. The key is never printed (query strings are masked).
The documentation is not reachable from the build environment, so endpoint names follow OddsPapi's public tutorials and every call reports its status instead of assuming.
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://api.oddspapi.io/v4"
KEYWORDS = re.compile(r"kill|headshot|\bhs\b|player|assist|death|ace|clutch", re.I)
TITLES = {"CS2": 17, "LoL": 18}               # sport ids named in OddsPapi's esports post; Valorant and Dota are looked up from /sports by name


def call(path, key, **params):
    q = urllib.parse.urlencode({**params, "apiKey": key})
    for attempt in range(4):
        req = urllib.request.Request(f"{BASE}/{path}?{q}", headers={"User-Agent": "fps-moba-odds-probe", "Accept": "application/json"})
        time.sleep(1.5)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
                return r.status, json.loads(body) if body else None, None
        except urllib.error.HTTPError as e:
            text = e.read()[:300].decode("utf-8", "replace")
            if e.code == 429 and attempt < 3:                  # the API says how long to wait; honour it (capped), do not hammer
                m = re.search(r'"retryMs":\s*(\d+)', text)
                time.sleep(min(int(m.group(1)) / 1000 if m else 2, 6) + 0.5)
                continue
            return e.code, None, text
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            return None, None, str(e)[:300]


def shape(x, depth=0):
    """A short description of a JSON value: keys and a sample, never the whole thing."""
    if isinstance(x, dict):
        return {k: shape(v, depth + 1) for k, v in list(x.items())[:12]} if depth < 3 else f"dict({len(x)})"
    if isinstance(x, list):
        return [shape(x[0], depth + 1), f"... {len(x)} items"] if x and depth < 3 else f"list({len(x)})"
    return x if not isinstance(x, str) else x[:60]


def names(x, out=None):
    """Every string under a 'name'-like key, to see which markets exist."""
    out = set() if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, str) and re.search(r"name|market|outcome|description", k, re.I):
                out.add(v[:80])
            else:
                names(v, out)
    elif isinstance(x, list):
        for v in x[:400]:
            names(v, out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="odds_probe.json")
    a = ap.parse_args()
    key = os.environ.get("ODDSPAPI_KEY")
    if not key:
        sys.exit("ODDSPAPI_KEY is not set")
    report = dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), calls=[])

    def log(label, st, data, err):
        report["calls"].append(dict(call=label, status=st, error=err, shape=shape(data) if data is not None else None))
        print(f"{label}: {st}{' ' + str(err) if err else ''}")

    st, sports, err = call("sports", key)
    log("sports", st, sports, err)
    ids = dict(TITLES)
    for s in (sports if isinstance(sports, list) else (sports or {}).get("data", []) if isinstance(sports, dict) else []):
        n = str(s.get("sportName") or s.get("name") or "")
        for t, pat in (("Valorant", "valorant"), ("Dota 2", "dota"), ("CS2", "counter"), ("LoL", "league")):
            if re.search(pat, n, re.I):
                ids[t] = s.get("sportId") or s.get("id")
    report["sport_ids"] = ids
    today = dt.date.today()
    for title, sid in ids.items():
        st, fx, err = call("fixtures", key, sportId=sid, **{"from": today.isoformat(), "to": (today + dt.timedelta(days=2)).isoformat()})
        log(f"fixtures {title} ({sid})", st, fx, err)
        rows = fx if isinstance(fx, list) else (fx or {}).get("data", []) if isinstance(fx, dict) else []
        with_odds = [r for r in rows if isinstance(r, dict) and r.get("hasOdds")]
        report[f"{title}_fixtures"] = dict(total=len(rows), with_odds=len(with_odds))
        seen_all = set()
        for fx_row in with_odds[:3]:
            fid = fx_row.get("fixtureId") or fx_row.get("id")
            st, od, err = call("odds", key, fixtureId=fid)
            log(f"odds {title} fixture {fid}", st, od, err)
            seen_all |= names(od) if od is not None else set()
        if with_odds:
            seen = sorted(n for n in seen_all if not re.fullmatch(r"[0-9a-f:-]{6,}|\d+", n))     # drop ids, keep market and outcome names
            report[f"{title}_market_names"] = seen[:200]
            report[f"{title}_player_or_kill_markets"] = [n for n in seen if KEYWORDS.search(n)][:50]
    # raw samples, so a parser can be written against the real structure (one fixture per title that has odds, plus the participant list for CS2)
    raw = {}
    for title, sid in ids.items():
        st, fx, err = call("fixtures", key, sportId=sid, **{"from": today.isoformat(), "to": (today + dt.timedelta(days=2)).isoformat()})
        rows = fx if isinstance(fx, list) else (fx or {}).get("data", []) if isinstance(fx, dict) else []
        raw[f"{title}_fixtures_head"] = rows[:3]
        for fx_row in [r for r in rows if isinstance(r, dict) and r.get("hasOdds")][:1]:
            st, od, err = call("odds", key, fixtureId=fx_row.get("fixtureId"))
            raw[f"{title}_odds_sample"] = od
    for path, kw in (("participants", {"sportId": ids.get("CS2")}), ("markets", {"sportId": ids.get("CS2")}), ("bookmakers", {})):
        st, d, err = call(path, key, **kw)
        log(path, st, d, err)
        raw[f"{path}_head"] = (d[:25] if isinstance(d, list) else d)
    json.dump(raw, open(a.out.replace(".json", "_raw.json"), "w"), indent=1)
    json.dump(report, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in report.items() if k.endswith(("_fixtures", "_player_or_kill_markets")) or k == "sport_ids"}, indent=1))


if __name__ == "__main__":
    main()
