"""Public synthetic proof controls; every witness checked by the original renderer."""
import copy,gzip,hashlib,itertools,json
from collections import Counter
from functools import lru_cache

def verify(adapter,fitted,fixtures,directory):
    core=adapter.core;source=gzip.decompress((fixtures/'prototype.py.gz').read_bytes()).decode()
    original=dict(itertools=itertools,Counter=Counter,lru_cache=lru_cache,regions=core.regions,features=core.features,canonical_shape=core.canonical_shape)
    exec(compile(source[source.index('FEATURES='):],str(fixtures/'prototype.py.gz'),'exec'),original)
    def save(name,value):(directory/name).write_bytes(gzip.compress(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    def grid(refs,colors):
        g=[[8]*9 for _ in range(12)];g[3]=[6]*9;g[10]=[6]*9
        for i,color in enumerate(refs):g[1][1+3*i]=color
        for i,color in enumerate(colors):g[5+3*(i//2)][1+3*(i%2)]=color
        assert core.parse(g)[0]is not None
        return g
    def model(policy='injective_multiset',region='lattice_halo'):
        return ('C8','colored_exact',policy,'any_complete_line','on_success',region)
    cases=[('non_injective',grid([1],[1,1,1,1]),model('set_membership')),
           ('match_sets_differ',grid([1,2],[1,2,1,2]),model()),
           ('fewer_slots_than_references',grid([1,1,1],[1,1,2,2]),model()),
           ('exactly_enough_slots',grid([1,1],[1,1,2,2]),model()),
           ('no_matching_slots',grid([3],[1,1,2,2]),model()),
           ('complete_outputs_agree',grid([1],[1,1,1,1]),model(region='tight_bbox'))]
    rows=[]
    for name,g,m in cases:
        events=[];calls=[];old=core.selections
        def selections(*args,**kwargs):calls.append(True);return old(*args,**kwargs)
        core.selections=selections
        try:output,record=core.render(g,m,(3,2),observer=events.append)
        finally:core.selections=old
        expected,detail=original['render'](g,m,(3,2))
        assert len(calls)==1 and output==expected and not any(e['kind']=='allocation_disagreement_proved'for e in events),name
        if name=='complete_outputs_agree':assert output is not None and sum(e['kind']=='allocation_witness_return'for e in events)==2
        rows.append({'name':name,'input':g,'model':m,'output':output,'record':record,'original_output':expected,'original_record':detail,'events':events,'original_selection_calls':len(calls)})
    save('proof-negative-fallback-cases.json.gz',rows)
    g=grid([1],[1,1,1,1]);m=model();events=[];output,record=core.render(g,m,(3,2),observer=events.append)
    assert output is None and record['failure']=='allocation_disagreement';proof=record['allocation_disagreement_proof']
    assert proof['domain']['selected_set_count']==proof['domain']['ordered_allocation_count']==4
    assert proof['unexecuted_selected_sets']==proof['unexecuted_ordered_allocations']==2
    fixture=json.loads(gzip.decompress((fixtures/'allocation-proof-control.json.gz').read_bytes()));stressgrid=fixture['input'];events=[]
    output,stress=fitted.候補(stressgrid,{},events.append);assert output is None
    assert len(stress['returns'])==fixture['expected_retained_models']==30
    proved=[r for r in stress['returns']if 'allocation_disagreement_proof'in r['record']]
    assert len(proved)==fixture['expected_proved_injective_models']==15
    for result,expected in zip(proved,fixture['proofs']):
        p=result['record']['allocation_disagreement_proof']
        assert list(result['model'])==expected['retained_model']and list(result['colors'])==expected['colors']
        assert all(p['domain'][k]==v for k,v in fixture['domain'].items())
        assert [w['output_sha256']for w in p['witnesses']]==expected['output_hashes']
        assert all(p[k]==expected[k]for k in ('differing_cell','unexecuted_selected_sets','unexecuted_ordered_allocations'))
    save('proof-stress-all30-full-returns.json.gz',{'input':stressgrid,'output':output,'record':stress,'events':events})
    witnesses=[]
    for casegrid,casemodel,casecolors,caseproof in [(g,m,(3,2),proof)]+[(stressgrid,tuple(r['model']),tuple(r['colors']),r['record']['allocation_disagreement_proof'])for r in proved]:
        parsed,_=original['parse'](casegrid,casemodel[0])
        _,match=original['selections'](parsed,casemodel[1],'set_membership')
        for witness in caseproof['witnesses']:
            mapping=[(i,tuple(slot))for i,slot in witness['assignments']]
            assert [i for i,slot in mapping]==list(range(len(parsed['references'])))
            assert len({slot for i,slot in mapping})==len(mapping)
            assert all(slot in match['reference_matches'][i]for i,slot in mapping)
            selected=frozenset(slot for i,slot in mapping);old=original['selections']
            original['selections']=lambda p,f,policy:([selected],{})
            try:expected,detail=original['render'](casegrid,casemodel,casecolors)
            finally:original['selections']=old
            assert expected==witness['output']and json.dumps(detail['allocations'],sort_keys=True)==json.dumps([witness['record']],sort_keys=True)
            assert hashlib.sha256(json.dumps(expected,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==witness['output_sha256']
            witnesses.append({'model':casemodel,'colors':casecolors,'witness':witness,'original_full_renderer_equal':True,'complete_injection_independently_verified':True})
    save('proof-all32-original-renderer-comparisons.json.gz',witnesses)
    fit_teachers=[]
    for separator in (6,7):
        inp=copy.deepcopy(g);inp[3]=[separator]*9;inp[10]=[separator]*9;out=copy.deepcopy(inp)
        for r in range(4,10):
            for c in range(6):
                if out[r][c]==8:out[r][c]=3
        out[11]=[2]*9;fit_teachers.append({'input':inp,'output':out})
    errors=[]
    for exception in (MemoryError,RecursionError,TimeoutError):
        for mode in ('fit','prediction'):
            events=[];count=[0];old=core._allocation_witness_output
            def interrupted(*args,**kwargs):
                if count[0]==1:raise exception('second complete witness interrupted')
                count[0]+=1;return old(*args,**kwargs)
            core._allocation_witness_output=interrupted
            try:
                if mode=='fit':adapter.fit(fit_teachers,events.append)
                else:adapter.predict(g,((m,(3,2)),),events.append)
                raise AssertionError('resource error swallowed')
            except exception:
                e=events[-1];assert e['kind']=='evaluation_exception'and e['semantic_HOLD']is False
                prefix=e['partial_current_model']['proof_witness_prefix'];assert len(prefix)==1 and prefix[0]['witness']['output']==proof['witnesses'][0]['output']
                errors.append({'exception':exception.__name__,'mode':mode,'events':events})
            finally:core._allocation_witness_output=old
    save('proof-completed-witness-resource-prefixes.json.gz',errors)
    old=core._allocation_witness_output;old_selections=core.selections;events=[];calls=[]
    def invalid(*args,**kwargs):return None,{'failure':'injected_invalid_complete_render'}
    def selected(*args,**kwargs):calls.append(True);return old_selections(*args,**kwargs)
    core._allocation_witness_output=invalid;core.selections=selected
    try:output,record=core.render(g,m,(3,2),events.append)
    finally:core._allocation_witness_output=old;core.selections=old_selections
    assert len(calls)==1 and not any(e['kind']=='allocation_disagreement_proved'for e in events)
    save('proof-invalid-complete-render-fallback.json.gz',{'output':output,'record':record,'events':events})
    # Consecutive renders inside one model: second parse fails before any proof.
    events=[];trace=adapter._Trace(events.append,'teacher_fit')
    trace({'kind':'model_start','model_index':0,'model':m})
    core.render(g,m,(3,2),observer=trace)
    assert 'proof_domain'in trace.active and len(trace.active['proof_witness_prefix'])==2
    old=core.parse
    def early_failure(*args,**kwargs):raise MemoryError('second render interrupted before proof')
    core.parse=early_failure
    try:
        core.render(g,m,(3,2),observer=trace);raise AssertionError('resource error swallowed')
    except MemoryError as error:trace.exception(error)
    finally:core.parse=old
    partial=events[-1]['partial_current_model']
    assert 'proof_domain'not in partial and partial['proof_witness_prefix']==[]
    assert sum(e['kind']=='render_start'for e in events)==2
    save('proof-consecutive-render-reset.json.gz',{'events':events,'no_stale_proof_domain':True})
    return {'successful':True,'negative_fallback_cases':7,'original_full_renderer_witnesses':len(witnesses),'resource_prefix_cases':len(errors),'consecutive_render_reset_cases':1,'stress_models':30,'proved_stress_models':15}
