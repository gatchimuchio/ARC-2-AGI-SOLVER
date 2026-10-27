"""Prospective border-cued congruent-body rays. Input grids/programs only.

GRAMMAR.md is authoritative; no teacher, target, task identifier, fitting core,
production solver, query loader or score access occurs in this module.
"""
from collections import Counter
from copy import deepcopy
import traceback
from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid
from 接続.ARC2.既存正方形座標 import d4_motif_transform_coord
from 接続.ARC2.既存凡例穴対応 import clone_grid, grid_shape

PROGRAMS = (4, 8)
TRANSFORMS = tuple('rot'+str(r)+suffix for r in (0,90,180,270) for suffix in ('','_flip_h'))
RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError)

class BudgetExhausted(RuntimeError):
    pass


def valid_grid(g):
    return (isinstance(g,list) and 1<=len(g)<=30 and isinstance(g[0],list)
            and 1<=len(g[0])<=30 and all(isinstance(row,list) and len(row)==len(g[0])
            and all(type(v)is int and 0<=v<=9 for v in row) for row in g))


def render(grid, connectivity, budget=200000, fault=None):
    rec=dict(program=connectivity,status='RUNNING',complete=False,steps=0,
             components=[],bodies=[],cues=[],body_pairs=[],scans=[],factors=[],
             cue_consensus=[],proposals=[],failures=[])
    def tick(stage):
        rec['active_stage']=stage
        rec['steps']+=1
        if fault is not None:
            fault(stage,rec['steps'])
        if rec['steps']>budget:
            raise BudgetExhausted('operational checkpoint budget exhausted')
    def failure(code,**details):
        rec['failures'].append(dict(failure=code,**details))
    def finish(output):
        rec.update(status='HOLD' if output is None else 'OK',complete=True)
        rec.pop('active_stage',None)
        return output,rec
    try:
        tick('validate')
        if type(connectivity)is not int or connectivity not in PROGRAMS:
            failure('invalid_program');return finish(None)
        if type(budget)is not int or budget<0:
            failure('invalid_operational_budget');return finish(None)
        if not valid_grid(grid):
            failure('invalid_arc_grid');return finish(None)
        h,w=grid_shape(grid)
        counts=Counter(v for row in grid for v in row)
        modes=sorted(v for v,n in counts.items()if n==max(counts.values()))
        rec['background_candidates']=modes
        if len(modes)!=1:
            failure('background_tie');return finish(None)
        bg=modes[0];rec['background']=bg
        rec['extraction']=dict(primitive='accepted mixed_region_dicts_for_grid',complete=False,
            interruption_boundary='Legacy extraction is atomic; internal incomplete traversal is unavailable')
        tick('component_extraction')
        components=mixed_region_dicts_for_grid(grid,bg,include_diagonal=connectivity==8)
        rec['extraction']['complete']=True
        owner={};cue_at={}
        for index,comp in enumerate(components):
            raw=dict(index=index,cells=[list(p)for p in comp['cells']],bbox=list(comp['bbox']),
                colors=comp['colors'],size=comp['size'])
            rec['components'].append(raw)
            tick('component_roles')
            if comp['size']==1:
                r,c=comp['cells'][0];normals=[]
                if r==0:normals.append([1,0])
                if r==h-1:normals.append([-1,0])
                if c==0:normals.append([0,1])
                if c==w-1:normals.append([0,-1])
                cue=dict(id=len(rec['cues']),component=index,cell=[r,c],color=grid[r][c],normals=normals)
                rec['cues'].append(cue);cue_at[r,c]=cue
                raw['role']='cue';raw['role_id']=cue['id']
                if not normals:failure('interior_singleton',cue=cue['id'])
            else:
                t,l,b,r=comp['bbox']
                own=set(comp['cells'])
                crop=[[grid[rr][cc]if(rr,cc)in own else bg for cc in range(l,r+1)]for rr in range(t,b+1)]
                body=dict(id=len(rec['bodies']),component=index,bbox=list(comp['bbox']),
                    cells=[list(p)for p in comp['cells']],crop=crop)
                rec['bodies'].append(body);raw['role']='body';raw['role_id']=body['id']
                for p in comp['cells']:owner[p]=body['id']
        bodies=rec['bodies'];cues=rec['cues']
        rec['foreground_ownership']=[dict(cell=[r,c],role='body',id=i)for (r,c),i in sorted(owner.items())]+[dict(cell=[r,c],role='cue',id=v['id'])for (r,c),v in sorted(cue_at.items())]
        foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
        if set(owner)|set(cue_at)!=foreground or set(owner)&set(cue_at):
            failure('foreground_ownership_incomplete')
        if len(bodies)<2:failure('fewer_than_two_bodies')
        if not cues:failure('no_cues')
        maps={}
        for source in bodies:
            sh,sw=grid_shape(source['crop'])
            for target in bodies:
                pair=dict(source=source['id'],target=target['id'],comparisons=[],matching=[])
                rec['body_pairs'].append(pair);maps[source['id'],target['id']]=pair['matching']
                target_cells={(r-target['bbox'][0],c-target['bbox'][1],grid[r][c])for r,c in target['cells']}
                for transform in TRANSFORMS:
                    comparison=dict(transform=transform,complete=False)
                    pair['comparisons'].append(comparison)
                    tick('body_d4_comparison')
                    transformed=sorted((*d4_motif_transform_coord(sh,sw,transform,r-source['bbox'][0],c-source['bbox'][1]),grid[r][c])for r,c in source['cells'])
                    match=set(transformed)==target_cells
                    comparison.update(transformed_colored_cells=[list(p)for p in transformed],matches=match,complete=True)
                    if match:pair['matching'].append(transform)
                pair['complete']=True
                if not pair['matching']:failure('bodies_not_congruent',source=source['id'],target=target['id'])
        for cue in cues:
            for normal in cue['normals']:
                scan=dict(id=len(rec['scans']),cue=cue['id'],inward=normal,
                    corridor=[],hit=None,failure=None,complete=False)
                rec['scans'].append(scan)
                dr,dc=normal;r,c=cue['cell'];r+=dr;c+=dc
                while 0<=r<h and 0<=c<w:
                    tick('cue_inward_scan')
                    if grid[r][c]!=bg:
                        scan['hit']=dict(cell=[r,c],color=grid[r][c],body=owner.get((r,c)),cue=cue_at.get((r,c),{}).get('id'))
                        break
                    scan['corridor'].append([r,c]);r+=dr;c+=dc
                if scan['hit']is None:scan['failure']='cue_has_no_foreground_hit'
                elif scan['hit']['body']is None:scan['failure']='cue_hits_cue'
                if scan['failure']:failure(scan['failure'],scan=scan['id'])
                scan['complete']=True
        for scan in rec['scans']:
            if scan['failure']:
                # This failed declared normal remains in the program; no replacement.
                continue
            cue=cues[scan['cue']];source=bodies[scan['hit']['body']]
            sh,sw=grid_shape(source['crop'])
            lr,lc=(scan['hit']['cell'][a]-source['bbox'][a]for a in (0,1))
            odr,odc=(-x for x in scan['inward'])
            for target in bodies:
                factor=dict(scan=scan['id'],cue=cue['id'],source=source['id'],target=target['id'],
                            alternatives=[],failures=[],complete=False)
                rec['factors'].append(factor)
                transforms=maps[source['id'],target['id']]
                if not transforms:factor['failures'].append('no_exact_transform')
                for transform in transforms:
                    alt=dict(transform=transform,ray=[],failures=[],complete=False)
                    factor['alternatives'].append(alt)
                    tick('directed_port_transform')
                    ar,ac=d4_motif_transform_coord(sh,sw,transform,lr,lc)
                    nr,nc=d4_motif_transform_coord(sh,sw,transform,lr+odr,lc+odc)
                    dr,dc=nr-ar,nc-ac
                    r,c=ar+target['bbox'][0],ac+target['bbox'][1]
                    alt.update(port=[r,c],outward=[dr,dc],color=cue['color'])
                    r+=dr;c+=dc
                    while 0<=r<h and 0<=c<w:
                        tick('outward_ray')
                        alt['ray'].append([r,c])
                        if grid[r][c]!=bg and not ((r,c)in cue_at and grid[r][c]==cue['color']):
                            alt['failures'].append(dict(failure='ray_original_foreground_collision',cell=[r,c],
                                color=grid[r][c],body=owner.get((r,c)),cue=cue_at.get((r,c),{}).get('id')))
                        r+=dr;c+=dc
                    alt['ray']=sorted(alt['ray'])
                    alt['complete']=True
                if any(a['failures']for a in factor['alternatives']):factor['failures'].append('retained_transform_failed')
                if factor['alternatives'] and any(a['ray']!=factor['alternatives'][0]['ray']for a in factor['alternatives'][1:]):
                    factor['failures'].append('retained_transform_disagreement')
                factor['complete']=True
                for why in factor['failures']:failure(why,scan=scan['id'],target=target['id'])
        cue_proposals={}
        for cue in cues:
            item=dict(cue=cue['id'],normal_proposals=[],failures=[],complete=False)
            rec['cue_consensus'].append(item)
            for scan in [s for s in rec['scans']if s['cue']==cue['id']]:
                tick('cue_normal_consensus')
                factors=[f for f in rec['factors']if f['scan']==scan['id']]
                valid=not scan['failure']and len(factors)==len(bodies)and all(not f['failures']for f in factors)
                cells=sorted({tuple(p)for f in factors for a in f['alternatives']for p in a['ray']})
                item['normal_proposals'].append(dict(scan=scan['id'],complete=True,valid=valid,cells=[list(p)for p in cells]))
            ns=item['normal_proposals']
            if not ns or any(not n['valid']for n in ns):item['failures'].append('retained_normal_failed')
            if ns and any(n['cells']!=ns[0]['cells']for n in ns[1:]):item['failures'].append('retained_normal_disagreement')
            item['complete']=True
            for why in item['failures']:failure(why,cue=cue['id'])
            if not item['failures']:cue_proposals[cue['id']]=ns[0]['cells']
        proposed={}
        for cid,cells in cue_proposals.items():
            for p in cells:
                tick('simultaneous_proposal')
                proposed.setdefault(tuple(p),set()).add(cues[cid]['color'])
        rec['proposals']=[dict(cell=list(p),colors=sorted(v))for p,v in sorted(proposed.items())]
        conflicts=[p for p in rec['proposals']if len(p['colors'])!=1]
        rec['conflicts']=conflicts
        if conflicts:failure('simultaneous_color_conflict')
        if rec['failures']:return finish(None)
        tick('clone_and_paint')
        output=clone_grid(grid)
        for (r,c),colors in proposed.items():output[r][c]=next(iter(colors))
        tick('preservation_checks')
        rec['preserved_foreground']=all(output[r][c]==grid[r][c]for r,c in foreground)
        rec['preserved_outside_proposals']=all(output[r][c]==grid[r][c]for r in range(h)for c in range(w)if(r,c)not in proposed)
        rec['changed_cells']=[[r,c]for r in range(h)for c in range(w)if output[r][c]!=grid[r][c]]
        if not rec['preserved_foreground']or not rec['preserved_outside_proposals']:
            failure('preservation_failed');return finish(None)
        if not rec['changed_cells']:
            failure('no_change_after_all_alternatives');return finish(None)
        return finish(output)
    except (BudgetExhausted,)+RESOURCE_ERRORS as e:
        rec.update(status='RESOURCE_INCOMPLETE',complete=False,exception=repr(e))
        return None,rec
    except Exception as e:
        rec.update(status='ERROR_INCOMPLETE',complete=False,exception=repr(e),traceback=traceback.format_exc())
        return None,rec

