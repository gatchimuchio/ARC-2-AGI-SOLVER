"""Portable public replay: the same 13 composition and 14 binding controls.

Run with --root PATCHED_ROOT --teachers TEACHERS_ONLY_JSON. No query data is read.
The two embedded baseline sources are the unmodified accepted113 binding/family.
"""
import argparse
import copy
import hashlib
import json
import sys
import types
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--teachers', type=Path, default=Path(__file__).resolve().parent / '枠命令配置資料/teachers-only.json')
args = parser.parse_args()
root = args.root.resolve()
data = args.teachers.read_bytes()
assert hashlib.sha256(data).hexdigest() == 'a58925d31a29fda5b45f2102f3e93637e18d80ab210f840da44233473f891bb7'
sys.path.insert(0, str(root))
from 接続.ARC2 import 並列枠命令配置 as new
from 接続.ARC2 import 枠命令配置接続 as binding
from 接続.ARC2 import 配置展開教材 as family
old = new.old
train = json.loads(data)['a32d8b75']['train']
assert new.fit is old.fit and new.act is old.act and new.MODELS is old.MODELS
models, fitting = new.fit(train)
assert models
checks = []

def baseline(name, source):
    module = types.ModuleType(name)
    module.__package__ = '接続.ARC2'
    exec(compile(source, name, 'exec'), module.__dict__)
    return module

