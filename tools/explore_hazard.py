"""Design-stage hazard sweep; does not read TEST or write submission evidence."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from avsim import core, studio

base = dict(civil=True, cutGap=12, pedGap=4.5, pedLook=1,
            cutT0=6.5, cutDur=4, pedT0=11, busGo=17)
hazards = [dict(type="bike", x=65, lane="E2", d=0.7, v=5.5,
                swerve=3.4, swDur=2.7, t0=0, trig=25)]
params = [dict(base, h0_x=x, h0_trig=trig)
          for x in (25, 45, 65, 85, 105) for trig in (12, 18, 24, 30, 36)]
r = core.rollout(params, hazards=hazards)
avoids, frames, foreknown = studio.oracle_avoids(params, r, hazards)
for k, p in enumerate(params):
    events = [e for e in r.events[k] if "ego" in (e["a"],e["b"])]
    if events:
        e = events[0]
        print(dict(x=p['h0_x'], trig=p['h0_trig'], other=e['b'], t=e['t'],
                   avoidable=bool(avoids[k]), brake_frame=int(frames[k]),
                   foreknown=bool(foreknown[k])), flush=True)
