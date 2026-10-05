"""有限候補fit結果の教師・負例・合成/metamorphic検証。"""
import copy, importlib, itertools, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.距離回収候補 import fit, render, consensus, parse, ROLE_NAMES
from 接続.ARC2 import 距離回収教材 as wrapper
from 接続.ARC2.HDS接続 import HDS学習実行系,候補機構を学習
REPORTS={}
def load_teachers():
    return json.loads((Path(__file__).with_name('fixtures')/'距離回収教師.json').read_text())['train']
def save(name,value):
    REPORTS[name]=value


def run():
    train = load_teachers()
    models, evidence = fit(train)
    results = []
    def check(name, ok, detail=None):
        results.append({'name':name, 'passed':bool(ok), 'detail':detail})
        if not ok: raise AssertionError(name + ': ' + str(detail))
    def prediction(g): return consensus(g, models)
    def blank(n=15):
        g = [[7]*n for _ in range(n)]
        m=n//2
        for r in range(m-1,m+2):
            for c in range(m-1,m+2):g[r][c]=3
        g[m][m]=2
        return g
    def manually_collect(g, selected):
        out=copy.deepcopy(g)
        ts=sorted((r,c) for r,row in enumerate(g) for c,v in enumerate(row) if v in (2,3))
        for r,c in selected:out[r][c]=7
        for r,c in ts[:len(selected)]:out[r][c]=9
        return out
    # 選択/描画はinputとfit結果しか受け取らない。全教師と反実outputのfit拒否。
    for i,p in enumerate(train):
        out, rec=prediction(p['input'])
        check('teacher_exact_'+str(i),out==p['output'])
        check('teacher_input_immutable_'+str(i),out is not p['input'])
    bad=copy.deepcopy(train);bad[0]['output'][0][0]=0
    rejected,diagnostic=fit(bad)
    check('inconsistent_teacher_no_fit',not rejected,{'survivors':len(rejected)})
    # 120 observed-palette permutations + all ten cyclic ARC color rotations.
    observed=sorted(models[0]['roles'].values())
    maps=[dict(zip(observed,p)) for p in itertools.permutations(observed)]
    maps += [{v:(v+shift)%10 for v in observed} for shift in range(10)]
    count=0
    for mapping in maps:
        remap=lambda g:[[mapping[v] for v in row] for row in g]
        mm=copy.deepcopy(models)
        for m in mm:m['roles']={k:mapping[v] for k,v in m['roles'].items()}
        for pair in train:
            out,rec=consensus(remap(pair['input']),mm)
            if out!=remap(pair['output']): raise AssertionError('palette_equivariance')
            count+=1
    check('all_palette_permutations_and_rotations',True,{'grid_comparisons':count,'maps':len(maps)})
    # 盤外への迂回経路を増やさないwall paddingによる平行移動。
    for i,pair in enumerate(train):
        for dy,dx in ((1,1),(2,3),(4,2)):
            def pad(g):
                out=[[6]*(len(g[0])+dx+2) for _ in range(len(g)+dy+2)]
                for r,row in enumerate(g):out[r+dy][dx:dx+len(row)]=row
                return out
            out,rec=prediction(pad(pair['input']))
            check(f'translation_wall_padding_{i}_{dy}_{dx}',out==pad(pair['output']))
    # 各容量1..9。seedは5番目に上書きされる。
    for n in range(1,10):
        g=blank();sources=[(5,c) for c in range(3,3+n)]
        for r,c in sources:g[r][c]=9
        out,rec=prediction(g)
        check('capacity_'+str(n),out==manually_collect(g,sources),{'count':n,'seed_replaced':out[7][7]==9})
    # 全到達不能はsourceを保存して出力不変。8近傍では漏れる角接点もC4では閉鎖。
    g=blank()
    for r in range(5,10):
        for c in range(5,10):
            if r in (5,9) or c in (5,9):g[r][c]=6
    g[1][1]=9
    out,rec=prediction(g)
    check('zero_reachable_preserve_all',out==g,rec)
    g2=copy.deepcopy(g);g2[5][5]=7
    out,rec=prediction(g2)
    check('diagonal_gap_does_not_open_C4',out==g2)
    g3=copy.deepcopy(g);g3[5][7]=7
    out,rec=prediction(g3)
    check('orthogonal_gap_opens_reachability',out==manually_collect(g3,[(1,1)]))
    # 容量超過・cutoffがstrictなら余剰sourceを保存。
    g=blank();sources=[(5,c) for c in range(3,12)]+[(0,0)]
    for r,c in sources:g[r][c]=9
    out,rec=prediction(g)
    check('capacity_overflow_strict_prefix',out==manually_collect(g,sources[:-1]),rec)
    # 8 nearer + 2同距離 => 9番目tieは両仮説ともHOLD。
    near=[(5,7),(9,7),(7,5),(7,9),(4,7),(10,7),(7,4),(7,10)]
    g=blank()
    for r,c in near+[(1,7),(13,7)]:g[r][c]=9
    out,rec=prediction(g)
    check('distance_tie_at_cutoff_HOLD',out is None and all(x['failure']=='capacity_cutoff_distance_tie' for x in rec['failures']),rec)
    # teacherでは区別できない起点を恣意的選択しない。
    g=blank(13)
    near=[(4,6),(8,6),(6,4),(6,8),(3,6),(9,6),(6,3),(6,9)]
    for r,c in near+[(6,12),(3,10)]:g[r][c]=9
    per=[render(g,m['roles'],m['parameters'],m['shape']) for m in models]
    out,rec=prediction(g)
    check('origin_ambiguity_global_HOLD',out is None and sum(x[0] is None for x in per)==1,
          {'model_results':[{'origin':m['parameters']['origin'],'failure':v[1].get('failure'),'selected':v[1].get('selected')} for m,v in zip(models,per)],'consensus':rec})
    # 所有権/語彙/形態逸脱は全体HOLD。
    g=blank();g[1][1]=9
    bad_cases={}
    h=copy.deepcopy(g);h[1][2]=2;bad_cases['duplicate_seed']=h
    h=copy.deepcopy(g);h[7][7]=7;bad_cases['missing_seed']=h
    h=copy.deepcopy(g);h[1][2]=0;bad_cases['unknown_color']=h
    h=copy.deepcopy(g);h[1][2]=3;bad_cases['extra_target_cell']=h
    h=copy.deepcopy(g);h[6][6]=7;bad_cases['missing_target_corner']=h
    h=copy.deepcopy(g);h[7][7],h[6][6]=h[6][6],h[7][7];bad_cases['offcenter_seed']=h
    h=copy.deepcopy(g);h[0].pop();bad_cases['ragged']=h
    h=copy.deepcopy(g);h[1][1]=7;bad_cases['missing_source_role']=h
    h=blank();
    for r in range(5,10):
        for c in range(5,10):h[r][c]=3
    h[7][7]=2;h[1][1]=9;bad_cases['unlearned_5x5_target']=h
    for name,h in bad_cases.items():
        out,rec=prediction(h)
        check(name+'_HOLD',out is None,rec)
    aliases=copy.deepcopy(models)
    for m in aliases:m['roles']['source']=m['roles']['target']
    out,rec=consensus(g,aliases)
    check('aliased_roles_HOLD',out is None,rec)
    # 未採用距離・容量・作用等の各代替仮説について教師全3枚の反証位置を保存。
    base=models[0]
    alternatives={
      'C8':{'metric':'C8_BFS'},'Manhattan':{'metric':'Manhattan'},
      'Chebyshev':{'metric':'Chebyshev'},'Euclidean_squared':{'metric':'Euclidean_squared'},
      'wall_passable':{'wall_passable':True},'source_terminal':{'source_transit':False},
      'farthest':{'ranking':'farthest'},'preserve_seed':{'capacity':'target_color_cells_preserve_seed'},
      'all_reachable_required':{'overflow':'require_all_reachable'},
      'copy_source':{'source_action':'preserve'},'column_major':{'slot_order':'col_asc_row_asc'},
      'reverse_row':{'slot_order':'row_desc_col_asc'},'reverse_column':{'slot_order':'row_asc_col_desc'},
    }
    negatives=[]
    for name,change in alternatives.items():
        p={**base['parameters'],**change};details=[]
        for i,pair in enumerate(train):
            out,rec=render(pair['input'],base['roles'],p,base['shape'])
            diff=[] if out is None else [{'cell':[r,c],'candidate':v,'teacher':pair['output'][r][c]} for r,row in enumerate(out) for c,v in enumerate(row) if v!=pair['output'][r][c]]
            details.append({'teacher_index':i,'exact':out==pair['output'],'failure':rec.get('failure'),'differences':diff,
                            'selected':rec.get('selected'),'reachable_count':rec.get('reachable_count')})
        check('alternative_rejected_'+name,not all(d['exact'] for d in details))
        negatives.append({'alternative':name,'parameters':change,'teachers':details})
    save('negative-alternative-evidence.json',negatives)
    save('test-results.json',{'checks':results,'check_count':len(results),'all_passed':all(x['passed'] for x in results),
                             'palette_grid_comparisons':count,'no_query_or_scorer':True})
    # 新wrapperの型・保持・native支持・全候補観測の接続検査。
    for ci,(bad,reason) in enumerate([([], 'too_few_teachers'), ([train[0]], 'too_few_teachers'),
                       ([train[0],train[0]], 'duplicate_teacher_inputs'),
                       ([train[0],{}], 'invalid_teachers')]):
        mm, rr=wrapper.距離回収をfit(bad)
        check('wrapper_'+str(ci)+'_'+reason,not mm and rr.get('failure')==reason)
    changed=copy.deepcopy(train);changed[0]['output']=[[1]]
    check('wrapper_shape_mismatch',wrapper.距離回収をfit(changed)[1]['failure']=='teacher_shape_not_preserved')
    material=wrapper.距離回収教材(train)
    check('wrapper_all_models_retained',material.展開モデル()==models)
    check('wrapper_immutable_state',isinstance(material.モデル群,tuple) and all(isinstance(x,tuple) and all(isinstance(y,tuple) for y in x) for x in material.モデル群))
    for minimum,admitted in [(3,True),(4,False)]:
        machine=HDS学習実行系(最小支持数=minimum)
        rr=候補機構を学習(machine,{'train':train,'test':[]},(),'ARC距離順位回収',material.候補)
        check('native_support_'+str(minimum),rr['現在観測数']==3 and rr['事前観測数']==0 and rr['同値採用']==admitted and rr['隔離数']==0)
    for ti,pair in enumerate(train):
        a,b=consensus(pair['input'],models);c,d=material.候補(pair['input'],{})
        check('wrapper_consensus_parity_'+str(ti),a==c and b=={k:v for k,v in d.items() if k!='retained_results'})
        check('wrapper_trace_all_models_'+str(ti),len(d['retained_results'])==len(models))
    mut=copy.deepcopy(train);detached=wrapper.距離回収教材(mut);mut[0]['output'][0][0]=0
    check('wrapper_detached_from_targets',detached.候補(train[0]['input'],{})[0]==train[0]['output'])
    print(json.dumps({'successful':True,'tests_run':len(results),'passed_cases':[x['name'] for x in results],
                      'palette_grid_comparisons':count},ensure_ascii=False))

if __name__=='__main__':run()
