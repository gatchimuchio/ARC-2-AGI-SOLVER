"""Frozen finite colored-ray reflection graph; direct production helpers."""
from collections import Counter, defaultdict, deque
from itertools import product
from .凡例旋回教材 import valid_grid, body_components
from .既存対角線橋 import diagonal_segment
from .既存凡例穴対応 import clone_grid
from copy import deepcopy

PROGRAMS = tuple(product((1, -1), ('reflector', 'incoming'), ('reflect', 'absorb')))
NORMALS = ((1, 0), (-1, 0), (0, 1), (0, -1))

def _observe(observer, kind, **values):
    if observer is not None:
        observer(deepcopy({'kind':kind, **values}))

def parse_input(grid, observer=None):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    counts = Counter(x for row in grid for x in row)
    modes = [x for x, n in counts.items() if n == max(counts.values())]
    if len(modes) != 1:
        return None, {'failure': 'background_tie', 'modes': sorted(modes)}
    bg = modes[0]
    glyphs, failed = [], []
    for index, component in enumerate(body_components(grid, bg)):
        cells = component['cells']
        t, l, b, r = component['bbox']
        glyph = dict(id=index, colour=component['color'], cells=sorted(cells), bbox=[t,l,b,r])
        if len(cells) == 1:
            glyph.update(kind='point', center=next(iter(cells)), normals=NORMALS)
        elif len(cells) == 3 and (b-t, r-l) in ((0,2), (2,0)):
            glyph.update(kind='bar', center=((t+b)//2,(l+r)//2),
                         normals=NORMALS[:2] if t == b else NORMALS[2:])
        elif len(cells) == 3 and (b-t,r-l) == (1,1):
            elbows = [p for p in cells if sum(abs(p[0]-q[0])+abs(p[1]-q[1]) == 1 for q in cells) == 2]
            assert len(elbows) == 1
            elbow = elbows[0]
            direction = tuple(-sum(q[a]-elbow[a] for q in cells) for a in (0,1))
            glyph.update(kind='source', center=elbow, direction=direction)
        else:
            glyph.update(kind='unresolved')
            failed.append({'failure':'unrecognized_whole_component', 'glyph':index})
        glyphs.append(glyph)
        _observe(observer, "role_completed", glyph=glyph, failed_roles=failed[-1:] if glyph["kind"] == "unresolved" else [])
    sources = [g for g in glyphs if g['kind']=='source']
    if not sources:
        failed.append({'failure':'no_sources'})
    record = {'background':bg, 'glyphs':glyphs, 'foreground_cells':sum(len(g['cells']) for g in glyphs),
              'sources':[g['id'] for g in sources], 'failed_roles':failed}
    if failed:
        return None, dict(record, failure='role_coverage_failed')
    return dict(background=bg,glyphs=glyphs,sources=sources), record

def render(grid, program, observer=None):
    if tuple(program) not in PROGRAMS:
        return None, {'failure':'invalid_program'}
    scene, record = parse_input(grid, observer=observer)
    _observe(observer, "roles_return", record=record)
    if scene is None:
        return None, record
    sign, turn_colour, point_policy = program
    initial = []
    for g in scene['sources']:
        d = tuple(sign*a for a in g['direction'])
        p = tuple(g['center'][a]+d[a] for a in (0,1))
        initial.append((g['id'],*p,*d,g['colour']))
    return execute_graph(grid, scene, record, program, initial, observer=observer)

def execute_graph(grid, scene, record, program, initial, observer=None):
    """Finite graph engine; render supplies all and only parsed L source states."""
    sign, turn_colour, point_policy = program
    h,w = len(grid),len(grid[0])
    bg = scene['background']
    ports = defaultdict(list)
    for g in scene['glyphs']:
        if g['kind'] == 'source':
            continue
        for n in g['normals']:
            p = tuple(g['center'][a]-n[a] for a in (0,1))
            ports[p].append((g,n))
    pending = deque(initial)
    seen = set()
    states, edges, failures, exits, contacts = [], [], [], [], []
    paint = defaultdict(set)
    contact_ids = set()
    while pending:
        _observe(observer, "state_prefix", role_record=record, program=program, initial=initial, pending=list(pending), seen=seen, states=states, edges=edges, failures=failures, exits=exits, contacts=contacts, paint=dict(paint), contact_ids=contact_ids)
        state = pending.popleft()
        sid,r,c,dr,dc,colour = state
        if not(0 <= r < h and 0 <= c < w):
            exits.append(list(state))
            continue
        if state in seen:
            continue
        seen.add(state)
        if grid[r][c] != bg:
            failure = {'failure':'foreground_collision','state':list(state),'original_colour':grid[r][c]}
            failures.append(failure)
            states.append(dict(state=list(state), status='foreground_collision'))
            continue
        hits = [(g,n) for g,n in ports[(r,c)] if dr*n[0]+dc*n[1] > 0]
        states.append(dict(state=list(state), contacts=[g['id'] for g,n in hits]))
        if not hits:
            paint[(r,c)].add(colour)
            next_state = (sid,r+dr,c+dc,dr,dc,colour)
            # Reuse exact diagonal primitive to certify the geometric step.
            assert diagonal_segment((r,c),(r+dr,c+dc)) == [(r,c),(r+dr,c+dc)]
            edges.append(dict(source=list(state), target=list(next_state), reflector=None))
            pending.append(next_state)
        for g,n in hits:
            contact_ids.add(g['id'])
            paint[(r,c)].add(g['colour'] if turn_colour=='reflector' else colour)
            dot = dr*n[0]+dc*n[1]
            rd,cd = dr-2*dot*n[0],dc-2*dot*n[1]
            terminal = g['kind']=='point' and point_policy=='absorb'
            contacts.append(dict(source=sid,glyph=g['id'],cell=[r,c],incoming=[dr,dc],normal=list(n),
                                 outgoing=None if terminal else [rd,cd],old_colour=colour,new_colour=g['colour']))
            if terminal:
                edges.append(dict(source=list(state),target=None,reflector=g['id'],terminal='point_absorbed'))
            else:
                next_state = (sid,r+rd,c+cd,rd,cd,g['colour'])
                assert diagonal_segment((r,c),(r+rd,c+cd)) == [(r,c),(r+rd,c+cd)]
                edges.append(dict(source=list(state),target=list(next_state),reflector=g['id']))
                pending.append(next_state)
    _observe(observer, "state_prefix", role_record=record, program=program, initial=initial, pending=list(pending), seen=seen, states=states, edges=edges, failures=failures, exits=exits, contacts=contacts, paint=dict(paint), contact_ids=contact_ids)
    conflicts = [{'cell':list(p),'colours':sorted(cs)} for p,cs in sorted(paint.items()) if len(cs)>1]
    bound = len(scene['sources'])*h*w*4*len({g['colour'] for g in scene['glyphs']})
    assert len(seen) <= bound
    record.update(program=list(program),initial=[list(s) for s in initial],states=states,edges=edges,
                  state_count=len(seen),state_space_bound=bound,contacts=contacts,boundary_exits=exits,
                  unhit_reflectors=[g['id'] for g in scene['glyphs'] if g['kind']!='source' and g['id'] not in contact_ids],
                  failed_states=failures,paint_conflicts=conflicts,
                  proposals=[{'cell':list(p),'colours':sorted(cs)} for p,cs in sorted(paint.items())])
    if failures or conflicts:
        return None, dict(record,failure='causal_collision' if failures else 'simultaneous_colour_conflict')
    output = clone_grid(grid)
    for (r,c),cs in paint.items():
        output[r][c] = next(iter(cs))
    record['added_cells'] = len(paint)
    record['preserved_foreground'] = all(output[r][c]==grid[r][c] for r in range(h) for c in range(w) if grid[r][c]!=bg)
    return output, record

def fit_teachers(teachers):
    all_returns, retained = [], []
    for program in PROGRAMS:
        returns = []
        for i,pair in enumerate(teachers):
            output,record = render(pair['input'],program)
            returns.append(dict(teacher=i,output=output,record=record,exact=output==pair['output']))
        exact = all(x['exact'] for x in returns)
        all_returns.append(dict(program=list(program),teachers=returns,all_exact=exact))
        if exact:
            retained.append(program)
    return tuple(retained), all_returns

def consensus(grid, programs):
    if not programs:
        return None, {'failure':'no_retained_programs'}
    returns = [{'program':list(p),'output':y,'record':rec} for p in programs for y,rec in [render(grid,p)]]
    if any(x['output'] is None for x in returns):
        return None, {'failure':'retained_program_failed','returns':returns}
    if any(x['output'] != returns[0]['output'] for x in returns):
        return None, {'failure':'retained_program_disagreement','returns':returns}
    return returns[0]['output'], {'returns':returns}
