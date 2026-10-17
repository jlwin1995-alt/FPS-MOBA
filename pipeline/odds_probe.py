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
    req = urllib.request.Request(f"{BASE}/{path}?{q}", headers={"User-Agent": "fps-moba-odds-probe", "Accept": "application/json"})
    time.sleep(0.6)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read()
            return r.status, json.loads(body) if body else None, None
    except urllib.error.HTTPError as e:
        return e.code, None, e.read()[:300].decode("utf-8", "replace")
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
        if with_odds:
            fid = with_odds[0].get("fixtureId") or with_odds[0].get("id")
            st, od, err = call("odds", key, fixtureId=fid)
            log(f"odds {title} fixture {fid}", st, od, err)
            seen = sorted(names(od)) if od is not None else []
            report[f"{title}_market_names"] = seen[:200]
            report[f"{title}_player_or_kill_markets"] = [n for n in seen if KEYWORDS.search(n)][:50]
    json.dump(report, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in report.items() if k.endswith(("_fixtures", "_player_or_kill_markets")) or k == "sport_ids"}, indent=1))


if __name__ == "__main__":
    main()
