from 接続.ARC2.既存配置展開 import render_layout_mask_macro_tile_expander,foreground_mixed_components,crop_bbox
from 接続.ARC2.既存格子操作 import transform_grid_by_name as transform
from 接続.ARC2.既存疎点転写 import shifted_sparse_point_mask
from 接続.ARC2.既存区切投射 import full_height_color_columns
from 接続.ARC2.記号命令教材 import valid_grid
D4=('identity','rot90','rot180','rot270','flip_h','flip_v','transpose','anti_transpose')

def parse(grid):
    if not valid_grid(grid): return [],{'failure':'invalid_grid'}
    h,w=len(grid),len(grid[0]); roles=[];probes=[]
    for sep in full_height_color_columns(grid):
        s,f=sep['col'],sep['color']; probe={'separator':sep};probes.append(probe)
        if s<5 or s>=w-1: probe['failure']='separator_geometry';continue
        n=s-2
        if n%2!=1: probe['failure']='even_cue_size';continue
        frame_rows=[r for r in range(h) if all(grid[r][c]==f for c in range(s))]
        if len(frame_rows) not in (2,3):probe['failure']='cue_frame_count';continue
        top,middle=frame_rows[:2]; bottom=frame_rows[2] if len(frame_rows)==3 else h
        if middle-top-1!=n or bottom-middle-1!=n or bottom not in (h,h-1):probe['failure']='cue_frame_spacing';continue
        if any(grid[r][0]!=f or grid[r][s-1]!=f for r in range(top,h)):
            probe['failure']='cue_side_frame';continue
        source=[row[:s] for row in grid[:top]]
        cue_grids=[crop_bbox(grid,(a+1,1,b-1,s-2)) for a,b in ((top,middle),(middle,bottom))]
        for bg in sorted(set(sum(source,[]))-{f}):
            sub={'background':bg};probe.setdefault('background_roles',[]).append(sub)
            comps=foreground_mixed_components(source,bg)
            if len(comps)!=2:sub['failure']='instruction_components';continue
            pairs=[(a,b) for a in comps for b in comps if a is not b and len(a['colors'])==2 and len(b['colors'])==1 and b['colors'][0] not in a['colors']]
            if len(pairs)!=1:sub['failure']='template_stencil_roles';continue
            tile,stencil=pairs[0];tg=crop_bbox(source,tile['bbox'])
            if set(sum(tg,[]))!=set(tile['colors']) or len(tg)!=n or len(tg[0])!=n:sub['failure']='solid_square_template';continue
            if f in set(sum(source,[])):sub['failure']='frame_in_instruction';continue
            cues=[]
            for cg in cue_grids:
                cells=[(r,c) for r,row in enumerate(cg) for c,v in enumerate(row) if v!=bg]
                colors={cg[r][c] for r,c in cells}
                cues.append((cells,colors))
            m=n//2
            corners={(0,0),(0,n-1),(n-1,0),(n-1,n-1)}
            for anchor_idx,dir_idx in ((0,1),(1,0)):
                ac,acol=cues[anchor_idx];dc,dcol=cues[dir_idx]
                if len(ac)!=1 or ac[0] not in corners or len(acol)!=1 or len(dc)!=2 or (m,m) not in dc or len(dcol)!=1:continue
                end=next(p for p in dc if p!=(m,m))
                if abs(end[0]-m)+abs(end[1]-m)!=1:continue
                role={'separator':s,'frame_color':f,'background':bg,'source':source,'tile_bbox':tile['bbox'],'tile':tg,'stencil_bbox':stencil['bbox'],'anchor':ac[0],'direction':end,'cue_size':n,'canvas':[row[s+1:] for row in grid],'anchor_index':anchor_idx}
                roles.append(role);sub['success']=True
    return roles,{'roles':len(roles),'probes':probes}

