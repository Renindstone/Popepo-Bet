import sys, time, itertools, json
import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ekf_eval import *
df = load()
res = []
def go(**kw):
    t = time.time()
    pred = run_ekf(df, **kw)
    ll, llou, n = evaluate(df, pred, "2016-07-01", "2021-07-01")
    llf, _, _ = evaluate(df, pred, "2016-07-01", "2021-07-01", divs=FULL)
    res.append({**kw, "ll": ll, "ll_ou": llou, "ll_full": llf})
    print(json.dumps(res[-1]), round(time.time() - t), flush=True)
    return ll
best = {}
for q, b in itertools.product([1e-5, 3e-5, 1e-4], [0.0, 0.01, 0.03]):
    go(q=q, b=b)
r0 = min(res, key=lambda x: x["ll"]); q, b = r0["q"], r0["b"]
for r in [0.1, 0.25]:
    go(q=q, b=b, r=r)
r1 = min(res, key=lambda x: x["ll"]); rr = r1.get("r", 0.0)
for qlg in [0.0, 1e-5, 5e-5]:
    go(q=q, b=b, r=rr, q_lg=qlg)
r2 = min(res, key=lambda x: x["ll"]); qlg = r2.get("q_lg", 2e-6)
for no in [0.0, -0.3]:
    go(q=q, b=b, r=rr, q_lg=qlg, new_offset=no)
print("BEST", json.dumps(min(res, key=lambda x: x["ll"])))
