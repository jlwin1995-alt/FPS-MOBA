"""P(over)/P(under) for a posted line given a projection. Python twin of site/model.js `sides` (site/test/parity.mjs keeps them equal)."""
import math
from . import config as C


def norm_cdf(z):
    return 0.5 * math.erfc(-z / math.sqrt(2))


def sigma(stat, m, sd=None):
    """Spread to use: the player's own empirical sd, never below the stat's floor or a share of the projection."""
    base = sd if sd else 0.0
    return max(base, C.SD_FLOOR[stat], C.SD_REL_FLOOR * abs(m))


def sides(line, m, sd):
    """(P(over), P(under)) with no push: kills are integers, so a whole-number line has a push band that is renormalised away,
    exactly as a book's de-vigged price is conditional on no push."""
    line = float(line)
    if line == int(line):
        o, u = 1 - norm_cdf((line + 0.5 - m) / sd), norm_cdf((line - 0.5 - m) / sd)
    else:
        o = 1 - norm_cdf((line - m) / sd)
        u = 1 - o
    t = o + u
    return (o / t, u / t) if t > 0 else (0.5, 0.5)


def implied(dec):
    """Decimal odds -> implied probability (with vig)."""
    try:
        d = float(dec)
    except (TypeError, ValueError):
        return None
    return 1 / d if d > 1 else None


def devig2(da, db):
    """Two-way decimal odds -> vig-free probabilities (multiplicative)."""
    a, b = implied(da), implied(db)
    if a is None or b is None:
        return None, None
    t = a + b
    return a / t, b / t
