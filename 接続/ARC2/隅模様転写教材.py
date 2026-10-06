"""Fresh necessary proofs around the unchanged original fitter and observer."""
from copy import deepcopy
from dataclasses import dataclass
import collections
from . import 隅模様転写基底教材 as base
PROGRAMS=base.PROGRAMS
RESOURCE_ERRORS=base.RESOURCE_ERRORS
core=base.core
valid_grid=base.valid_grid
render=base.render
predict=base.predict
gridkey=base.gridkey
validate_teachers=base.validate_teachers
# Every listed branch precedes the first activation/action read in the frozen core.
COMMON_FAILURES=frozenset(('background_tie','frame_color_or_cover_not_unique',
    'whole_frame_component_ownership','decoration_nearest_corner_tie',
    'whole_decoration_component_crosses_corners','corner_has_multiple_whole_decorations'))

def _certificate(pair):
 g=pair['input'];target=pair['output'];h,w=len(g),len(g[0]);counts=collections.Counter(v for line in g for v in line);maximum=max(counts.values());bgs=[color for color,total in counts.items()if total==maximum];bg=bgs[0]if len(bgs)==1 else None
 result={'input_palette':sorted(counts),'input_color_counts':dict(sorted(counts.items())),'target_palette':sorted({v for line in target for v in line}),'input_shape':[h,w],'target_shape':[len(target),len(target[0])],'background_candidates':bgs,'violations':[]}
 if result['input_shape']!=result['target_shape']:result['violations'].append('output_shape_must_equal_input_shape')
 if not set(v for line in target for v in line)<=set(counts):result['violations'].append('output_cannot_introduce_new_color')
 if g==target:result['violations'].append('renderer_rejects_no_change')
 if len(bgs)!=1:result['violations'].append('unique_input_modal_background_required')
 if result['input_shape']==result['target_shape']and bg is not None:
  changes=[(r,c,g[r][c],target[r][c])for r in range(h)for c in range(w)if g[r][c]!=target[r][c]];old_nonbackground=sorted({a for r,c,a,b in changes if a!=bg});new_colors=sorted({b for r,c,a,b in changes})
  result.update(changed_cells=changes,changed_cell_count=len(changes),changed_original_nonbackground_colors=old_nonbackground,changed_target_colors=new_colors)
  if len(old_nonbackground)>1:result['violations'].append('only_one_frame_color_can_be_changed_in_original_foreground')
  if bg in new_colors:result['violations'].append('no_proposal_can_paint_original_background_color')
  if len(old_nonbackground)==1 and old_nonbackground[0]in new_colors:result['violations'].append('frame_color_cannot_be_a_decoration_write_color')
 if bg is not None:
  role_certificates=[]
  for color in sorted(set(counts)-{bg}):
   remaining={(r,c)for r in range(h)for c in range(w)if g[r][c]==color};components=[]
   while remaining:
    todo=[min(remaining)];remaining.remove(todo[0]);cells=[]
    while todo:
     r,c=todo.pop();cells.append((r,c))
     for dr in (-1,0,1):
      for dc in (-1,0,1):
       if (dr or dc)and(r+dr,c+dc)in remaining:remaining.remove((r+dr,c+dc));todo.append((r+dr,c+dc))
    r0=min(r for r,c in cells);r1=max(r for r,c in cells);c0=min(c for r,c in cells);c1=max(c for r,c in cells);interior=sorted((r,c)for r,c in cells if r0<r<r1 and c0<c<c1)
    components.append({'cells':sorted(cells),'bbox':[r0,c0,r1,c1],'strict_bbox_interior_cells':interior,'cannot_be_owned_by_any_rectangle_perimeter':bool(interior)})
   role_certificates.append({'color':color,'components':components,'impossible_frame_role':any(c['cannot_be_owned_by_any_rectangle_perimeter']for c in components)})
  result['frame_color_component_certificates']=role_certificates
  if not role_certificates or all(r['impossible_frame_role']for r in role_certificates):result['violations'].append('every_possible_frame_color_has_unownable_whole_C8_component')
 result['fit_impossibility_proved']=bool(result['violations']);return result


def necessity_certificate(pair):
    try:return _certificate(pair)
    except BaseException as error:
        prefix=[];tb=error.__traceback__
        while tb:
            frame=tb.tb_frame
            if frame.f_code is _certificate.__code__:
                prefix.append({key:value for key,value in frame.f_locals.items() if key in (
                    'g','target','h','w','counts','bgs','bg','result','changes','old_nonbackground',
                    'new_colors','role_certificates','color','remaining','components','todo','cells',
                    'r','c','dr','dc','r0','r1','c0','c1','interior')})
            tb=tb.tb_next
        base.report_exception(None,error,'necessity_certificate_exception',completed_and_active_certificate_prefix=prefix)
        raise


