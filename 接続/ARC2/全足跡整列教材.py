"""Generic fit-impossibility proof; exact v1 fitter remains the sole fallback.

No renderer call is claimed for symbolically rejected teacher/program calls.
"""
from copy import deepcopy
from dataclasses import dataclass
from . import 全足跡整列基底教材 as base

PROGRAMS=base.PROGRAMS
RESOURCE_ERRORS=base.RESOURCE_ERRORS
core=base.core
valid_grid=base.valid_grid
render=base.render
predict=base.predict
gridkey=base.gridkey
validate_teachers=base.validate_teachers


def axis_certificate(grid):
    """Complete finite color/row counts over an already validated ARC input."""
    height=len(grid);width=len(grid[0]);counts=[[0]*height for _ in range(10)]
    row_index=None;column_index=None;colors=[]
    try:
        for row_index,line in enumerate(grid):
            for column_index,color in enumerate(line):
                counts[color][row_index]+=1
        totals=[sum(rows)for rows in counts]
        maximum=max(totals)
        backgrounds=[color for color,total in enumerate(totals)if total==maximum]
        background=backgrounds[0]if len(backgrounds)==1 else None
        witnesses=[]
        for color,rows in enumerate(counts):
            occupied=[row for row,n in enumerate(rows)if n]
            eligible=(totals[color]>=3 and color!=background and len(occupied)==1
                      and 1<=occupied[0]<height-1)if background is not None else None
            entry={'color':color,'total_occurrences':totals[color],
                   'row_counts':list(rows),'occupied_rows':occupied,
                   'is_original_background':color==background if background is not None else None,
                   'eligible_axis_witness':eligible}
            colors.append(entry)
            if eligible:witnesses.append({'axis_color':color,'axis_row':occupied[0],
                                           'axis_cell_count':totals[color]})
        observed=[color for color,total in enumerate(totals)if total]
        absence_proved=background is not None and not witnesses
        return {'input_shape':[height,width],'background_candidates':backgrounds,
                'original_unique_background':background,'colors':colors,'witnesses':witnesses,
                'analysis_complete':True,'axis_absence_proved':absence_proved,
                'proof_status':'proved_empty_roles' if absence_proved else
                    'inapplicable_nonunique_background' if background is None else 'eligible_witness_exists',
                'symbolic_raw_pair_count':max(0,height-2)*(len(observed)-1)if background is not None else None,
                'raw_pairs_enumerated':False,'renderer_executed':False}
    except BaseException as error:
        base.report_exception(None,error,'axis_certificate_exception',
                              completed_color_certificates=colors,partial_row_counts=counts,
                              active_row=row_index,active_column=column_index)
        raise


def fit(teachers,observer=None):
    certificates=[];active=None;validation=None
    try:
        # The exact v1 validator enforces all pair/grid schemas before gridkey.
        valid,validation=base.validate_teachers(teachers)
        if not valid:return base.fit(teachers,observer)
        for index,pair in enumerate(teachers):
            active={'teacher_index':index,'input':pair['input']}
            certificate=axis_certificate(pair['input'])
            row={'teacher_index':index,**certificate};certificates.append(row);active=None
            base.emit(observer,'axis_necessity_certificate',certificate=row)
        rejecting=[row['teacher_index']for row in certificates if row['axis_absence_proved']]
        proof={'certificates':certificates,'rejecting_teacher_indices':rejecting,
               'necessary_not_sufficient':True,'original_raw_diagnostics_unchanged':False}
        if not rejecting:
            # No absence proof: call the byte-identical v1 fitter directly.
            models,original_record=base.fit(teachers,observer)
            record=dict(original_record)
            record['axis_necessity']={**proof,'disposition':'exact_v1_fitter_fallback',
                                     'original_raw_diagnostics_unchanged':True}
            return models,record
        calls=[{'program':program,'teacher_index':index,
                'execution_status':'not_executed_after_fit_impossibility_proof',
                'renderer_executed':False,'output_returned':False,
                'symbolic_raw_pair_count':certificates[index]['symbolic_raw_pair_count'],
                'raw_pairs_enumerated':False}
               for program in PROGRAMS for index in range(len(teachers))]
        record={**validation,'program_returns':[],'evaluated_programs':0,
                'evaluated_teacher_returns':0,'retained_count':0,
                'failure':'fit_domain_proven_empty_by_axis_necessity',
                'axis_necessity':{**proof,'disposition':'fit_domain_proven_empty'},
                'symbolic_unexecuted_programs':list(PROGRAMS),'unexecuted_calls':calls,
                'symbolic_fit_result':'no declared program can reproduce every teacher'}
        base.emit(observer,'teacher_fit_proven_empty',models=(),record=record)
        return (),record
    except BaseException as error:
        base.report_exception(observer,error,'axis_necessity_fit_exception',
                              stage='axis_necessity_fit',validation=validation,
                              completed_teacher_certificates=certificates,active_call=active)
        raise


@dataclass(frozen=True,init=False,slots=True)
class 全足跡整列教材(base.全足跡整列教材):
    def __init__(self,教師群,監査=None,観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models);object.__setattr__(self,'教師数',record['teacher_count'])
        object.__setattr__(self,'異入力数',record['distinct_input_count']);object.__setattr__(self,'適合数',len(models))
        object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(deepcopy(record))
