"""Small teacher-first and fixed-geometry check packet; never reads queries."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

# NEW current test binding; the pre055 reference remains test-only.
ROOT = Path(__file__).resolve().parent / '復旧現行資料/055'
BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / '接続/ARC2/標識組立教材.py'
REFERENCE = ROOT / '標識組立教材.before055.py'
TEACHERS = ROOT / 'teachers-only.json'
TEACHER_SHA = '19627fc3649ae3c23141ceaf5ab9c6d189dd8ee725b0e3c8db35423c106f5711'
sys.path.insert(0, str(BASE))
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
baseline = load('接続.ARC2._before055_current_check', REFERENCE)
complete_module = load('接続.ARC2.標識組立完全所有', BASE / '接続/ARC2/標識組立完全所有.py')
module = load('接続.ARC2._candidate055_current_check', SOURCE)
ROLES = {'marker': 7, 'target': 4, 'background': 1}


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def teachers():
    require(hashlib.sha256(TEACHERS.read_bytes()).hexdigest() == TEACHER_SHA, 'teacher source hash')
    old_tree = ast.parse(REFERENCE.read_text())
    new_tree = ast.parse(SOURCE.read_text())
    old_fit = next(node for node in old_tree.body if getattr(node, 'name', None) == 'fit_guarded')
    new_fit = next(node for node in new_tree.body if getattr(node, 'name', None) == 'fit_guarded')
    require(ast.dump(old_fit) == ast.dump(new_fit), 'fitter AST unchanged')
    for name in ('valid_grid', 'guarded_render'):
        before = next(node for node in old_tree.body if getattr(node, 'name', None) == name)
        after = next(node for node in new_tree.body if getattr(node, 'name', None) == name)
        require(ast.dump(before) == ast.dump(after), name + ' AST unchanged')
    pairs = json.loads(TEACHERS.read_text())['train']
    view = module.標識組立教材(pairs)
    require(view.役割 == baseline.fit_guarded(pairs) == ROLES, 'same teacher eligibility and roles')
    cells = 0
    for index, pair in enumerate(pairs):
        previous = baseline.guarded_render(pair['input'], ROLES)
        current = view.候補(pair['input'], {})
        require(previous == current == module.guarded_render(pair['input'], ROLES), f'teacher {index} record equality')
        require(current[0] == pair['output'], f'teacher {index} exact output')
        cells += sum(len(row) for row in pair['output'])
    require(len(pairs) == 4 and cells == 176, 'four teachers and 176 output cells')
    result = {'stage': 'teachers', 'teachers': 4, 'exact_output_cells': cells,
              'old_records_equal': True, 'fitter_ast_equal': True, 'successful': True, 'tests_run': 4, 'evidence_kind': 'NEW current test binding',
              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
    (ROOT / 'teacher-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


def grid(markers, target, height=8, width=8):
    result = [[1] * width for _ in range(height)]
    for r, c in markers:
        result[r][c] = 7
    for r, c in target:
        require(result[r][c] == 1, 'literal cell overlap')
        result[r][c] = 4
    return result


def targeted():
    receipt = json.loads((ROOT / 'teacher-result.json').read_text())
    require(receipt['source_sha256'] == hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'teachers first for frozen source')
    view = module.標識組立教材(json.loads(TEACHERS.read_text())['train'])
    tie = grid([(1, 2), (5, 5)], [(2, 2), (2, 1), (4, 5), (4, 6)])
    expected = [[1, 4, 4], [4, 4, 1]]
    require(baseline.guarded_render(tie, ROLES)[1]['failure'] == 'dominant_translation_axis_tie', 'original tie rejection')
    require(module.guarded_render(tie, ROLES) == baseline.guarded_render(tie, ROLES), 'default tie rejection retained')
    require(view.候補(tie, {})[0] == expected, 'complete two-body tie')
    # A detached target island makes complete two-body ownership impossible.
    incomplete = grid([(1, 2), (5, 5)], [(2, 2), (2, 1), (4, 5), (4, 6), (7, 7)])
    # The extra upper target creates a second full port at the source marker.
    ambiguous = grid([(1, 2), (5, 5)], [(2, 2), (2, 1), (1, 1), (0, 2), (4, 5), (4, 6)])
    require(complete_module.guarded_render(ambiguous, ROLES)[1]['failure'] == 'invalid_complete_alternative', 'all ambiguous port alternatives considered')
    for label, literal in [('incomplete_body_ownership', incomplete), ('ambiguous_full_ports', ambiguous)]:
        require(view.候補(literal, {})[0] is None, label)
    untied = grid([(1, 2), (5, 6)], [(2, 2), (2, 1), (4, 6), (4, 7)], width=9)
    require(view.候補(untied, {}) == baseline.guarded_render(untied, ROLES), 'untied complete record equality')
    require(baseline.guarded_render(untied, ROLES)[0] == expected, 'untied literal output')
    print(json.dumps({'stage': 'targeted', 'fixed_contrasts': 4, 'passed': True, 'successful': True, 'tests_run': 4, 'evidence_kind': 'NEW current test binding'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', nargs='?', default='all', choices=['teachers', 'targeted', 'all'])
    args = parser.parse_args()
    if args.stage == 'all':
        teachers()
        targeted()
        print(json.dumps({'tests_run': 8, 'successful': True, 'evidence_kind': 'NEW current test binding', 'stage': 'all'}))
    else:
        {'teachers': teachers, 'targeted': targeted}[args.stage]()
