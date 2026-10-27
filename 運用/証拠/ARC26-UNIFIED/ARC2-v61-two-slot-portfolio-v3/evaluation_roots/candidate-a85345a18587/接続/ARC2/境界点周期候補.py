"""Pure frozen point-pair experiment. No task names, teacher outputs or external IO."""
from collections import Counter, defaultdict
from .既存凡例穴対応 import clone_grid, grid_shape
from .既存行周期 import superposed_cell_value

DIRECTIONS=('right','left','down','up')
def valid_grid(g):
    return (type(g) is list and 1<=len(g)<=30 and type(g[0]) is list and 1<=len(g[0])<=30 and all(type(row)is list and len(row)==len(g[0]) and all(type(v)is int and 0<=v<=9 for v in row)for row in g))

def line_cells(h,w,direction):
    if direction in ('right','left'):
        return [[(r,c)for c in (range(w)if direction=='right'else range(w-1,-1,-1))]for r in range(h)]
    return [[(r,c)for r in (range(h)if direction=='down'else range(h-1,-1,-1))]for c in range(w)]

def parse(g):
    if not valid_grid(g):return None,{'failure':'invalid_arc_grid','grid':g}
    counts=Counter(v for row in g for v in row); maximum=max(counts.values())
    leaders=[c for c in range(10)if counts[c]==maximum]
    roles=[{'color':c,'count':counts[c],'role_eligible':c in leaders,'reason':'modal'if c in leaders else 'not_modal'}for c in range(10)]
    if len(leaders)!=1:return None,{'failure':'background_tie','background_alternatives':roles}
    bg=leaders[0];h,w=grid_shape(g);directions=[]
    for direction in DIRECTIONS:
        records=[];active=0
        for line_index,cells in enumerate(line_cells(h,w,direction)):
            vals=[g[r][c]for r,c in cells];fg=[i for i,v in enumerate(vals)if v!=bg]
            rec={'line_index':line_index,'cells':cells,'values':vals,'foreground_indices':fg}
            if not fg:
                rec.update(status='inactive_background',pair_candidates=[]);records.append(rec);continue
            active+=1;s=vals[0]
            candidates=[i for i in range(1,len(vals))if vals[i]==s]if s!=bg else []
            rec.update(seed_color=s,pair_candidates=[{'distance':p,'first':cells[0],'second':cells[p]}for p in candidates])
            if s==bg:rec.update(status='invalid',reason='foreground_line_missing_boundary_seed')
            elif len(candidates)!=1:rec.update(status='invalid',reason='seed_color_occurrence_count_not_two')
            else:
                p=candidates[0];foreign=[{'index':i,'cell':cells[i],'color':vals[i],'on_phase':i%p==0}for i in fg if vals[i]!=s]
                rec.update(status='valid',period=p,foreign_points=foreign,explained_foreground_count=2+len(foreign))
            records.append(rec)
        valid=active>0 and all(x['status']!='invalid'for x in records)
        directions.append({'direction':direction,'valid':valid,'active_lines':active,'lines':records,'reason':'all_foreground_explained_by_boundary_pairs'if valid else 'invalid_active_line_or_no_foreground'})
    raw=[x for x in directions if x['valid']]
    evidence={'background':bg,'background_alternatives':roles,'directions':directions,'raw_valid_direction_count':len(raw)}
    if len(raw)!=1:return None,dict(evidence,failure='raw_direction_not_unique')
    return {'background':bg,'direction':raw[0]['direction'],'lines':raw[0]['lines']},evidence

def merge_proposals(g,proposals):
    cells=defaultdict(set)
    for r,c,color in proposals:cells[r,c].add(color)
    conflicts=[{'cell':[r,c],'colors':sorted(cs)}for (r,c),cs in sorted(cells.items())if len(cs)>1]
    if conflicts:return None,{'failure':'proposal_color_collision','conflicts':conflicts}
    out=clone_grid(g)
    for (r,c),cs in cells.items():out[r][c]=next(iter(cs))
    return out,{'proposal_cells':len(cells),'proposals':[{'cell':[r,c],'color':next(iter(cs))}for (r,c),cs in sorted(cells.items())]}

