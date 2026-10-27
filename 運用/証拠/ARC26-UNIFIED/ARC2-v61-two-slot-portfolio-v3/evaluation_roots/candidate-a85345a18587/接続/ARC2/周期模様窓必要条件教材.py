"""NEW proof-front fitter; exact recovered032 files remain separate and unchanged.

Every model remains in the ordered domain. A necessary-condition refutation
licenses explicitly symbolic, unexecuted slots, never fabricated action returns.
Unrefuted models execute the unchanged action for every teacher.
"""
from dataclasses import dataclass, asdict
from . import 周期模様窓教材 as strict
from . import 周期模様窓基底教材 as base
from .周期模様窓基底教材 import *

METHOD='NEW034-palette-shape-necessity-front-v1'
SWAPPED_TRANSFORMS=frozenset(('rot90','rot270','transpose','anti_transpose'))
ROLE_FIELDS=frozenset(('background','foreground','input_shape','bbox','cells','mask',
                      'foreground_count','background_count','ownership'))


def complete_role_witness(role,grid):
    """Check the complete ownership record once, outside the model loop.

    Connectedness comes from the exact strict parser that supplied this role.
    This check does not broaden its domain or create roles for failed parses.
    """
    if(type(role)is not dict or set(role)!=ROLE_FIELDS
       or type(role['background'])is not int or not 0<=role['background']<=9
       or type(role['foreground'])is not int or not 0<=role['foreground']<=9
       or role['background']==role['foreground']
       or type(role['input_shape'])is not list or len(role['input_shape'])!=2
       or any(type(v)is not int for v in role['input_shape'])
       or role['input_shape']!=[len(grid),len(grid[0])]
       or not valid_grid(role['mask'])or any(v not in(0,1)for row in role['mask']for v in row)
       or type(role['bbox'])is not list or len(role['bbox'])!=4 or any(type(v)is not int for v in role['bbox'])
       or type(role['foreground_count'])is not int or type(role['background_count'])is not int
       or type(role['ownership'])is not str
       or role['ownership']!='complete foreground single C8 + all remaining input background'):
        return False
    bg,fg=role['background'],role['foreground']
    if {v for row in grid for v in row}!={bg,fg}:return False
    expected=[(r,c,fg)for r,row in enumerate(grid)for c,v in enumerate(row)if v==fg]
    if not expected:return False
    count=len(expected);background_count=len(grid)*len(grid[0])-count
    if (background_count<=count or role['foreground_count']!=count or role['background_count']!=background_count
        or type(role['cells'])is not list or role['cells']!=expected
        or any(type(cell)is not tuple or any(type(v)is not int for v in cell)for cell in role['cells'])):return False
    r0,c0,r1,c1=min(r for r,_,_ in expected),min(c for _,c,_ in expected),max(r for r,_,_ in expected),max(c for _,c,_ in expected)
    if role['bbox']!=[r0,c0,r1,c1]:return False
    return role['mask']==[[int(grid[r][c]==fg)for c in range(c0,c1+1)]for r in range(r0,r1+1)]


@dataclass(frozen=True,slots=True)
class StrictRoleWitness:
    background:int
    foreground:int
    input_shape:tuple
    bbox:tuple
    cells:tuple
    mask:tuple
    foreground_count:int
    background_count:int
    ownership:str


@dataclass(frozen=True,slots=True,init=False)
class TeacherWitness:
    teacher_index:int
    input:tuple|None
    target:tuple|None
    role:StrictRoleWitness|None
    reason:str|None
    target_colors:tuple
    target_shape:tuple
    complete:bool
    incomplete_reason:str|None

    def __init__(self,teacher_index,pair,parsed):
        # This constructor is outside the model loop. Failed validation, absent
        # role or malformed role yields no certificate, rather than a refutation.
        fields={'teacher_index':teacher_index,'input':None,'target':None,'role':None,
                'reason':None,'target_colors':(),'target_shape':(),'complete':False,
                'incomplete_reason':'invalid_or_absent_teacher_witness'}
        if (type(teacher_index)is int and teacher_index>=0 and type(pair)is dict
            and set(pair)=={'input','output'} and valid_grid(pair['input'])and valid_grid(pair['output'])
            and type(parsed)is dict and set(parsed)=={'role','reason'}):
            role,reason=parsed['role'],parsed['reason']
            fields.update(input=tuple(tuple(row)for row in pair['input']),target=tuple(tuple(row)for row in pair['output']),
                          reason=reason,
                          target_colors=tuple(sorted({v for row in pair['output']for v in row})),
                          target_shape=(len(pair['output']),len(pair['output'][0])))
            if role is None or reason is not None:
                fields['incomplete_reason']='strict_input_role_absent_or_failed'
            elif complete_role_witness(role,pair['input']):
                # The exact strict parser supplied this complete role. The full
                # source role/input are retained, not recomputed from a query.
                frozen_role=StrictRoleWitness(role['background'],role['foreground'],tuple(role['input_shape']),
                    tuple(role['bbox']),tuple(role['cells']),tuple(tuple(row)for row in role['mask']),
                    role['foreground_count'],role['background_count'],role['ownership'])
                fields.update(role=frozen_role,complete=True,incomplete_reason=None)
            else:fields['incomplete_reason']='malformed_strict_input_role'
        for key,value in fields.items():object.__setattr__(self,key,value)


