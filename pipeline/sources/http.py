"""Polite JSON/HTML fetching for the results sources: a browser-like User-Agent, a small delay between calls, retries on transient errors.
Sites that refuse us (Cloudflare 403, HLTV) are reported as failures and never routed around."""
import json, time, urllib.error, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
_last = {}


class Refused(Exception):
    """The site said no (403/429). Not retried, not worked around."""


def fetch(url, headers=None, delay=0.35, tries=3, timeout=40):
    host = url.split("/")[2]
    for i in range(tries):
        wait = _last.get(host, 0) + delay - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                raise Refused(f"{e.code} from {host}")
            if e.code in (404, 410):
                raise
            err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
        time.sleep(1.5 * (i + 1))
    raise err


def get_json(url, headers=None, **kw):
    return json.loads(fetch(url, headers=headers, **kw))


def get_text(url, headers=None, **kw):
    return fetch(url, headers=headers, **kw).decode("utf-8", "replace")
