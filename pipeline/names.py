"""Name matching between the board (PickFinder / Thunderpick names) and the results sources."""
import re

norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
STOP = {"team", "esports", "esport", "gaming", "club", "gg"}


def board_team_keys(name):
    """'Apogee Esports (BCA)' -> {'apogeeesports', 'apogee', 'bca'}: the full name, the name without filler words, and the tag."""
    tag = re.search(r"\((.*?)\)", name or "")
    base = re.sub(r"\(.*?\)", "", name or "").strip()
    words = [w for w in re.split(r"[^A-Za-z0-9]+", base) if w]
    keys = {norm(base), norm(tag.group(1)) if tag else "", norm("".join(w for w in words if w.lower() not in STOP))}
    return {k for k in keys if len(k) >= 2}


def source_team_keys(*names):
    out = set()
    for n in names:
        words = [w for w in re.split(r"[^A-Za-z0-9]+", n or "") if w]
        out |= {norm(n), norm("".join(w for w in words if w.lower() not in STOP))}
        out |= {norm(w) for w in words if len(w) >= 5 and w.lower() not in STOP}      # 'Betclic Apogee Esports' also answers to 'betclic' and 'apogee'
    return {k for k in out if len(k) >= 2}


def same_team(board_name, *source_names):
    return bool(board_team_keys(board_name) & source_team_keys(*source_names))


def same_player(a, b):
    """Exact on the normalised handle, else one contains the other (dictionary: 'MartinezSa' and 'Martinez')."""
    x, y = norm(a), norm(b)
    return bool(x and y and (x == y or (min(len(x), len(y)) >= 4 and (x in y or y in x))))
