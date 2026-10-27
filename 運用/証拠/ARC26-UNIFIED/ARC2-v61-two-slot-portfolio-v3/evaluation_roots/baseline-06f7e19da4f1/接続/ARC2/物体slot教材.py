"""全raw対応の自己支持と同時描画を証明し、元出力だけを同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter,defaultdict
from .既存物体slot import (infer_object_slot_marker_corridor_colors,render_object_slot_marker_corridor_projector,
    object_slot_policy,object_slot_supported,object_slot_rect_cells,object_slot_path_cells,
    object_slot_serializable_event,object_slot_aligned_directions)

def valid_grid(grid):
    return (isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)
            and 1<=len(grid[0])<=30 and all(isinstance(row,list)and len(row)==len(grid[0])
            and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))

def guarded_render(grid,marker,corridor,allow_unmatched_removal=False):
    if not valid_grid(grid):return None,{'failure':'invalid_arc_grid'}
    if any(type(v)is not int or not 0<=v<=9 for v in (marker,corridor))or marker==corridor:
        return None,{'failure':'invalid_role_colors'}
    raw,raw_record=render_object_slot_marker_corridor_projector(grid,marker,corridor)
    if raw is None:return None,{'failure':'original_renderer_unresolved','raw_record':raw_record}
    policy,rejection=object_slot_policy(grid,marker)
    if policy is None:return None,{'failure':'original_policy_unresolved','rejection':rejection}
    counts=Counter(v for row in grid for v in row);leaders=[c for c,n in counts.items()if n==max(counts.values())]
    if len(leaders)!=1:return None,{'failure':'background_tie'}
    bg=leaders[0];object_color=policy['object_color'];height,width=len(grid),len(grid[0])
    if policy['background_color']!=bg or len({bg,object_color,marker,corridor})!=4 or set(counts)!={bg,object_color,marker}:
        return None,{'failure':'input_role_palette_violation'}
    markers=policy['marker_components'];objects=policy['object_components'];events=policy['events']
    marker_cells=set().union(*(set(m['cells'])for m in markers));object_cells=set().union(*(set(o['cells'])for o in objects))
    if marker_cells!={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v==marker}or object_cells!={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v==object_color}:
        return None,{'failure':'source_component_coverage_failed'}
    if not events or len({e['object_index']for e in events})!=len(events)or len({e['marker_index']for e in events})!=len(events):
        return None,{'failure':'raw_event_roles_not_unique'}
    proposals=defaultdict(set);slots=set();selected=set();details=[]
    for event in events:
        oi,mi=event['object_index'],event['marker_index']
        if not 0<=oi<len(objects)or not 0<=mi<len(markers):return None,{'failure':'invalid_event_component_index'}
        obj=objects[oi];mark=markers[mi];own=set(obj['cells']);mark_cells=set(mark['cells']);slot=set(event['slot_cells']);path=set(event['path_cells'])
        mb,sb=mark['bbox'],event['slot_bbox'];direction=event['direction']
        if (sb[2]-sb[0],sb[3]-sb[1])!=(mb[2]-mb[0],mb[3]-mb[1])or slot!=set(object_slot_rect_cells(sb))or len(slot)!=len(mark_cells):
            return None,{'failure':'slot_marker_shape_disagreement'}
        if set(event['marker_cells'])!=mark_cells or tuple(event['marker_bbox'])!=tuple(mb)or tuple(event['object_bbox'])!=tuple(obj['bbox']):
            return None,{'failure':'event_component_disagreement'}
        if direction not in object_slot_aligned_directions(sb,mb)or not path or path!=set(object_slot_path_cells(sb,mb,direction)):
            return None,{'failure':'event_corridor_disagreement'}
        if any(not(0<=r<height and 0<=c<width)or grid[r][c]!=bg for r,c in slot|path):
            return None,{'failure':'slot_corridor_not_original_background'}
        isolated=[[value if value!=object_color or(r,c)in own else bg for c,value in enumerate(row)]for r,row in enumerate(grid)]
        if not object_slot_supported(isolated,sb,object_color,direction):
            return None,{'failure':'event_borrows_other_object_support','event':object_slot_serializable_event(event)}
        if slots&slot:return None,{'failure':'selected_slots_overlap'}
        slots.update(slot);selected.update(mark_cells)
        for p in slot:proposals[p].add(marker)
        for p in path|mark_cells:proposals[p].add(corridor)
        details.append(object_slot_serializable_event(event))
    if len(slots)!=len(selected):return None,{'failure':'selected_marker_area_changed'}
    conflicts=[(p,sorted(v))for p,v in sorted(proposals.items())if len(v)>1]
    if conflicts:return None,{'failure':'proposal_colour_conflict','conflicts':conflicts}
    unmatched=marker_cells-selected;unmatched_count=len(markers)-len(events)
    record={'raw_record':raw_record,'pair_count':len(events),'unmatched_marker_components':unmatched_count,
            'unmatched_marker_pixels':len(unmatched),'selected_marker_pixels':len(selected),'slot_pixels':len(slots),'events':details}
    if unmatched and not allow_unmatched_removal:return None,dict(record,failure='unwitnessed_unmatched_marker_removal')
    expected=[row[:]for row in grid]
    for r,c in marker_cells:expected[r][c]=bg
    for (r,c),values in proposals.items():expected[r][c]=next(iter(values))
    if any(expected[r][c]!=grid[r][c]for r,c in object_cells):return None,dict(record,failure='object_pixels_changed')
    if sum(v==marker for row in expected for v in row)!=len(selected):return None,dict(record,failure='selected_marker_count_changed')
    if any(expected[r][c]!=bg for r,c in unmatched):return None,dict(record,failure='unmatched_marker_removal_disagreement')
    operations=marker_cells|set(proposals)
    if any(expected[r][c]!=grid[r][c]for r in range(height)for c in range(width)if(r,c)not in operations):
        return None,dict(record,failure='outside_operations_changed')
    changed=sum(a!=b for ar,br in zip(grid,expected)for a,b in zip(ar,br))
    expected_record={'renderer_case':'object_slot_marker_corridor_projector','object_slot_background_color':bg,'object_slot_marker_color':marker,
                     'object_slot_object_color':object_color,'object_slot_corridor_color':corridor,'object_slot_event_count':changed,
                     'object_slot_changed_cell_count':changed,'object_slot_pair_count':len(events),'object_slot_removed_marker_component_count':unmatched_count,
                     'object_slot_records':details,'object_slot_input_shape':[height,width],'object_slot_output_shape':[height,width]}
    if raw!=expected or raw_record!=expected_record:return None,dict(record,failure='source_output_or_record_disagreement')
    record.update(changed_pixels=changed,corridor_union_pixels=sum(next(iter(v))==corridor for v in proposals.values()),
                  object_pixels_preserved=len(object_cells),outside_operation_pixels=height*width-len(operations))
    return raw,record

def fit_teachers(teachers):
    if len(teachers)<2 or any(not valid_grid(p['input'])or not valid_grid(p['output'])for p in teachers):
        return None,{'failure':'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple,p['input']))for p in teachers})!=len(teachers):return None,{'failure':'duplicate_teacher_inputs'}
    colors,color_record=infer_object_slot_marker_corridor_colors(teachers);record={'raw_colors':colors,'color_record':color_record}
    if colors is None:return None,dict(record,failure='raw_roles_unresolved')
    raw=[render_object_slot_marker_corridor_projector(p['input'],*colors)for p in teachers]
    record['raw_records']=[r for _,r in raw];record['raw_pair_fits']=[out is not None and out==p['output']for(out,_),p in zip(raw,teachers)]
    if not all(record['raw_pair_fits']):return None,dict(record,failure='raw_teacher_reproduction_failed')
    structural=[guarded_render(p['input'],*colors,allow_unmatched_removal=True)for p in teachers]
    record['teacher_records']=[r for _,r in structural]
    if any(out is None or out!=p['output']for(out,_),p in zip(structural,teachers)):
        return None,dict(record,failure='teacher_certificate_failed')
    witnesses=sum(bool(r['unmatched_marker_pixels'])for _,r in structural)
    record['unmatched_removal_witnesses']=witnesses
    return {'marker_color':colors[0],'corridor_color':colors[1],'allow_unmatched_removal':witnesses>0,'unmatched_removal_witnesses':witnesses},record

class 物体slot教材:
    def __init__(self, 教師群):
        self.モデル, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.モデル is None:
            return None, {"failure": "全教師を再現する物体slot回廊なし"}
        return guarded_render(格子, self.モデル['marker_color'], self.モデル['corridor_color'],
                              self.モデル['allow_unmatched_removal'])

    def 記録(self):
        return {"全教師共通役割と分岐証拠": self.モデル}
