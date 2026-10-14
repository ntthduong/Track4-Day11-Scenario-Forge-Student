"""Check submission provenance, arithmetic and untouched supplied simulator files."""
import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from avsim import core, space, studio
from lab11 import estimate, feasible, policy
import numpy as np

E = ROOT/'evidence'
def read(n):
    return json.loads((E/f'{n}.json').read_text(encoding='utf-8'))
def close(a,b):
    assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12),(a,b)

identifier = '2A202602905'
nat,seeds = space.student_variant(identifier)
meta=read('meta')
assert meta['seeds']==seeds
assert (ROOT/'REPORT.md').read_text(encoding='utf-8').splitlines()[0]==f'MSSV: {identifier}'
budgets=dict(replay_n=400,mc_n=3000,iters=8,per_iter=300,final_n=600,seeds=3,fix_n=400,progress_n=256,mine_n=1500)
for name in ('world','replay','mc','hunt','estimate','fix','mine'):
    doc=read(name)
    assert doc['_run']['mssv']==identifier
    assert doc['_run']['town']==meta['_run']['town']
    assert doc['_run']['quick'] is False and doc['_run']['salted'] is False
    assert doc['_run']['budgets']==budgets
    assert meta['steps'][name]['quick'] is False

mc=read('mc')
close(mc['p'],mc['crashes']/mc['n'])
assert sum(mc['modes'].values())==mc['crashes']
lo,hi=estimate.wilson_ci(mc['crashes'],mc['n'])
close(lo,mc['lo']); close(hi,mc['hi'])
est=read('estimate')
assert est['budget']==16800 and len(est['seeds'])==3
for s in est['seeds']:
    close(s['total'],sum(p['p'] for p in s['per'].values())+est['other']['p'])
    for p in s['per'].values():
        assert p['n']==600 and 0<=p['ess']<=600+1e-8 and 0<=p['top_share']<=1
        if not p['hits']:
            close(p['upper_zero_hits'],3/(0.2*p['n']))
fx=read('fix')
assert fx['chosen']==policy.choose_policy(fx['table'],fx['baseline_train']['progress'])
assert fx['chosen']['progress']>=0.95*fx['baseline_train']['progress']
assert json.loads((ROOT/'policy_candidates.json').read_text())==[
    {'cautionV':5.0},{'cautionV':6.5},{'cautionV':6.0},{'cautionV':9.0},{'cautionV':8.5},
    {'cutinLat':2.6},{'cutinLat':3.0},{'cutinLat':3.3},{'T':2.0},
    {'cutinLat':3.0,'cautionV':6.5},{'cutinLat':3.0,'cautionV':7.0},
    {'cutinLat':2.6,'cautionV':7.0,'pedBuffer':3.5}]
hz=studio.load(ROOT/'hazard.json')
assert not studio.check_space(hz)
assert feasible.is_feasible(hz['params']) and studio.hazard_ok(hz['hazards'],hz['params'])
r=core.rollout(hz['params'],policy=hz['policy'],hazards=hz['hazards'])
mn=read('mine')
assert mn['exact']['planner']==[[e['a'],e['b'],e['t']] for e in r.events[0]]
assert mn['accepted']>=0.5
for name in ('baseline','chosen'):
    d=mn[name]
    assert d['crashes']==d['avoidable']+d['unavoidable']+d['unattributed']
    assert d['low_speed']<=d['crashes']
    assert d['n']+d['overlap_at_start']+mn['infeasible']==1500
    close(d['p'],d['avoidable']/d['n'])
    close(d['per_trip'],hz['exposure']*d['p'])
assert mn['baseline']['avoidable']>0
assert hz['exposure']==1 and 'not an observed real-world frequency' in hz['why']

original='9b5d9607d393505293f45e890f212093d7576d82'
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',original],cwd=ROOT,text=True).splitlines()
protected=[p for p in paths if p.startswith(('avsim/','viewer/')) or p in
           ('run_all.py','policy_candidates.json','tests/test_parity.py','tests/test_todos.py','tests/js_dump.js')]
for p in protected:
    old=subprocess.check_output(['git','show',f'{original}:{p}'],cwd=ROOT).replace(b'\r\n',b'\n')
    assert old==(ROOT/p).read_bytes().replace(b'\r\n',b'\n'),f'Protected file changed: {p}'

report=(ROOT/'REPORT.md').read_text(encoding='utf-8')
for n in range(1,10):
    assert f'## {n}.' in report
for p in ('bus_bypass.png','crosswalk_block.png','policy-comparison.png','hazard-bike.png'):
    assert (E/'shots'/p).exists(),f'Missing screenshot: {p}'

test=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,text=True,capture_output=True)
(E/'test-results.txt').write_text(test.stdout+test.stderr,encoding='utf-8')
assert test.returncode==0,test.stdout+test.stderr
assert '44 passed' in test.stdout,test.stdout
def fingerprint(p):
    data=p.read_bytes()
    if p.suffix in ('.json','.txt'):
        data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()
manifest={str(p.relative_to(E)).replace('\\','/'):fingerprint(p)
          for p in sorted(E.rglob('*')) if p.is_file() and p.name not in ('validation.json','manifest.json')}
(E/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
result=dict(mssv=identifier,town=meta['_run']['town'],seeds=seeds,quick=False,salted=False,
            environment=dict(python=platform.python_version(),numpy=np.__version__,
                             node=subprocess.check_output(['node','--version'],text=True).strip()),
            all_budget_checks=True,policy_selected_from_train=True,hazard_valid=True,
            exact_scene_reproduced=True,accepted=mn['accepted'],protected_files_unchanged=protected,
            tests_command=f'{sys.executable} -m pytest -q',tests_passed=44,
            test_output='test-results.txt',evidence_hashes='manifest.json',
            hash_convention='SHA-256; JSON/TXT CRLF normalized to LF, binary files unchanged',
            real_world_exposure='not measured; exposure=1 is the controlled test protocol',
            grading_note='Public and extra tests passed; hidden grader and final grade are external.')
(E/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
