"""Offline checks of the maths and the model plumbing.  python -m pipeline.selftest [--dump]   (--dump prints the probability fixtures site/test/parity.mjs compares against)"""
import json, sys
from . import config as C
from . import model as M
from . import prob

GRID = [(line, m, sd) for line in (0.5, 4, 9.5, 17.5, 33.5, 34) for m in (3, 8.4, 17, 34.2) for sd in (1.5, 3.1, 6.0)]


def main():
    if "--dump" in sys.argv:
        print(json.dumps([dict(line=l, m=m, sd=s, over=prob.sides(l, m, s)[0], under=prob.sides(l, m, s)[1]) for l, m, s in GRID]))
        return
    for l, m, s in GRID:
        o, u = prob.sides(l, m, s)
        assert abs(o + u - 1) < 1e-12 and 0 <= o <= 1, (l, m, s)
    assert prob.sides(10.5, 12, 3)[0] > 0.5 > prob.sides(10.5, 9, 3)[0]
    assert abs(prob.sides(10.5, 10.5, 3)[0] - 0.5) < 1e-9
    a, b = prob.devig2(1.5, 2.6)
    assert abs(a + b - 1) < 1e-12 and a > b
    assert prob.devig2(1.0, 2.0) == (None, None)
    assert prob.sigma("M12K", 40, 0) >= max(C.SD_FLOOR["M12K"], 0.12 * 40)
    # stats: a 2-0 series has no maps 1-3 value, and is not counted as 0
    row = dict(m1_k="20", m2_k="15", m3_k="", m1_hs="9", m2_hs="7", m3_hs="")
    assert M.series_value(row, "M12K") == 35 and M.series_value(row, "M123K") is None and M.series_value(row, "M12HS") == 16
    # recency cut and thin sample
    logs = [dict(title="CS2", player="p", date=d, m1_k="10", m2_k="10") for d in ("2024-01-01", "2026-09-01", "2026-09-05")]
    assert [d for d, _ in M.player_history(logs, "CS2", "p", "M12K", "2026-10-01")] == ["2026-09-05", "2026-09-01"]
    assert M.project([20.0] * 3, 18.0, "M12K") is None
    p = M.project([30.0] * 15, 20.0, "M12K")
    assert 20 < p["proj"] < 30 and abs(p["proj"] - (15 * 30 + C.SHRINK_N * 20) / (15 + C.SHRINK_N)) < 1e-9
    print("selftest ok")


if __name__ == "__main__":
    main()
