"""Read a concrete reactive counterexample from the existing TRAIN draws only."""
import json
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from avsim import core,space,viewer
from lab11 import estimate,feasible,metrics,modes,search
E=ROOT/'evidence'
meta=json.loads((E/'meta.json').read_text())
nat,seeds=space.student_variant(meta['_run']['mssv'])
h=json.loads((E/'hunt.json').read_text())['bus_bypass']['proposal']
prop={k:np.array(v) if k in ('mean','std','p_bin') else v for k,v in h.items()}
z,b=search.mixture_sample(prop,nat,400,np.random.default_rng(seeds['search']+11),0.2)
params=space.to_params(z,b,nat)
weights=np.exp(estimate.log_weights(z,b,nat,prop,0.2))
indices=[i for i,p in enumerate(params) if feasible.is_feasible(p)]
ps=[params[i] for i in indices]
n=len(ps)
r=core.rollout(ps+ps,policy=[{}]*n+[{'cautionV':5.0}]*n)
cases=[]
for k,i in enumerate(indices):
    e=metrics.ego_events(r,k+n)
    if not metrics.ego_events(r,k) and e and modes.label_mode(r,k+n,e[0],metrics.contact_type)=='bus_bypass':
        cases.append((weights[i],k,i,e[0]))
assert cases,'No baseline-safe/cautious-failing TRAIN example found.'
w,k,i,e=max(cases,key=lambda c:c[0])
def details(index):
    c2start=np.flatnonzero(np.abs(r.F[index,:,core.C2,6])>0.05)
    leader=np.flatnonzero(r.EGO[index,:,3]==core.C2)
    return dict(events=metrics.ego_events(r,index),
                first_c2_lateral_move_t=float(c2start[0]*core.DT) if len(c2start) else None,
                first_c2_leader_t=float(leader[0]*core.DT) if len(leader) else None,
                at_cautious_contact=dict(t=e['t'],ego=r.F[index,e['f'],core.EGO,:].tolist(),
                                         c2=r.F[index,e['f'],core.C2,:].tolist()))
doc=dict(source='Supplementary reading of the original bus_bypass TRAIN importance draws; no TEST tuning',
         seed=seeds['search']+11,n_draws=400,draw_index=i,weight=float(w),params=params[i],
         baseline=details(k),cautious_policy={'cautionV':5.0},cautious=details(k+n))
(E/'caution_counterexample.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
viewer.export(str(E/'caution_viewer.json'),[dict(id='TRAIN-166-caution5',label='bus_bypass',params=params[i])],
              policy={'cautionV':5.0},baseline_policy={},title=meta['_run']['mssv']+': TRAIN reactive counterexample')
print(json.dumps(doc,ensure_ascii=False,indent=2),flush=True)