BASELINE_BINDING = '"""Completed legacy no-fit gate and exact strict-fit necessity prepass."""\nfrom . import 全枠命令配置 as view\n\n\ndef complete_raw_record(record):\n    if not isinstance(record, dict):\n        return False\n    failure_fields = {\n        \'macro_tile_foreground_component_count_not_two\': {\'foreground_component_count\'},\n        \'macro_tile_pair_not_unique\': {\'valid_pair_count\', \'foreground_component_count\'},\n        \'macro_tile_output_exceeds_arc_limit\': {\'macro_tile_shape\', \'macro_layout_shape\', \'macro_tiled_shape\'},\n        \'macro_tile_layout_has_no_active_cells\': set(),\n        \'identity_macro_tile_render\': set(),\n    }\n    if record.get(\'failure\') in failure_fields:\n        return set(record) == failure_fields[record[\'failure\']] | {\'failure\'}\n    return (record.get(\'renderer_case\') == \'layout_mask_macro_tile_expander\'\n            and set(record) == {\'renderer_case\', \'background\', \'macro_background_color\',\n                                \'macro_motif_bbox\', \'macro_layout_bbox\', \'macro_tile_shape\',\n                                \'macro_layout_shape\', \'macro_tiled_shape\', \'macro_layout_color\',\n                                \'macro_active_cell_count\', \'macro_motif_colors\'})\n\n\ndef completed_no_fit(teachers, fitted, record):\n    if fitted is not False or not isinstance(record, dict):\n        return False\n    if set(record) != {\'failure\', \'raw_pair_fits\', \'raw_records\'}:\n        return False\n    fits, records = record[\'raw_pair_fits\'], record[\'raw_records\']\n    return (record[\'failure\'] == \'original_teacher_reproduction_failed\'\n            and isinstance(fits, list) and isinstance(records, list)\n            and len(fits) == len(records) == len(teachers) and len(teachers) >= 2\n            and all(type(value) is bool for value in fits) and not all(fits)\n            and all(complete_raw_record(value) for value in records))\n\n\ndef fit(teachers):\n    strict = view.strict\n    if (not isinstance(teachers, list) or len(teachers) < 2\n            or any(not isinstance(p, dict) or not strict.valid_grid(p.get(\'input\'))\n                   or not strict.valid_grid(p.get(\'output\')) for p in teachers)\n            or len({tuple(map(tuple, p[\'input\'])) for p in teachers}) != len(teachers)):\n        return strict.fit(teachers)\n    witnesses = []\n    for index, pair in enumerate(teachers):\n        roles, record = strict.parse(pair[\'input\'])\n        if (set(record) != {\'roles\', \'probes\'} or record[\'roles\'] != len(roles)\n                or not isinstance(record[\'probes\'], list)):\n            raise RuntimeError(\'strict_parse_completion_unrecognized\')\n        witnesses.append({\'teacher_index\': index, \'role_count\': len(roles),\n                          \'complete\': True, \'record\': record})\n    rejected = [w[\'teacher_index\'] for w in witnesses if w[\'role_count\'] == 0]\n    count = len(strict.MODELS)\n    common = {\'complete\': True, \'teacher_count\': len(teachers), \'model_count\': count,\n              \'proof_parse_calls\': len(witnesses), \'teacher_parse_witnesses\': witnesses}\n    if rejected:\n        return (), {**common, \'status\': \'proven_empty\', \'retained_count\': 0,\n                    \'retained_models\': (), \'teacher_fit_exact\': False,\n                    \'rejected_teacher_indices\': rejected, \'evaluated_teacher_calls\': 0,\n                    \'symbolic_unexecuted_teacher_calls\': count * len(teachers)}\n    models, record = view.fit(teachers)\n    if record.get(\'complete\') is not True:\n        raise RuntimeError(\'strict_fit_completion_unrecognized\')\n    return models, {**common, \'status\': \'fitted\' if models else \'completed_no_fit\',\n                    \'retained_count\': len(models), \'retained_models\': models,\n                    \'teacher_fit_exact\': bool(models), \'rejected_teacher_indices\': [],\n                    \'evaluated_teacher_calls\': sum(len(r[\'teacher_returns\'])\n                                                    for r in record[\'all_model_returns\']),\n                    \'symbolic_unexecuted_teacher_calls\': 0}\n\n\ndef compact(record):\n    return {key: value for key, value in record.items() if key != \'teacher_parse_witnesses\'}\n'
BASELINE_FAMILY = '"""全component所有と全block対応を証明し元格子を同じHDSへ渡す。"""\nfrom __future__ import annotations\nfrom collections import Counter\nfrom .既存配置展開 import foreground_mixed_components,crop_bbox,render_layout_mask_macro_tile_expander\nfrom . import 枠命令配置接続 as frame_binding\n\ndef valid_grid(grid):\n    return(isinstance(grid,list)and 1<=len(grid)<=30 and isinstance(grid[0],list)and 1<=len(grid[0])<=30\n           and all(isinstance(row,list)and len(row)==len(grid[0])and all(type(v)is int and 0<=v<=9 for v in row)for row in grid))\n\ndef guarded_render(grid):\n    if not valid_grid(grid):return None,{\'failure\':\'invalid_arc_grid\'}\n    raw,raw_record=render_layout_mask_macro_tile_expander(grid)\n    if raw is None:return None,{\'failure\':\'original_renderer_unresolved\',\'raw_record\':raw_record}\n    counts=Counter(v for row in grid for v in row);leaders=[v for v,n in counts.items()if n==max(counts.values())]\n    if len(leaders)!=1:return None,{\'failure\':\'background_tie\'}\n    bg=leaders[0];components=foreground_mixed_components(grid,bg)\n    if len(components)!=2:return None,{\'failure\':\'foreground_component_count_not_two\'}\n    groups=[set(map(tuple,c[\'cells\']))for c in components]\n    foreground={(r,c)for r,row in enumerate(grid)for c,v in enumerate(row)if v!=bg}\n    if groups[0]&groups[1]or groups[0]|groups[1]!=foreground:return None,{\'failure\':\'foreground_coverage_failed\'}\n    pairs=[]\n    for mi,m in enumerate(components):\n        for li,l in enumerate(components):\n            if mi!=li and len(set(m[\'colors\']))>=2 and len(set(l[\'colors\']))==1 and l[\'colors\'][0]not in set(m[\'colors\']):pairs.append((mi,li))\n    if len(pairs)!=1:return None,{\'failure\':\'raw_roles_not_unique\'}\n    mi,li=pairs[0];motif,layout=components[mi],components[li]\n    for i,component in enumerate(components):\n        r0,c0,r1,c1=component[\'bbox\']\n        contained={(r,c)for r in range(r0,r1+1)for c in range(c0,c1+1)if grid[r][c]!=bg}\n        if contained!=groups[i]:return None,{\'failure\':\'foreign_foreground_in_bbox\',\'role\':\'motif\'if i==mi else\'layout\'}\n    tile=crop_bbox(grid,motif[\'bbox\']);mask=crop_bbox(grid,layout[\'bbox\']);th,tw=len(tile),len(tile[0]);lh,lw=len(mask),len(mask[0]);lc=layout[\'colors\'][0]\n    if any(v not in {bg,lc}for row in mask for v in row):return None,{\'failure\':\'layout_nonbinary_cells\'}\n    oh,ow=th*lh,tw*lw\n    if not(1<=oh<=30 and 1<=ow<=30):return None,{\'failure\':\'output_outside_arc_bounds\'}\n    expected=[[None]*ow for _ in range(oh)];coverage=set();active=[]\n    for lr in range(lh):\n        for ll in range(lw):\n            enabled=mask[lr][ll]==lc\n            if enabled:active.append([lr,ll])\n            for tr in range(th):\n                for tc in range(tw):\n                    p=(lr*th+tr,ll*tw+tc)\n                    if p in coverage:return None,{\'failure\':\'block_overlap\'}\n                    coverage.add(p);expected[p[0]][p[1]]=tile[tr][tc]if enabled else bg\n    if len(coverage)!=oh*ow or len(active)!=len(groups[li]):return None,{\'failure\':\'layout_or_output_coverage_failed\'}\n    tile_counts=Counter(v for row in tile for v in row if v!=bg)\n    expected_counts={c:n*len(active)for c,n in tile_counts.items()}\n    if dict(Counter(v for row in expected for v in row if v!=bg))!=expected_counts:return None,{\'failure\':\'motif_colour_multiplicity_failed\'}\n    expected_record={\'renderer_case\':\'layout_mask_macro_tile_expander\',\'background\':bg,\'macro_background_color\':bg,\n        \'macro_motif_bbox\':list(motif[\'bbox\']),\'macro_layout_bbox\':list(layout[\'bbox\']),\'macro_tile_shape\':[th,tw],\n        \'macro_layout_shape\':[lh,lw],\'macro_tiled_shape\':[oh,ow],\'macro_layout_color\':lc,\n        \'macro_active_cell_count\':len(active),\'macro_motif_colors\':motif[\'colors\']}\n    if raw!=expected or raw_record!=expected_record:return None,{\'failure\':\'original_grid_or_record_disagreement\'}\n    return raw,{\'raw_record\':raw_record,\'foreground_component_count\':2,\'input_foreground_pixels\':len(foreground),\n        \'active_layout_cells\':active,\'inactive_layout_cell_count\':lh*lw-len(active),\'tile_cell_count\':th*tw,\n        \'output_cell_count\':len(coverage),\'motif_foreground_counts\':sorted(tile_counts.items()),\n        \'output_foreground_counts\':sorted(expected_counts.items())}\n\ndef fit_teachers(teachers):\n    if len(teachers)<2 or any(not valid_grid(p[\'input\'])or not valid_grid(p[\'output\'])for p in teachers):\n        return False,{\'failure\':\'insufficient_or_invalid_teachers\'}\n    if len({tuple(map(tuple,p[\'input\']))for p in teachers})!=len(teachers):return False,{\'failure\':\'duplicate_teacher_inputs\'}\n    raw=[render_layout_mask_macro_tile_expander(p[\'input\'])for p in teachers]\n    record={\'raw_pair_fits\':[out is not None and out==p[\'output\']for(out,_),p in zip(raw,teachers)],\'raw_records\':[r for _,r in raw]}\n    if not all(record[\'raw_pair_fits\']):return False,dict(record,failure=\'original_teacher_reproduction_failed\')\n    guarded=[guarded_render(p[\'input\'])for p in teachers];record[\'teacher_records\']=[r for _,r in guarded]\n    if any(out is None or out!=p[\'output\']for(out,_),p in zip(guarded,teachers)):\n        return False,dict(record,failure=\'teacher_certificate_failed\')\n    return True,record\n\nclass 配置展開教材:\n    def __init__(self, 教師群):\n        self.適合, record = fit_teachers(教師群)\n        if frame_binding.completed_no_fit(教師群, self.適合, record):\n            self.枠命令モデル群, self.枠命令適合記録 = frame_binding.fit(教師群)\n\n    def 候補(self, 格子, _policy):\n        if hasattr(self, \'枠命令モデル群\'):\n            return frame_binding.view.consensus(格子, self.枠命令モデル群)\n        if not self.適合:\n            return None, {"failure": "全教師を再現する配置mask展開なし"}\n        return guarded_render(格子)\n\n    def 記録(self):\n        if hasattr(self, \'枠命令モデル群\'):\n            return {"全教師共通配置積": self.適合,\n                    "全教師共通枠命令配置": frame_binding.compact(self.枠命令適合記録)}\n        return {"全教師共通配置積": self.適合}\n'
SOURCE_MAP = [{'path': '接続/ARC2/並列枠命令配置.py', 'before_sha256': None, 'after_sha256': 'fe30021e81a14dfc65785f737e787c5ba5dc415d8f4d5fe77ebb923482300d32'}, {'path': '接続/ARC2/枠命令配置接続.py', 'before_sha256': '7e76b3fbe96ee8617474255bda4b1ff4ef2e91bd426698203935027fa76b75e3', 'after_sha256': '495c113455c26c0ff46b96e7d4d2c143dcddaa8e4a45a726f27901c5c7c767c0'}, {'path': '接続/ARC2/配置展開教材.py', 'before_sha256': 'dd1b253da8f1bb6190510089a648e0bf294f3a3156432a5fe504ca3ad88957e4', 'after_sha256': 'a7f7a65ec351f0dd1d9a6bc819b5e384351ca339d952f70259b22b6191709c39'}]
baseline_binding = baseline('accepted113_binding', BASELINE_BINDING)
original_family = baseline('accepted113_family', BASELINE_FAMILY)
original_family.frame_binding = baseline_binding
for entry in SOURCE_MAP:
    assert hashlib.sha256((root / entry['path']).read_bytes()).hexdigest() == entry['after_sha256']