def act(role,model):
    swap,tt,dt,reflection,at=model
    bg=role['background']; n=role['cue_size'];m=n//2
    cue=[[0]*n for _ in range(n)];r,c=role['direction'];cue[r][c]=1
    direction=transform(cue,dt);point=next((r,c)for r,row in enumerate(direction)for c,v in enumerate(row)if v)
    turns={(m-1,m):0,(m,m+1):1,(m+1,m):2,(m,m-1):3}[point]
    source=[row[:] for row in role['source']];tile=transform(role['tile'],tt)
    if swap:
        a,b=sorted(set(sum(tile,[])));tile=[[b if v==a else a for v in row]for row in tile]
    # Conjugate the template so the accepted whole-macro transform turns only the stencil.
    tile=transform(tile,D4[(-turns)%4])
    if reflection:tile=transform(tile,'flip_h')
    r0,c0,r1,c1=role['tile_bbox']
    for r,row in enumerate(tile):source[r0+r][c0:c1+1]=row
    macro,record=render_layout_mask_macro_tile_expander(source)
    if macro is None:return None,{'failure':'accepted_macro_failed','raw':record}
    if record['macro_background_color']!=bg or tuple(record['macro_motif_bbox'])!=tuple(role['tile_bbox']) or tuple(record['macro_layout_bbox'])!=tuple(role['stencil_bbox']):
        return None,{'failure':'accepted_macro_roles_disagree','raw':record}
    if reflection:macro=transform(macro,'flip_h')
    macro=transform(macro,D4[turns])
    cue=[[0]*n for _ in range(n)];r,c=role['anchor'];cue[r][c]=1
    anch=transform(cue,at);ar,ac=next((r,c)for r,row in enumerate(anch)for c,v in enumerate(row)if v)
    canvas=[row[:]for row in role['canvas']];h,w=len(canvas),len(canvas[0]);mh,mw=len(macro),len(macro[0])
    dr=0 if ar==0 else h-mh;dc=0 if ac==0 else w-mw
    if dr<0 or dc<0 or mh>h or mw>w:return None,{'failure':'macro_out_of_bounds','macro_shape':[mh,mw]}
    painted=0
    for color in sorted(set(sum(macro,[]))-{bg}):
        cells={(r,c)for r,row in enumerate(macro)for c,v in enumerate(row)if v==color}
        target=shifted_sparse_point_mask(cells,dr,dc,h,w)
        if target is None:return None,{'failure':'stamp_out_of_bounds'}
        for r,c in target:canvas[r][c]=color
        painted+=len(target)
    return canvas,{'macro':record,'turns':turns,'offset':[dr,dc],'painted_cells':painted,'canvas_cells':h*w}


from itertools import product
MODELS=tuple(product((False,True),D4,D4,(False,True),D4))

def render(grid,model):
    roles,record=parse(grid)
    record['model']=model
    returns=[{'role_index':i,'return':out,'record':rec}for i,role in enumerate(roles)for out,rec in [act(role,model)]]
    record['role_returns']=returns
    # Every structural interpretation finishes before any HOLD is determined.
    if not returns:return None,{**record,'failure':'no_complete_role'}
    if any(r['return'] is None for r in returns):return None,{**record,'failure':'role_failed'}
    if any(r['return']!=returns[0]['return']for r in returns[1:]):return None,{**record,'failure':'role_disagreement'}
    return returns[0]['return'],record

def fit(train):
    if not isinstance(train,list) or len(train)<2 or any(not isinstance(p,dict) or not valid_grid(p.get('input')) or not valid_grid(p.get('output'))for p in train):
        return (),{'failure':'invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in train})!=len(train):return (),{'failure':'duplicate_teacher_inputs'}
    model_returns=[];kept=[]
    for model in MODELS:
        returns=[{'teacher_index':i,'return':out,'record':rec,'exact':out==p['output']}for i,p in enumerate(train)for out,rec in [render(p['input'],model)]]
        accepted=all(r['exact']for r in returns)
        model_returns.append({'model':model,'accepted':accepted,'teacher_returns':returns})
        if accepted:kept.append(model)
    return tuple(kept),{'complete':True,'model_count':len(MODELS),'retained_count':len(kept),'all_model_returns':model_returns}

def consensus(grid,models):
    returns=[{'model':model,'return':out,'record':rec}for model in models for out,rec in [render(grid,model)]]
    record={'complete':True,'model_returns':returns}
    if not returns:return None,{**record,'failure':'no_models'}
    if any(r['return'] is None for r in returns):return None,{**record,'failure':'retained_model_failed'}
    if any(r['return']!=returns[0]['return']for r in returns[1:]):return None,{**record,'failure':'retained_model_disagreement'}
    return returns[0]['return'],record
