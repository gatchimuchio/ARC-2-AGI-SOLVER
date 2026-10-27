"""教師役割と全component/全copy証明を同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter,defaultdict
import itertools
from .既存制御複写 import (_control_bar_shape_source,_control_bar_affected_shape_indexes,
    render_control_bar_shape_rewrite,connected_component_dicts_for_grid)

def valid_grid(grid):
    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30
           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def raw_teacher_policy(pairs):
 if len(pairs)<2:return None,{'failure':'too_few_teachers'}
 new_sets=[];bar_sets=[];periods=[];sources=[]
 for pair in pairs:
  source,record=_control_bar_shape_source(pair['input'])
  if source is None:return None,{'failure':'source_parse_failed','record':record}
  new=set(v for row in pair['output']for v in row)-set(v for row in pair['input']for v in row)
  if len(new)!=1:return None,{'failure':'output_only_color_count','new_colors':sorted(new)}
  new_sets.append(new);bar_sets.append(set(source['control_colors']));periods.append(source['inferred_period']);sources.append(source)
 common=set.intersection(*new_sets)
 if len(common)!=1:return None,{'failure':'new_color_not_shared'}
 if any(v!=bar_sets[0]for v in bar_sets):return None,{'failure':'control_colors_not_shared'}
 if any(v!=periods[0]for v in periods):return None,{'failure':'period_not_shared','periods':periods}
 target=next(iter(common));rows=[];fits=[]
 for recolor,copy in itertools.permutations(sorted(bar_sets[0]),2):
  results=[render_control_bar_shape_rewrite(p['input'],recolor,copy,target,periods[0])for p in pairs];pair_fits=[out is not None and out==p['output']for(out,r),p in zip(results,pairs)];row={'policy':[recolor,copy,target,periods[0]],'pair_fits':pair_fits,'records':[r for out,r in results]};rows.append(row)
  if all(pair_fits):fits.append(row['policy'])
 return (fits[0]if len(fits)==1 else None),{'periods':periods,'control_colors':sorted(bar_sets[0]),'new_color':target,'all_policies':rows,'successful_policies':fits}

def guarded_render(grid,policy,allow_control_removal=False):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    if not isinstance(policy,(tuple,list))or len(policy)!=4:return None,{'failure':'invalid_policy'}
    recolor,copy,target,period=policy
    if any(type(v)is not int or not 0<=v<=9 for v in (recolor,copy,target))or len({recolor,copy,target})!=3 or type(period)is not int or period<1:
        return None,{'failure':'invalid_policy'}
    raw,raw_record=render_control_bar_shape_rewrite(grid,*policy)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    source,rejection=_control_bar_shape_source(grid)
    if source is None:return None,{'failure':'original_source_unresolved','rejection':rejection}
    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];h,w=len(grid),len(grid[0]);bars=source['control_bars'];shapes=source['shapes']
    if source['background']!=bg or bg in {recolor,copy,target}or set(source['control_colors'])!={recolor,copy}:
        return None,{'failure':'control_role_alias_or_unassigned'}
    control_cells={tuple(p)for b in bars for p in b['cells']};shape_cells={tuple(p)for o in shapes for p in o['cells']}
    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}
    if control_cells&shape_cells or control_cells|shape_cells!=foreground:return None,{'failure':'component_coverage_failed'}
    components=connected_component_dicts_for_grid(grid,set(counts)-{bg})
    if any(o['bbox'][0]<h-1==o['bbox'][2]for o in components):return None,{'failure':'bottom_straddling_component'}
    if len(components)!=len(bars)+len(shapes):return None,{'failure':'component_count_coverage_failed'}
    heights=Counter(o['bbox'][2]-o['bbox'][0]+1 for o in shapes);modes=[v for v,n in heights.items()if n==max(heights.values())]
    if len(modes)!=1:return None,{'failure':'shape_height_mode_tie'}
    geometric_period=modes[0]+1;starts=sorted({o['bbox'][0]for o in shapes});gaps=[b-a for a,b in zip(starts,starts[1:])]
    if any(gap%geometric_period for gap in gaps):return None,{'failure':'unwitnessed_gcd_period_branch','height_period':geometric_period,'row_gaps':gaps}
    if source['inferred_period']!=geometric_period or period!=geometric_period:
        return None,{'failure':'fitted_period_input_disagreement','fitted':period,'height_period':geometric_period}
    ri=_control_bar_affected_shape_indexes(source,recolor);ci=_control_bar_affected_shape_indexes(source,copy)
    if not ri or not ci:return None,{'failure':'empty_control_role'}
    top=min(shapes[i]['bbox'][0]for i in ci);highest=[i for i in ci if shapes[i]['bbox'][0]==top]
    if len(highest)!=1:return None,{'failure':'highest_copy_source_not_unique'}
    source_shape=shapes[highest[0]];recolor_cells={tuple(p)for i in ri for p in shapes[i]['cells']};copy_proposals=defaultdict(set);proposed=0
    for repeat in range(1,len(set(ri))+1):
        for r,c in source_shape['cells']:
            nr=r-period*repeat;proposed+=1
            if not(0<=nr<h and 0<=c<w):return None,{'failure':'copy_clipping_required','repeat':repeat,'cell':[nr,c]}
            copy_proposals[(nr,c)].add(source_shape['color'])
    proposals=defaultdict(set)
    for p in control_cells:proposals[p].add(bg)
    for p in recolor_cells:proposals[p].add(target)
    for p,values in copy_proposals.items():proposals[p].update(values)
    conflicts=[(p,sorted(v))for p,v in sorted(proposals.items())if len(v)>1]
    if conflicts:return None,{'failure':'simultaneous_colour_conflict','conflicts':conflicts}
    expected=[row[:]for row in grid]
    for(r,c),values in proposals.items():expected[r][c]=next(iter(values))
    stationary=foreground-control_cells-recolor_cells
    if any(expected[r][c]!=grid[r][c]for r,c in stationary):return None,{'failure':'stationary_foreground_overwritten'}
    if any(expected[r][c]!=target for r,c in recolor_cells):return None,{'failure':'recolor_component_incomplete'}
    operations=set(proposals)
    if any(expected[r][c]!=grid[r][c]for r in range(h)for c in range(w)if(r,c)not in operations):
        return None,{'failure':'outside_operations_changed'}
    record={'background':bg,'component_count':len(components),'shape_count':len(shapes),'control_count':len(bars),
            'control_erasure_pixels':len(control_cells),'height_mode':modes[0],'period':period,'row_gaps':gaps,
            'recolor_component_count':len(set(ri)),'recolor_pixels':len(recolor_cells),'copy_selected_count':len(set(ci)),
            'highest_copy_index':highest[0],'copy_operation_count':len(set(ri)),'copy_proposed_pixels':proposed,
            'copy_union_pixels':len(copy_proposals),'copy_added_background_pixels':sum(grid[r][c]==bg for r,c in copy_proposals)}
    if control_cells and not allow_control_removal:return None,dict(record,failure='unwitnessed_control_consumption')
    changed=sum(a!=b for ar,br in zip(grid,expected)for a,b in zip(ar,br))
    expected_record={'renderer_case':'control_bar_shape_rewrite','control_bar_shape_background_color':bg,
        'control_bar_shape_recolor_control_color':recolor,'control_bar_shape_copy_control_color':copy,
        'control_bar_shape_recolor_target_color':target,'control_bar_shape_period':period,
        'control_bar_shape_control_count':len(bars),'control_bar_shape_recolor_shape_count':len(set(ri)),
        'control_bar_shape_copy_shape_count':len(set(ci)),'control_bar_shape_copy_cell_count':len(copy_proposals),
        'control_bar_shape_recolored_cell_count':len(recolor_cells),'control_bar_shape_event_count':changed,
        'control_bar_shape_input_shape':[h,w],'control_bar_shape_output_shape':[h,w]}
    if raw!=expected or raw_record!=expected_record:return None,dict(record,failure='original_grid_or_record_disagreement')
    record.update(raw_record=raw_record,changed_pixels=changed,stationary_foreground_pixels=len(stationary))
    return raw,record

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):
        return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    policy,record=raw_teacher_policy(teachers)
    if policy is None:return None,dict(record,failure='raw_teacher_policy_unresolved')
    results=[guarded_render(p['input'],policy,True)for p in teachers];record['teacher_records']=[r for _,r in results]
    if any(out is None or out!=p['output']for(out,_),p in zip(results,teachers)):
        return None,dict(record,failure='teacher_certificate_failed')
    witnesses=sum(bool(r['control_erasure_pixels'])for _,r in results);record['control_consumption_witnesses']=witnesses
    return {'policy':policy,'allow_control_removal':witnesses>0,'control_consumption_witnesses':witnesses},record

class 制御複写教材:
    def __init__(self, 教師群):
        self.モデル, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.モデル is None:
            return None, {"failure": "全教師を再現する制御bar複写なし"}
        return guarded_render(格子, self.モデル['policy'], self.モデル['allow_control_removal'])

    def 記録(self):
        return {"全教師共通役割と消去証拠": self.モデル}