def check(name, grid, expected, programs=models):
    out, record = new.consensus(grid, programs)
    assert out == expected, (name, record)
    json.dumps(record)
    checks.append({'name': name, 'passed': True, 'failure': record.get('failure'),
                   'model_returns': len(record['model_returns']),
                   'partition_counts': [r['record']['partition_count'] for r in record['model_returns']]})
    return record


def put(panel, block, r0, c0):
    for r, row in enumerate(block):
        panel[r0+r][c0:c0+len(row)] = row


def panel(bottom_right=False, invert=False):
    result = [[0] * 14 for _ in range(6)]
    tile = [[1, 2], [1, 1]]
    if invert:
        tile = [[3-v for v in row] for row in tile]
    put(result, tile, 1, 0)
    result[4][0] = 3
    anchor = [[0, 0], [0, 0]]
    anchor[1 if bottom_right else 0][1 if bottom_right else 0] = 4
    direction = [[0, 7, 0], [0, 7, 0], [0, 0, 0]]
    for block, col in ((anchor, 4), (direction, 9)):
        framed = [[6] * (len(block[0])+2)]
        framed += [[6] + row + [6] for row in block]
        framed += [[6] * (len(block[0])+2)]
        put(result, framed, 0, col)
    return result


for i, pair in enumerate(train):
    assert old.consensus(pair['input'], models)[0] == pair['output']
    check('original_teacher_' + str(i), pair['input'], pair['output'])

