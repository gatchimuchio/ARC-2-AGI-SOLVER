"""Generic marker-enclosure-conditioned residual registration.
Input-only components/cue roles, all-teacher shape correspondences, observed-key
HDS action relation. No task identifiers, fixed outputs, or coordinate priors.
Declared rendering prior: translate sparse masks, crop to canvas before writing.
"""
from collections import Counter
from itertools import product
from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid
from 接続.ARC2.既存疎点転写 import shifted_sparse_point_mask
from hds学習系統 import HDS学習実行系, 最小排気系
from hds学習系統.型 import 学習入力, 観測事実


def observation(values,boundary):
    return 学習入力(原入力=values,対象系境界=boundary,観測群=tuple(観測事実((k,),v,type(v).__name__,True) for k,v in values.items()))


def enclosed(cells,marker,cavity_diagonal):
    """Whether the marker-erased complement pocket reaches bbox exterior (C4 or C8)."""
    body=set(cells)-{marker}
    if not body:return False
    r0=min(r for r,c in body)-1;r1=max(r for r,c in body)+1
    c0=min(c for r,c in body)-1;c1=max(c for r,c in body)+1
    todo=[marker];seen={marker}
    while todo:
        r,c=todo.pop()
        if r<=r0 or r>=r1 or c<=c0 or c>=c1:return False
        for dr,dc in ((-1,0),(1,0),(0,-1),(0,1)) + (((-1,-1),(-1,1),(1,-1),(1,1)) if cavity_diagonal else ()):
            p=r+dr,c+dc
            if p not in body and p not in seen:seen.add(p);todo.append(p)
    return True


def interpretations(g,diagonal,cavity_diagonal):
    h,w=len(g),len(g[0]);counts=Counter(v for row in g for v in row)
    backgrounds=[v for v,n in counts.items() if n==max(counts.values())]
    scenes=[]
    for bg in backgrounds:
        components=mixed_region_dicts_for_grid(g,bg,diagonal)
        cues=[o for o in components if o['size']==1 and any(r in (0,h-1) or c in (0,w-1) for r,c in o['cells'])]
        objects=[o for o in components if o not in cues]
        if not cues or not objects:continue
        for axis in (0,1):
            tangent=1-axis;choices=[]
            for obj in objects:
                hist=Counter(g[r][c] for r,c in obj['cells']);bindings=[]
                for cue in cues:
                    q=tuple(next(iter(cue['cells'])));color=g[q[0]][q[1]]
                    if q[tangent] not in (0,(h,w)[tangent]-1) or hist[color]!=1:continue
                    marker=next(p for p in obj['cells'] if g[p[0]][p[1]]==color)
                    marker=tuple(marker);tsign=1 if q[tangent]>marker[tangent] else -1
                    if q[tangent]==marker[tangent]:continue
                    nsign=-tsign if axis==0 else tsign
                    base=[0,0];base[axis]=q[axis]-marker[axis]
                    bindings.append(dict(obj=obj,marker=marker,cue=q,feature=enclosed(obj['cells'],marker,cavity_diagonal),base=base,axis=axis,tsign=tsign,nsign=nsign))
                if not bindings:break
                choices.append(bindings)
            if len(choices)==len(objects):
                for bound in product(*choices):scenes.append(dict(bg=bg,cues=cues,bound=bound,diagonal=diagonal))
    return scenes


def correspondence(g,y,scene):
    if (len(g),len(g[0]))!=(len(y),len(y[0])):return None
    target=[row[:] for row in y];bg=scene['bg']
    for cue in scene['cues']:
        for r,c in cue['cells']:
            if y[r][c]!=g[r][c]:return None
            target[r][c]=bg
    dst=mixed_region_dicts_for_grid(target,bg,scene['diagonal'])
    def shape(grid,o):
        r0,c0,_,_=o['bbox'];return tuple(sorted((r-r0,c-c0,grid[r][c]) for r,c in o['cells']))
    if len(dst)!=len(scene['bound']):return None
    used=set();rows=[]
    for binding in scene['bound']:
        obj=binding['obj'];matches=[i for i,q in enumerate(dst) if shape(g,obj)==shape(y,q)]
        if len(matches)!=1 or matches[0] in used:return None
        index=matches[0];used.add(index);q=dst[index]
        delta=[q['bbox'][a]-obj['bbox'][a] for a in (0,1)]
        axis=binding['axis'];residual=( (delta[axis]-binding['base'][axis])*binding['nsign'],delta[1-axis]*binding['tsign'])
        rows.append((binding['feature'],residual))
    return rows