def proof_record(validation,certificates,probes,reason,refuting):
    probe_domains={(row['program'],row['teacher_index'])for row in probes}
    unexecuted=[{'phase':'declared_fit','program':program,'teacher_index':index,
                 'execution_status':'unexecuted_after_all_program_impossibility_proof',
                 'renderer_executed_in_this_phase':False,
                 'separate_proof_probe_executed_for_same_domain':(program,index)in probe_domains}
                for program in PROGRAMS for index in range(validation['teacher_count'])]
    return {**validation,'program_returns':[],'evaluated_programs':0,
            'evaluated_teacher_returns':0,'retained_count':0,'failure':reason,
            'necessity':{'certificates':certificates,'common_prefix_returns':probes,
                         'refuting_teacher_indices':refuting,'fit_impossibility_proved':True,
                         'disposition':'fit_domain_proven_empty','original_fitter_executed':False},
            'actual_common_prefix_executions':len(probes),'actual_declared_fit_renderer_calls':0,
            'actual_renderer_executions_in_fit':len(probes),'unexecuted_calls':unexecuted}


def fit(teachers,observer=None):
    certificates=[];probes=[];validation=None;active=None
    try:
        valid,validation=base.validate_teachers(teachers)
        if not valid:return base.fit(teachers,observer)
        base.emit(observer,'necessity_teacher_validation',valid=True,record=validation)
        for index,pair in enumerate(teachers):
            active={'phase':'necessity_certificate','teacher_index':index,'input':pair['input'],'target':pair['output']}
            certificate=necessity_certificate(pair)
            row={'teacher_index':index,'input':pair['input'],'target':pair['output'],'certificate':certificate}
            certificates.append(row);active=None;base.emit(observer,'necessity_certificate_completed',**row)
        refuting=[r['teacher_index']for r in certificates if r['certificate']['fit_impossibility_proved']]
        if refuting:
            record=proof_record(validation,certificates,probes,'fit_domain_proven_empty_by_necessary_invariants',refuting)
            base.emit(observer,'teacher_fit_proven_empty',models=(),record=record);return (),record
        # Fresh generic calls. Only completed, listed structural failures prove
        # all-model impossibility; resource/node-cap failures propagate unchanged.
        for index,pair in enumerate(teachers):
            program=PROGRAMS[0]
            active={'phase':'common_prefix_probe','program':program,'teacher_index':index,'input':pair['input']}
            base.emit(observer,'common_prefix_start',**active)
            def relay(event):
                if observer is not None:observer({**event,'execution_phase':'common_prefix_probe','teacher_index':index})
            output,detail=base.render(pair['input'],program,relay if observer is not None else None)
            refutation=output is None and detail.get('status')=='HOLD' and detail.get('failure')in COMMON_FAILURES
            row={'phase':'common_prefix_probe','program':program,'teacher_index':index,
                 'input':pair['input'],'output':output,'record':detail,
                 'complete':True,'all_model_refutation':refutation}
            probes.append(row);active=None;base.emit(observer,'common_prefix_completed',**row)
            if refutation:
                record=proof_record(validation,certificates,probes,'fit_domain_proven_empty_by_common_structural_rejection',[index])
                base.emit(observer,'teacher_fit_proven_empty',models=(),record=record);return (),record
        # Original code, full four-program fit and diagnostics remain unchanged.
        active={'phase':'original_fitter_fallback'}
        models,original=base.fit(teachers,observer);active=None
        record=dict(original);record['necessity']={'certificates':certificates,
            'common_prefix_returns':probes,'refuting_teacher_indices':[],
            'fit_impossibility_proved':False,'disposition':'exact_original_fitter_fallback',
            'original_fitter_executed':True}
        record.update(actual_common_prefix_executions=len(probes),
            actual_declared_fit_renderer_calls=original.get('evaluated_teacher_returns',0),
            actual_renderer_executions_in_fit=len(probes)+original.get('evaluated_teacher_returns',0),
            unexecuted_calls=[])
        return models,record
    except BaseException as error:
        base.report_exception(observer,error,'necessity_fit_exception',stage='necessity_fit',
            validation=validation,completed_teacher_certificates=certificates,
            completed_common_prefix_returns=probes,active_call=active)
        raise


@dataclass(frozen=True,init=False,slots=True)
class 隅模様転写教材(base.隅模様転写教材):
    def __init__(self,教師群,監査=None,観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models);object.__setattr__(self,'教師数',record['teacher_count'])
        object.__setattr__(self,'異入力数',record['distinct_input_count']);object.__setattr__(self,'適合数',len(models))
        object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(deepcopy(record))