canvas = [[8 + r % 2] * 14 for r in range(6)]
top, bottom = panel(), panel(True)
sep = [[6] * 14]
stamp = [[2, 1], [2, 2]]
for command, y, x in ((top, 0, 0), (bottom, 4, 12)):
    expected = [row[:] for row in canvas]
    put(expected, stamp, y, x)
    grid = command + sep + canvas
    assert old.consensus(grid, models)[0] == expected
    check('single_command_' + str(y), grid, expected)

grid = top + sep + canvas + sep + bottom
expected = [row[:] for row in canvas]
put(expected, stamp, 0, 0)
put(expected, stamp, 4, 12)
record = check('two_disjoint_commands', grid, expected)
view = record['model_returns'][0]['record']['partition_returns'][0]['record']
assert len(view['command_returns']) == 2 and view['written_cells'] == 8
old_out, old_record = old.consensus(grid, models)
assert old_out is None and old_record['model_returns'][0]['record']['failure'] == 'relational_role_disagreement'
checks.append({'name': 'frozen095_disagreement_unchanged', 'passed': True})
check('opposite_peeling_orders_agree', bottom + sep + canvas + sep + top, expected)

same_expected = [row[:] for row in canvas]
put(same_expected, stamp, 0, 0)
record = check('same_color_overlap', top + sep + canvas + sep + top, same_expected)
assert record['model_returns'][0]['record']['partition_returns'][0]['record']['written_cells'] == 4
check('adjacent_commands_consumed', top + sep + top + sep + canvas, same_expected)

# Some writes equal the original canvas. They still conflict with a different
# color from another command; comparing only changed pixels would be unsound.
conflict_grid = top + sep + [[2] * 14 for _ in range(6)] + sep + panel(invert=True)
record = check('idempotent_write_conflict', conflict_grid, None)
assert record['model_returns'][0]['record']['partition_returns'][0]['record']['failure'] == 'command_write_conflict'

