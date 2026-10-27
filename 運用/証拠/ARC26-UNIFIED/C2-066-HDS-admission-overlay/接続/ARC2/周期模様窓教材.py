"""A pure input-parse impossibility proof; otherwise the unchanged finite fitter."""
from . import 周期模様窓基底教材 as _base
from .周期模様窓基底教材 import *

def fit(teachers,observer=None):
    valid,validation=validate_teachers(teachers)
    if not valid:return _base.fit(teachers,observer)
    parsed=[];teacher_index=None;raw_role=None;raw_reason=None
    try:
        for teacher_index,pair in enumerate(teachers):
            raw_role=raw_reason=None
            raw_role,raw_reason=core.parse(pair['input'])
            parsed.append({'teacher_index':teacher_index,'role':raw_role,'reason':raw_reason})
            emit(observer,{'kind':'proof_teacher_parsed',**parsed[-1]})
        failures=[p['teacher_index'] for p in parsed if p['role'] is None]
        if failures:
            record=dict(validation,program_count=len(SPECS),retained_count=0,complete_program_teacher_evaluations=0,
                actual_parse_invocations=len(parsed),proof_parse_invocations=len(parsed),actual_action_invocations=0,
                unexecuted_program_teacher_evaluations=len(SPECS)*len(teachers),parsed_teachers=parsed,
                return_pool=[],model_teacher_returns=[],completed_models=[],failure='no_model_fits_all_teachers',
                fit_domain_proof={'disposition':'proven_empty','failed_teacher_indices':failures,
                    'premise':'Every declared action requires the same successful parameter-independent input parse.',
                    'conclusion':'A complete parse failure on any teacher makes simultaneous exact teacher fit impossible for every model.'},
                unexecuted_domain={'model_index_start':0,'model_index_stop_exclusive':len(SPECS),
                    'model_identity':'SPECS ordered exact Cartesian grammar','fields':FIELDS,
                    'teacher_indices':tuple(range(len(teachers))),'action_calls_executed':False,
                    'rendered_returns':False})
            emit(observer,{'kind':'teacher_fit_proven_empty','record':record})
            return (),record
    except BaseException as error:
        try:
            attach_exception(error,{'stage':'fit_domain_proof','exception':type(error).__name__,'message':str(error),
                'teacher_index':teacher_index,'parsed_teacher_prefix':parsed,'raw_role':raw_role,'raw_reason':raw_reason,
                'model_teacher_returns':[],'completed_models':[],'completed_returns':0,'actual_action_invocations':0,'semantic_HOLD':False},observer)
        except BaseException:pass
        raise
    models,record=_base.fit(teachers,observer)
    try:
        record['proof_parse_invocations']=len(parsed)
        record['actual_parse_invocations']+=len(parsed)
        record['fit_domain_proof']={'disposition':'all_parse_fallback','parsed_teachers':parsed}
    except BaseException as error:
        try:attach_exception(error,record,observer)
        except BaseException:pass
        raise
    return models,record

@dataclass(frozen=True,init=False,slots=True)
class 周期模様窓教材:
    モデル群:tuple
    教師数:int
    不足理由:str|None
    def __init__(self,教師群,監査=None,観測=None):
        models,record=fit(教師群,観測)
        object.__setattr__(self,'モデル群',models);object.__setattr__(self,'教師数',record['teacher_count']);object.__setattr__(self,'不足理由',record.get('failure'))
        if 監査 is not None:監査.update(record)
    def 候補(self,格子,_policy,観測=None):return predict(格子,self.モデル群,観測)
    def 展開モデル(self):return [{'model_index':m[0],'spec':dict(zip(FIELDS,m[1:]))} for m in self.モデル群]
    def 記録(self):return {'保持候補数':len(self.モデル群),'保持候補':self.展開モデル(),'教師数':self.教師数,'教師fit最小数':2,'不足理由':self.不足理由,'固定prior':'finite motif extent/window/center/D4/phase/overlay hypotheses; preserve every alternative'}