def render(g,model):
    parsed,parse_record=parse(g)
    if parsed is None:return None,{'status':'HOLD','parse':parse_record,'reason':parse_record['failure']}
    bg=parsed['background'];proposals=[];line_records=[];errors=[]
    for line in parsed['lines']:
        if line['status']=='inactive_background':continue
        p=line['period'];cells=line['cells'];seed=line['seed_color'];foreign=line['foreign_points']
        terminals=[x for x in foreign if model['terminal_phase']=='any_foreign' or x['on_phase']]
        passthrough=[x for x in foreign if x not in terminals]
        rec={'line_index':line['line_index'],'period':p,'seed_color':seed,'terminal_candidates':terminals,'passthrough_foreign':passthrough}
        if len(terminals)>1:
            rec['failure']='multiple_terminal_candidates';errors.append(rec);line_records.append(rec);continue
        if terminals and terminals[0]['index']<=p:
            rec['failure']='terminal_not_after_seed_pair';errors.append(rec);line_records.append(rec);continue
        terminal=terminals[0]if terminals else None
        end=terminal['index']if terminal and model['stop']=='terminal'else len(cells)-1
        paint=terminal['color']if terminal and model['paint']=='terminal'else seed
        local=[]
        for distance in range(end+1):
            color=superposed_cell_value([{'color':paint,'length':p}],distance,bg)
            if color==bg:continue
            r,c=cells[distance]
            if terminal and distance==terminal['index']:color=terminal['color']
            local.append([r,c,color])
        rec.update(stop_index=end,paint_color=paint,proposal=local);line_records.append(rec);proposals.extend(local)
    record={'parse':parse_record,'model':model,'lines':line_records}
    if errors:return None,dict(record,status='HOLD',reason='terminal_role_unresolved',errors=errors)
    out,merge=merge_proposals(g,proposals);record['merge']=merge
    if out is None:return None,dict(record,status='HOLD',reason=merge['failure'])
    proposed={(r,c)for r,c,_ in proposals}
    preserved=[(r,c)for r,row in enumerate(g)for c,_ in enumerate(row)if(r,c)not in proposed]
    if any(out[r][c]!=g[r][c]for r,c in preserved):raise AssertionError('conservation failure')
    for rec in line_records:
        for point in rec['passthrough_foreign']:
            r,c=point['cell']
            if out[r][c]!=g[r][c]:raise AssertionError('off-phase conservation failure')
    record.update(status='OUTPUT',reason='complete_finite_relation',preserved_cells=len(preserved),changed_cells=sum(a!=b for x,y in zip(g,out)for a,b in zip(x,y)))
    return out,record

def fit(pairs,models):
    if len(pairs)<2:return [],{'failure':'insufficient_distinct_teachers'}
    if len({tuple(map(tuple,p['input']))for p in pairs})!=len(pairs):return [],{'failure':'duplicate_teacher_inputs'}
    records=[];fitted=[]
    for model in models:
        results=[]
        for i,pair in enumerate(pairs):
            out,rec=render(pair['input'],model)
            results.append({'teacher':i,'input':pair['input'],'target':pair['output'],'output':out,'exact':out==pair['output'],'record':rec})
        accepted=all(r['exact']for r in results)
        records.append({'model':model,'accepted':accepted,'teachers':results})
        if accepted:fitted.append(model)
    return fitted,{'hypotheses':records,'fitted_models':fitted}

def predict(g,models):
    if not models:return None,{'reason':'no_fitted_models','alternatives':[]}
    results=[{'model':m,'output':o,'record':r}for m in models for o,r in [render(g,m)]]
    if any(r['output']is None for r in results):return None,{'reason':'unresolved_fitted_model','alternatives':results}
    outputs={tuple(map(tuple,r['output']))for r in results}
    if len(outputs)!=1:return None,{'reason':'fitted_model_output_disagreement','alternatives':results}
    return results[0]['output'],{'reason':'all_fitted_models_agree','alternatives':results}

MODEL_KEYS = ('model_id', 'terminal_phase', 'stop', 'paint')
PROGRAMS = (('m00', 'aligned', 'terminal', 'terminal'), ('m01', 'aligned', 'terminal', 'seed'), ('m02', 'aligned', 'boundary', 'terminal'), ('m03', 'aligned', 'boundary', 'seed'), ('m04', 'any_foreign', 'terminal', 'terminal'), ('m05', 'any_foreign', 'terminal', 'seed'), ('m06', 'any_foreign', 'boundary', 'terminal'), ('m07', 'any_foreign', 'boundary', 'seed'))