def render(g,scene,relation):
    h,w=len(g),len(g[0]);writes={};cropped=0
    for cue in scene['cues']:
        for r,c in cue['cells']:writes[r,c]=g[r][c]
    for b in scene['bound']:
        residual=relation(b['feature'])
        if residual is None:return None,{'failure':'unknown_or_unadmitted_feature'}
        axis=b['axis'];delta=b['base'][:]
        delta[axis]+=residual[0]*b['nsign'];delta[1-axis]+=residual[1]*b['tsign']
        cells=set(map(tuple,b['obj']['cells']))
        # Generic crop-before-render: crop source domain, then use old sparse action.
        retained={p for p in cells if 0<=p[0]+delta[0]<h and 0<=p[1]+delta[1]<w}
        if not retained:return None,{'failure':'whole_object_cropped'}
        shifted=shifted_sparse_point_mask(retained,*delta,h,w)
        if shifted is None:return None,{'failure':'sparse_translation_failed'}
        cropped+=len(cells)-len(retained)
        for r,c in retained:
            p=r+delta[0],c+delta[1];v=g[r][c]
            if p in writes:return None,{'failure':'ownership_collision'}
            writes[p]=v
    out=[[scene['bg']]*w for _ in range(h)]
    for (r,c),v in writes.items():out[r][c]=v
    return out,{'cropped_cells':cropped}


class FeatureAlignment:
    def __init__(self,teachers):
        self.models=[];self.records=[];self.training_rows={};self.teacher_count=len(teachers)
        if len(teachers)<2 or len({str(p['input']) for p in teachers})!=len(teachers):return
        for diagonal,cavity_diagonal in product((False,True),repeat=2):
            parsed=[interpretations(p['input'],diagonal,cavity_diagonal) for p in teachers]
            # Preserve every input-eligible role: ambiguous correspondences do not get pruned.
            if any(not scenes for scenes in parsed):continue
            relation={};rows=[];valid=True
            for pair,scenes in zip(teachers,parsed):
                scene_rows=[correspondence(pair['input'],pair['output'],s) for s in scenes]
                if any(r is None for r in scene_rows) or any(r!=scene_rows[0] for r in scene_rows):valid=False;break
                rows.extend(scene_rows[0])
                for key,value in scene_rows[0]:
                    if key in relation and relation[key]!=value:valid=False
                    relation[key]=value
            if not valid:continue
            if not all(all(render(p['input'],s,relation.get)[0]==p['output'] for s in scenes) for p,scenes in zip(teachers,parsed)):continue
            boundary='ARCmarker_enclosure_residual_'+str((diagonal,cavity_diagonal))
            machine=HDS学習実行系() # unchanged default minimum=3, object-level relation only
            for key,value in rows:machine.実行(observation({'enclosed':key,'residual':value},boundary))
            self.models.append((diagonal,cavity_diagonal,machine,boundary,relation))
            self.training_rows[boundary]=rows
            self.records.append(dict(diagonal=diagonal,cavity_diagonal=cavity_diagonal,physical_observations=len(rows),class_counts=dict(Counter(str(k) for k,v in rows)),relation={str(k):v for k,v in relation.items()}))

    def 学習する(self,machine,_observation=None):
        """Optional production binding to the same HDS instance as outer admission."""
        bound=[]
        for diagonal,cavity_diagonal,_,boundary,relation in self.models:
            for key,value in self.training_rows[boundary]:
                machine.実行(observation({'enclosed':key,'residual':value},boundary))
            bound.append((diagonal,cavity_diagonal,machine,boundary,relation))
        self.models=bound

    def 候補(self,g,_policy):
        if not self.models:return None,{'failure':'no_all_teacher_model'}
        outputs=[];details=[]
        for diagonal,cavity_diagonal,machine,boundary,known in self.models:
            def relation(key):
                if key not in known:return None
                result=machine.照会(observation({'enclosed':key},boundary))
                values=[p.予測値 for p in result.予測群 if p.結果経路==('residual',)]
                if 最小排気系().排出する(result).状態!='出力' or not values or any(v!=values[0] for v in values):return None
                return values[0]
            scenes=interpretations(g,diagonal,cavity_diagonal)
            if not scenes:return None,{'failure':'retained_model_unparsed'}
            for scene in scenes:
                out,info=render(g,scene,relation)
                if out is None:return None,info
                outputs.append(out);details.append(info)
        if any(out!=outputs[0] for out in outputs):return None,{'failure':'retained_interpretations_disagree'}
        return outputs[0],{'models':len(self.models),'interpretations':len(outputs),'renders':details}

    def 記録(self):return {'教師数':self.teacher_count,'事前支持数':0,'保持候補':self.records,'crop_prior':'crop source domain before sparse translation'}