record = check('command_failure_is_mandatory', top + sep + [[8] * 14] + sep + bottom, None)
cmds = record['model_returns'][0]['record']['partition_returns'][0]['record']['command_returns']
assert len(cmds) == 2 and all(c['failure'] == 'command_role_failed' for c in cmds)
wrong = (False, 'identity', 'identity', False, 'identity')
record = check('retained_program_disagreement', grid, None, [models[0], wrong])
assert record['failure'] == 'retained_model_disagreement' and len(record['model_returns']) == 2

# Constructor, complete object state, fit record and successful prediction
# outputs/records are exactly those of the accepted class.
old_instance = original_family.配置展開教材(train)
new_instance = family.配置展開教材(train)
assert vars(new_instance) == vars(old_instance)
assert new_instance.記録() == old_instance.記録()
for i, pair in enumerate(train):
    assert new_instance.候補(pair['input'], None) == old_instance.候補(pair['input'], None)
checks.append({'name': 'accepted_constructor_state_and_teacher_predictions_exact', 'passed': True})

original_result = binding.view.consensus(grid, models)
assert binding.completed_relational_disagreement(*original_result, models)
out, record = binding.predict(grid, models)
assert out == expected and record['accepted113_record'] == original_result[1]
assert new_instance.候補(grid, None) == (out, record)
checks.append({'name': 'complete_old_disagreement_admits_same_family_composition', 'passed': True})

saved_old, saved_parallel = binding.view.consensus, binding.parallel.consensus
called = []
try:
    def forbidden(*args):
        called.append(args)
        raise AssertionError('composition must not run')
    binding.parallel.consensus = forbidden
    cases = []
    success = saved_old(train[0]['input'], models)
    cases.append(('successful_delegation_is_identical', success))
    for name in ('incomplete', 'missing_model', 'returned_model_grid', 'role_failed',
                 'truncated_roles', 'false_disagreement', 'model_order_mismatch'):
        output, old_record = copy.deepcopy(original_result)
        entry = old_record['model_returns'][0]
        role_record = entry['record']
        if name == 'incomplete':
            old_record['complete'] = False
        elif name == 'missing_model':
            old_record['model_returns'] = []
        elif name == 'returned_model_grid':
            entry['return'] = [[0]]
        elif name == 'role_failed':
            role_record['role_returns'][0]['return'] = None
            role_record['role_returns'][0]['record'] = {'failure': 'macro_out_of_bounds'}
        elif name == 'truncated_roles':
            role_record['role_returns'].pop()
        elif name == 'false_disagreement':
            for role in role_record['role_returns']:
                role['return'] = copy.deepcopy(role_record['role_returns'][0]['return'])
        elif name == 'model_order_mismatch':
            entry['model'] = (False, 'identity', 'identity', False, 'identity')
        cases.append((name + '_cannot_open_gate', (output, old_record)))
    for name, result in cases:
        binding.view.consensus = lambda *args, result=result: result
        actual = binding.predict(grid, models)
        assert actual is result
        checks.append({'name': name, 'passed': True})
    for kind in (RuntimeError, MemoryError, TimeoutError):
        def faulty(*args, kind=kind):
            raise kind('accepted prediction exception')
        binding.view.consensus = faulty
        try:
            binding.predict(grid, models)
        except kind:
            checks.append({'name': kind.__name__ + '_not_rescued', 'passed': True})
        else:
            raise AssertionError(kind.__name__)
    assert not called

    # A failed new composition stays HOLD and receives every original program.
    binding.view.consensus = saved_old
    observed = []
    def failed(grid, programs):
        observed.append(programs)
        return None, {'complete': True, 'failure': 'retained_model_failed'}
    binding.parallel.consensus = failed
    output, record = binding.predict(grid, models)
    assert output is None and observed == [models]
    assert record['failure'] == 'retained_model_failed'
    checks.append({'name': 'new_failure_remains_hold_all_original_models_passed', 'passed': True})
finally:
    binding.view.consensus, binding.parallel.consensus = saved_old, saved_parallel


assert len(checks) == 27 and all(check['passed'] for check in checks)
print(json.dumps({'status': 'pass', 'successful': True, 'tests_run': len(checks),
                  'composition_tests_run': 13, 'binding_tests_run': 14,
                  'strict_model_count': fitting['model_count'],
                  'retained_count': len(models), 'checks': checks,
                  'source_files': SOURCE_MAP}, ensure_ascii=False))