def witness_record(witness):
    if type(witness)is not TeacherWitness:return {'complete':False,'incomplete_reason':'absent_typed_witness'}
    record=asdict(witness)
    if record['input']is not None:record['input']=[list(row)for row in witness.input]
    if record['target']is not None:record['target']=[list(row)for row in witness.target]
    if witness.role is not None:
        record['role'].update(input_shape=list(witness.role.input_shape),bbox=list(witness.role.bbox),
            cells=list(witness.role.cells),mask=[list(row)for row in witness.role.mask])
    else:record['raw_role_source_ref']=witness.teacher_index
    return record


def certify_teacher(witness,spec,model_index):
    result={'model_index':model_index,'teacher_witness_ref':witness.teacher_index if type(witness)is TeacherWitness else None,
            'necessary_only':True,'status':'inconclusive','refuted':False}
    if (type(model_index)is not int or not 0<=model_index<len(SPECS)
        or not valid_spec(spec)or SPECS[model_index]!=spec):
        return dict(result,reason='invalid_or_mismatched_model_spec')
    if type(witness)is not TeacherWitness or witness.complete is not True:
        return dict(result,reason='incomplete_teacher_witness')
    role=witness.role
    allowed=tuple(sorted({role.background,spec[6],spec[7]}))
    missing=tuple(color for color in witness.target_colors if color not in allowed)
    mh,mw=len(role.mask),len(role.mask[0])
    if spec[3]in SWAPPED_TRANSFORMS:mh,mw=mw,mh
    ih,iw=role.input_shape
    shape=(5*mh+1,5*mw+1)if spec[0]=='motif5plus1'else(3*ih-2,3*iw-2)
    shape_mismatch=shape!=witness.target_shape
    refuted=bool(missing or shape_mismatch)
    return dict(result,status='refuted'if refuted else'not_refuted',refuted=refuted,
                allowed_colors=allowed,target_colors=witness.target_colors,
                missing_target_colors=missing,transformed_mask_shape=(mh,mw),
                expected_output_shape=shape,target_shape=witness.target_shape,
                shape_mismatch=shape_mismatch)


