"""Teacher-only finite motif-view grammar. No corpus, expected-grid, or task ID access."""
from collections import Counter
from itertools import product
from .既存倍率置換 import extract_motif_components, pattern_from_component, scaled_pattern_cells
from .既存格子操作 import transform_grid_by_name

TRANSFORMS = ('identity','rot90','rot180','rot270','flip_h','flip_v','transpose','anti_transpose')

def models():
    return [dict(zip(('extent','window','center','transform','phase','overlay','base_ink','highlight'), p))
            for p in product(('motif5plus1','input3minus2'),('motif2','input'),('floor','ceil'),
                             TRANSFORMS,('window','canvas'),('tile','scale2'),range(10),range(10))
            if p[-2] != p[-1]]

def parse(grid):
    if (not isinstance(grid,list) or not 1 <= len(grid) <= 30 or not isinstance(grid[0],list)
        or not 1 <= len(grid[0]) <= 30 or any(not isinstance(row,list) or len(row)!=len(grid[0]) for row in grid)
        or any(type(v) is not int or not 0<=v<=9 for row in grid for v in row)):
        return None, 'invalid_arc_grid'
    counts=Counter(v for row in grid for v in row)
    if len(counts)!=2: return None,'not_binary'
    ranked=counts.most_common()
    if ranked[0][1]==ranked[1][1]: return None,'background_tie'
    bg,fg=ranked[0][0],ranked[1][0]
    comps=extract_motif_components(grid)
    if len(comps)!=1: return None,'not_one_whole_c8_component'
    comp=comps[0]
    expected={(r,c,fg) for r,row in enumerate(grid) for c,v in enumerate(row) if v==fg}
    if set(comp['cells'])!=expected: return None,'foreground_ownership_failed'
    raw=pattern_from_component(comp)
    mask=[[int(v is not None) for v in row] for row in raw]
    return {'background':bg,'foreground':fg,'input_shape':[len(grid),len(grid[0])],
            'bbox':list(comp['bbox']),'cells':comp['cells'],'mask':mask,
            'foreground_count':len(expected),'background_count':counts[bg],
            'ownership':'complete foreground single C8 + all remaining input background'},None

def action(role,model):
    b,f=role['background'],role['foreground']
    if {model['base_ink'],model['highlight']}&{b,f}:
        return {'status':'failure','reason':'output_colors_not_new','output':None}
    mask=transform_grid_by_name(role['mask'],model['transform'])
    mh,mw=len(mask),len(mask[0]); ih,iw=role['input_shape']
    oh,ow=(5*mh+1,5*mw+1) if model['extent']=='motif5plus1' else (3*ih-2,3*iw-2)
    wh,ww=(2*mh,2*mw) if model['window']=='motif2' else (ih,iw)
    if not (1<=oh<=30 and 1<=ow<=30):
        return {'status':'failure','reason':'output_extent_outside_arc','shape':[oh,ow],'output':None}
    if wh>oh or ww>ow:
        return {'status':'failure','reason':'window_outside_canvas','output':None}
    bias=int(model['center']=='ceil'); top,left=(oh-wh+bias)//2,(ow-ww+bias)//2
    ar,ac=(top,left) if model['phase']=='window' else (0,0)
    pattern=tuple(tuple(model['base_ink'] if v else None for v in row) for row in mask)
    out=[[b]*ow for _ in range(oh)]
    # Euclidean residue anchors enumerate every translated tile intersecting the canvas.
    for tr in range(ar % mh - mh,oh,mh):
        for tc in range(ac % mw - mw,ow,mw):
            for r,c,v in scaled_pattern_cells(pattern,1,tr,tc):
                if 0<=r<oh and 0<=c<ow: out[r][c]=v
    if model['overlay']=='scale2':
        if (wh,ww)!=(2*mh,2*mw):
            return {'status':'failure','reason':'scale_window_mismatch','output':None}
        pattern=tuple(tuple(model['highlight'] if v else None for v in row) for row in mask)
        for r,c,v in scaled_pattern_cells(pattern,2,top,left): out[r][c]=v
    else:
        for r in range(top,top+wh):
            for c in range(left,left+ww):
                if out[r][c]==model['base_ink']: out[r][c]=model['highlight']
    return {'status':'success','output':out,'shape':[oh,ow],
            'window':[top,left,wh,ww],'period':[mh,mw],'phase_origin':[ar,ac]}

def safe_action(role,model):
    try: return action(role,model)
    except MemoryError as e: return {'status':'resource_error','reason':type(e).__name__,'output':None}
    except Exception as e: return {'status':'runtime_error','reason':type(e).__name__+': '+str(e),'output':None}

def consensus(returns):
    if not returns: return {'status':'HOLD','reason':'no_retained_models','output':None}
    if any(x['status']!='success' for x in returns):
        return {'status':'HOLD','reason':'retained_model_failure','output':None}
    if any(x['output']!=returns[0]['output'] for x in returns[1:]):
        return {'status':'HOLD','reason':'retained_model_disagreement','output':None}
    return {'status':'EMIT','reason':'all_retained_complete_outputs_agree','output':returns[0]['output']}
