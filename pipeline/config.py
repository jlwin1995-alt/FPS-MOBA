"""Constants shared by the pipeline. Everything the baseline model assumes lives here so it can be swapped for the real model's numbers."""

TITLES = ["CS2", "Valorant", "LoL", "Dota"]
KIND = {"CS2": "FPS", "Valorant": "FPS", "LoL": "MOBA", "Dota": "MOBA"}

# stat key -> (label, maps used, per-map column prefix, needs the maps to all be played)
STATS = {
    "M1K":   dict(label="Map 1 Kills",    maps=(1,),      col="k",  hs=False),
    "M12K":  dict(label="Maps 1-2 Kills", maps=(1, 2),    col="k",  hs=False),
    "M123K": dict(label="Maps 1-3 Kills", maps=(1, 2, 3), col="k",  hs=False),
    "M1HS":  dict(label="Map 1 HS",       maps=(1,),      col="hs", hs=True),
    "M12HS": dict(label="Maps 1-2 HS",    maps=(1, 2),    col="hs", hs=True),
}

# ---- baseline projection (PLACEHOLDER: replace with the real model; see README "Plugging in the real model") ----
W_L5, W_L10, W_REST = 0.40, 0.35, 0.25      # recency weights on the last 5 / series 6-10 / series 11-15
SHRINK_N = 8                                # pseudo-games of the title+stat average blended into every player (more = less trust in a thin sample)
SD_FLOOR = {"M1K": 2.5, "M12K": 3.5, "M123K": 4.5, "M1HS": 1.5, "M12HS": 2.2}
SD_REL_FLOOR = 0.12                         # sd never below this share of the projection
RECENCY_DAYS = 120                          # history older than this is dropped (a player's 15 rows once ran back 19 months)
MIN_GAMES = 4                               # fewer usable series than this -> no projection
LEAN, STRONG = 0.25, 0.5                    # z = (projection - line) / sd

BREAKEVEN = {"2pick": 57.7, "3pick": 59.8, "4pick": 56.2, "5pick": 54.9}   # PrizePicks-style flex/power break-evens, per leg
PP_BE = 57.7