def fit(teachers,observer=None):
    valid,validation=validate_teachers(teachers)
    if not valid:return base.fit(teachers,observer)
    pre_parsed=[];parsed=[];witnesses=[];witness_records=[];certificates=[]
    actual_rows=[];symbolic_slots=[];completed=[];retained=[];pool=Returns(observer)
    model_index=teacher_index=None;spec=None;pending=None;result=None
    certificate_rows=[];pending_certificate=None;exact=None;exacts=[]
    role=reason=None;slot=None;symbolic_committed=False;phase='strict_prepass'
    fallback_started=fallback_returned=False;fallback_models=None;fallback_record=None
    try:
        # Same complete, parameter-independent strict prepass as recovered032.
        for teacher_index,pair in enumerate(teachers):
            role=reason=None
            role,reason=core.parse(pair['input'])
            pre_parsed.append({'teacher_index':teacher_index,'role':role,'reason':reason})
            emit(observer,{'kind':'proof_teacher_parsed',**pre_parsed[-1]})
        failures=[p['teacher_index']for p in pre_parsed if p['role']is None]
        if failures:
            record=dict(validation,fit_method=METHOD,original_strict_fit_executed=False,
                program_count=len(SPECS),retained_count=0,complete_program_teacher_evaluations=0,
                actual_parse_invocations=len(pre_parsed),proof_parse_invocations=len(pre_parsed),
                actual_action_invocations=0,unexecuted_program_teacher_evaluations=len(SPECS)*len(teachers),
                accounted_program_teacher_slots=len(SPECS)*len(teachers),parsed_teachers=pre_parsed,
                return_pool=[],model_teacher_returns=[],completed_models=[],failure='no_model_fits_all_teachers',
                fit_domain_proof={'disposition':'proven_empty','failed_teacher_indices':failures,
                    'premise':'Every declared action requires the same successful parameter-independent input parse.',
                    'conclusion':'A complete parse failure on any teacher makes simultaneous exact teacher fit impossible for every model.'},
                unexecuted_domain={'model_index_start':0,'model_index_stop_exclusive':len(SPECS),
                    'model_identity':'SPECS ordered exact Cartesian grammar','fields':FIELDS,
                    'teacher_indices':tuple(range(len(teachers))),'action_calls_executed':False,'rendered_returns':False})
            emit(observer,{'kind':'teacher_fit_proven_empty','record':record})
            return (),record
        emit(observer,{'kind':'teacher_validation','valid':True,'record':validation})
        # Keep the recovered base fitter's second parse pass and its actual roles.
        phase='strict_second_parse_and_witness'
        for teacher_index,pair in enumerate(teachers):
            role=reason=None
            role,reason=core.parse(pair['input']);parsed.append({'role':role,'reason':reason})
            emit(observer,{'kind':'teacher_parsed','teacher_index':teacher_index,**parsed[-1]})
            witness=TeacherWitness(teacher_index,pair,parsed[-1]);witnesses.append(witness)
            witness_records.append(witness_record(witness))
            emit(observer,{'kind':'teacher_necessity_witness','witness':witness_records[-1]})
        phase='model_certificates'
        for model_index,spec in enumerate(SPECS):
            certificate_rows=[];pending_certificate=None
            for teacher_index,witness in enumerate(witnesses):
                pending_certificate=None
                pending_certificate=certify_teacher(witness,spec,model_index)
                certificate_rows.append(pending_certificate)
            certificate={'model_index':model_index,'spec':spec,'teacher_witnesses':certificate_rows,
                         'refuting_teacher_indices':[c['teacher_witness_ref']for c in certificate_rows if c['refuted']]}
            certificates.append(certificate)
            emit(observer,{'kind':'model_necessity_certificate','certificate':certificate})
        certificate_rows=[];pending_certificate=None
        if not any(c['refuting_teacher_indices']for c in certificates):
            phase='exact_strict_fallback';fallback_started=True
            fallback_models,fallback_record=strict.fit(teachers,observer);fallback_returned=True
            record=dict(fallback_record,fit_method=METHOD+'-exact-strict-fallback',original_strict_fit_executed=True,
                certificate_preparation_parse_invocations=len(pre_parsed)+len(parsed),
                actual_parse_invocations=len(pre_parsed)+len(parsed)+fallback_record.get('actual_parse_invocations',0),
                proof_parse_invocations=len(pre_parsed)+fallback_record.get('proof_parse_invocations',0),
                teacher_necessity_witnesses=witness_records,model_necessity_certificates=certificates,
                certificate_evaluations=len(SPECS)*len(teachers),symbolic_model_teacher_slots=[],
                symbolically_unexecuted_program_teacher_evaluations=0,
                accounted_program_teacher_slots=fallback_record.get('complete_program_teacher_evaluations',0)+fallback_record.get('unexecuted_program_teacher_evaluations',0),
                original_strict_record=fallback_record)
            emit(observer,{'kind':'necessity_exact_fallback_completed','summary':{
                'certificate_count':len(certificates),'certificate_refutations':0,
                'preparation_parse_invocations':len(pre_parsed)+len(parsed),
                'original_parse_invocations':fallback_record.get('actual_parse_invocations',0),
                'retained_count':len(fallback_models)}})
            return fallback_models,record
        phase='actual_or_symbolic_evaluation'
        for model_index,spec in enumerate(SPECS):
            certificate=certificates[model_index]
            refuting=certificate['refuting_teacher_indices']
            if refuting:
                for teacher_index in range(len(teachers)):
                    slot=None;symbolic_committed=False
                    slot={'model_index':model_index,'teacher_index':teacher_index,'model_certificate_ref':model_index,
                          'refuting_teacher_indices':tuple(refuting),'action_executed':False,'actual_return_known':False,
                          'exactness':'proven_not_exact'if teacher_index in refuting else'unknown_model_refuted_elsewhere'}
                    symbolic_slots.append(slot)
                    symbolic_committed=True
                    emit(observer,{'kind':'symbolic_model_teacher_slot',**slot})
                item={'model_index':model_index,'retained':False,'evaluation':'symbolic_refutation',
                      'model_certificate_ref':model_index,'proven_not_exact_teacher_indices':tuple(refuting),
                      'unexecuted_unknown_exact_teacher_indices':tuple(i for i in range(len(teachers))if i not in refuting)}
            else:
                exacts=[]
                for teacher_index,pair in enumerate(teachers):
                    pending=None;result=None;parse=parsed[teacher_index]
                    result=apply(parse['role'],parse['reason'],spec)
                    pending={'model_index':model_index,'teacher_index':teacher_index,'return':result,
                             'row_committed':False,'action_executed':parse['role']is not None}
                    exact=result['status']=='success'and valid_grid(result['output'])and result['output']==pair['output']
                    row={'model_index':model_index,'teacher_index':teacher_index,'return_ref':pool.add(result),
                         'full_grid_fit':exact,'parse_reused':True,'action_executed':parse['role']is not None}
                    actual_rows.append(row);pending['row_committed']=True;exacts.append(exact)
                    emit(observer,{'kind':'model_teacher_return',**row})
                pending=None;result=None
                item={'model_index':model_index,'teacher_exacts':exacts,'retained':all(exacts),'evaluation':'actual'}
                if all(exacts):retained.append((model_index,)+spec)
            completed.append(item)
            emit(observer,{'kind':'model_completed',**item})
        phase='finalize'
        record=dict(validation,fit_method=METHOD,original_strict_fit_executed=False,
            program_count=len(SPECS),retained_count=len(retained),actual_parse_invocations=len(pre_parsed)+len(parsed),
            proof_parse_invocations=len(pre_parsed),parsed_teachers=parsed,
            fit_domain_proof={'disposition':'per_model_necessary_conditions','parsed_teachers':pre_parsed},
            teacher_necessity_witnesses=witness_records,model_necessity_certificates=certificates,
            certificate_evaluations=len(SPECS)*len(teachers),symbolic_model_teacher_slots=symbolic_slots,
            symbolically_unexecuted_program_teacher_evaluations=len(symbolic_slots),
            unexecuted_program_teacher_evaluations=len(symbolic_slots),
            complete_program_teacher_evaluations=len(actual_rows),accounted_program_teacher_slots=len(actual_rows)+len(symbolic_slots),
            actual_action_invocations=sum(r['action_executed']for r in actual_rows),
            return_pool=pool.pool,model_teacher_returns=actual_rows,completed_models=completed,
            failure=None if retained else'no_model_fits_all_teachers')
        emit(observer,{'kind':'necessity_fit_completed','summary':{
            'program_count':len(SPECS),'teacher_count':len(teachers),'retained_count':len(retained),
            'actual_teacher_rows':len(actual_rows),'symbolic_teacher_slots':len(symbolic_slots),
            'accounted_teacher_slots':len(actual_rows)+len(symbolic_slots)}})
        return tuple(retained),record
    except BaseException as error:
        try:
            previous_diagnostic=getattr(error,'evaluation_diagnostic',None)
            attach_exception(error,{'stage':'necessity_fit','phase':phase,'exception':type(error).__name__,'message':str(error),
                'model_index':model_index,'teacher_index':teacher_index,'spec':spec,
                'raw_pending_parse_role':role,'raw_pending_parse_reason':reason,
                'proof_parsed_teachers':pre_parsed,'parsed_teachers':parsed,'teacher_necessity_witnesses':witness_records,
                'model_necessity_certificates':certificates,'pending_certificate_rows':certificate_rows,
                'raw_pending_certificate':pending_certificate,'return_pool':pool.pool,
                'model_teacher_returns':actual_rows,'symbolic_model_teacher_slots':symbolic_slots,
                'completed_models':completed,'retained_prefix':tuple(retained),'pending_return':pending,
                'raw_pending_return':result,'completed_actual_returns':len(actual_rows),
                'raw_pending_symbolic_slot':slot,'symbolic_slot_committed':symbolic_committed,
                'original_strict_fallback_started':fallback_started,'original_strict_fallback_returned':fallback_returned,
                'original_strict_fallback_models':fallback_models,'original_strict_fallback_record':fallback_record,
                'original_strict_diagnostic':previous_diagnostic,
                'completed_symbolic_slots':len(symbolic_slots),'planned_slots':len(SPECS)*len(teachers),
                'semantic_HOLD':False},observer)
        except BaseException:pass
        raise
