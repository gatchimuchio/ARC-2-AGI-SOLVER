import json
import random
from pathlib import Path
from 接続.ARC2 import 領域指令核 as core
from 接続.ARC2.矢印到達候補 import parse_input
from 接続.ARC2.凡例旋回教材 import guarded_render
from 接続.ARC2.既存格子操作 import transform_grid_by_name

ROOT=Path(__file__).parent
teachers=json.loads((ROOT/'teachers-only.json').read_text())
fitted,record=core.fit_teachers(teachers)
assert fitted
checks=[]
def check(name,value):
    assert value,name
    checks.append(name)
check('all_four_teacher_outputs',all(core.predict(p['input'],fitted)[0]==p['output']for p in teachers))
check('all_sixteen_models_retained',len(fitted.models)==16)
check('arrow_pulse_existing_view_incompatible',all(parse_input(p['input'])[0]is None for p in teachers))
check('legend_turn_existing_view_incompatible',all(guarded_render(p['input'])[0]is None for p in teachers))
# Refit under a deterministic palette permutation; no privileged marker/turn colors.
rng=random.Random(13)
for i in range(10):
    palette=list(range(10));rng.shuffle(palette)
    mapped=[{k:[[palette[v]for v in row]for row in p[k]]for k in ('input','output')}for p in teachers]
    fit,_=core.fit_teachers(mapped)
    check('palette_refit_'+str(i),fit is not None and all(core.predict(p['input'],fit)[0]==p['output']for p in mapped))
# Synthetic split map, right-facing marker, simultaneous transfer preserves source.
g=[[2,2,2,4,4],[2,1,2,4,4],[2,1,1,4,4],[2,1,2,4,4],[2,2,2,4,4]]
expected=[[2]*5 for _ in range(5)]
check('synthetic_right_transfer',core.predict(g,fitted)[0]==expected)
for name in core.TURNS:
    check('synthetic_direction_'+name,core.predict(transform_grid_by_name(g,name),fitted)[0]==transform_grid_by_name(expected,name))
broken=[row[:]for row in g];broken[0][0]=1
check('unowned_marker_holds',core.predict(broken,fitted)[0]is None)
edge=[[2,2,2],[2,1,2],[2,1,1],[2,1,2],[2,2,2]]
check('out_of_bounds_ray_holds',core.predict(edge,fitted)[0]is None)
# Two same-color target components must remain independent.
g=[[2,2,2,4,4],[2,1,2,4,4],[2,1,1,4,4],[2,1,2,4,4],[2,2,2,4,4],[5,5,5,5,5],[4,4,4,4,4]]
expected=[[2]*5 for _ in range(5)]+[[5]*5,[4]*5]
check('disconnected_same_color_target_preserved',core.predict(g,fitted)[0]==expected)
# Reflect an observed scene to move its top corner cue to an unobserved bottom corner.
flipped=transform_grid_by_name(teachers[0]['input'],'flip_v')
output,why=core.predict(flipped,fitted)
check('unseen_turn_corner_holds',output is None and why.get('reason')=='retained_output_disagreement')
# Teacher target corruption cannot become a lookup or output patch.
changed=json.loads(json.dumps(teachers));changed[0]['output'][0][0]=(changed[0]['output'][0][0]+1)%10
check('corrupt_teacher_no_fit',core.fit_teachers(changed)[0]is None)
# Independent audit's synthetic two-cover case: a failed interpretation cannot vanish.
probe=json.loads((ROOT/'synthetic-cover-regression.json').read_text())
scenes,failure=core.parse(probe,1,9)
check('failed_cover_not_dropped',not scenes and failure=='eligible_cover_ray_out_of_bounds')
check('failed_cover_prediction_holds',core.predict(probe,fitted)[0]is None)
result={'successful':True,'checks':checks,'count':len(checks),'teacher_exact':4,'retained_models':len(fitted.models),'existing_view_failures':{'arrow_pulses':[parse_input(p['input'])[1]['reason']for p in teachers],'legend_turn':[guarded_render(p['input'])[1]['failure']for p in teachers]}}

print(json.dumps(result,indent=2))
