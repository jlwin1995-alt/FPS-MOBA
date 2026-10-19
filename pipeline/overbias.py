"""Does correcting the model's over-lean raise the side-call hit rate?   python -m pipeline.overbias
Leave-one-slate-out: each correction is fitted on the other slates and applied to the held-out one, over every graded FPS leg in the Log.
Rules: the published side (projection vs line); a shift by the mean projection error; a shift per market class (kills / HS); a scale by actual/projection;
a threshold that calls over as often as legs actually go over; and a shrink toward the line (least squares of actual-line on projection-line).
Result on 2026-10-16..19 (599 legs): none beats 51.2%, the published side is 50.1%; see docs/over-bias-test.md."""
import json,statistics as st
import glob, os
S=tuple(sorted(os.path.basename(p)[:-5] for p in glob.glob('site/data/log/20*.json')))
rows=[]
for s in S:
    for r in json.load(open(f'site/data/log/{s}.json'))['fps']:
        if r.get('Result') in ('OVER','UNDER') and r.get('Proj') is not None:
            rows.append(dict(slate=s,match=r['Match'],mk=r['Market'],hs='HS' in r['Market'],line=r['Line'],act=r['Actual'],proj=r['Proj'],over=r['Result']=='OVER',cl=s+'|'+r['Match']))
print(len(rows),'legs')
def fit(train):
    """parameters learned on the training legs only"""
    d=st.mean(r['proj']-r['act'] for r in train)                                   # mean projection error
    dk={k:st.mean(r['proj']-r['act'] for r in train if r['hs']==k) for k in (False,True)}
    ratio=st.mean(r['act'] for r in train)/st.mean(r['proj'] for r in train)
    q=sum(r['over'] for r in train)/len(train)                                       # actual over rate
    gap=sorted(r['proj']-r['line'] for r in train)
    t=gap[int(round((1-q)*len(gap)))-1] if q<1 else gap[0]                           # threshold so that a share q of training legs would be called over
    # shrink toward the line: beta by least squares of (act-line) on (proj-line)
    xs=[r['proj']-r['line'] for r in train]; ys=[r['act']-r['line'] for r in train]
    mx,my=st.mean(xs),st.mean(ys); beta=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
    return dict(d=d,dk=dk,ratio=ratio,t=t,beta=beta,alpha=my-beta*mx)
RULES={
 'baseline (proj vs line)':lambda r,p:(r['proj']-r['line'],0),
 'shift by mean proj error':lambda r,p:(r['proj']-p['d']-r['line'],0),
 'shift per market class (kills/HS)':lambda r,p:(r['proj']-p['dk'][r['hs']]-r['line'],0),
 'scale by actual/proj ratio':lambda r,p:(r['proj']*p['ratio']-r['line'],0),
 'threshold at actual over-rate':lambda r,p:(r['proj']-r['line']-p['t'],0),
 'shrink toward line (beta,alpha)':lambda r,p:(p['alpha']+p['beta']*(r['proj']-r['line']),0),
}
def evaluate(name,f,rows_by):
    hits=tot=ov=0; per={}
    for s in S:
        test=[r for r in rows if r['slate']==s]; train=[r for r in rows if r['slate']!=s]
        p=fit(train); h=n=0
        for r in test:
            if r['act']==r['line']: continue
            sc,_=f(r,p)
            if sc==0: continue
            n+=1; h+=((sc>0)==r['over']); ov+=sc>0
        per[s]=(h,n); hits+=h; tot+=n
    return hits,tot,ov,per
base=None
print(f"{'rule (leave-one-slate-out)':36} {'hit':>10} {'overs called':>13}   by slate")
for name,f in RULES.items():
    h,n,ov,per=evaluate(name,f,rows)
    print(f"{name:36} {h:4}/{n:<4}={h/n:5.1%} {ov/n:12.0%}   "+' '.join(f"{a}/{b}={a/b:.0%}" for a,b in per.values()))
p=fit(rows); print('full-sample parameters:',{k:(round(v,3) if not isinstance(v,dict) else {str(a):round(b,3) for a,b in v.items()}) for k,v in p.items()})
