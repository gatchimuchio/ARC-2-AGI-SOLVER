# NEW current test binding: candidate root and frozen-source train-only subset defaults.
"""Portable source-only checker; stdout is one JSON line and no files are written."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import resource
import types
from unittest.mock import patch

resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))


def ordinary_pair():
    source = [[0]*10 for _ in range(10)]
    for r,c in ((4,4),(4,5),(5,4),(5,5)):
        source[r][c] = 4
    for r,c in ((4,6),(5,6),(1,2),(2,2)):
        source[r][c] = 2
    for r,c in ((1,3),(2,3),(2,4)):
        source[r][c] = 7
    output = [[0]*10 for _ in range(10)]
    for r in (4,5):
        output[r][4:8] = [4,4,2,7]
    output[5][8] = 7
    return {'input': source, 'output': output}


def model_keys(models):
    return {json.dumps(model, sort_keys=True, separators=(',', ':')) for model in models}


def raises(kind, call):
    try:
        call()
    except kind:
        return
    raise AssertionError(f'{kind.__name__} did not propagate')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--teachers', default=str(Path(__file__).resolve().parent / '復旧現行資料/093096/teachers-only.json'))
    parser.add_argument('--task', default='cbebaa4b')
    parser.add_argument('--candidate-dir', default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.root).resolve()))
    package = importlib.import_module('接続.ARC2')
    candidate_path = str(Path(args.candidate_dir).resolve() / '接続' / 'ARC2')
    if candidate_path not in package.__path__:
        package.__path__.append(candidate_path)
    core = importlib.import_module('接続.ARC2.疎標点重畳候補')
    adapter = importlib.import_module('接続.ARC2.疎標点重畳教材')
    legacy = importlib.import_module('接続.ARC2.重畳組立教材')
    original_type = getattr(legacy, '既存重畳組立教材', legacy.重畳組立教材)
    extended_type = adapter.extend_overlap_family(original_type, legacy.guarded_overlap_mosaic)
    tests = 0

    frozen = Path(core.__file__).read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == '1713eac98ca8225efb3412c38e1783558bf84e314fae66c85f2daaec6cb7516e'
    # Reconstruct the unchanged reference entirely in memory, with hash proof.
    # The reference is test-only and never used by the runtime adapter.
    reference = frozen.decode().replace(
        "            if not singles:\n                return\n"
        "            # Every completion must pair this pin with one unplaced piece.\n"
        "            # A saturated prefix cannot acquire another connected piece.\n"
        "            row, col = min(singles)\n", '').replace(
        "                          for source_row, source_col in piece['pins']}",
        "                          for row, col in singles for source_row, source_col in piece['pins']}")
    assert hashlib.sha256(reference.encode()).hexdigest() == '7cd8f01e64f42784f64205f85153253133eea21345e9dd84234dc457e1a8a6a1'
    old = types.ModuleType('reference_sparse_marker')
    exec(compile(reference, '<reference_sparse_marker>', 'exec'), old.__dict__)
    assert old.DEFAULT_WORK_LIMIT == core.DEFAULT_WORK_LIMIT == 250000
    tests += 1

    pairs = json.loads(Path(args.teachers).read_text())[args.task]['train']
    policies, _ = core.fit_teachers(pairs)
    old_policies, _ = old.fit_teachers(pairs)
    assert policies == old_policies == [False, True]
    extended = extended_type(pairs)
    assert extended.疎標点規則 == policies
    for pair in pairs:
        output, record = extended.候補(pair['input'], {})
        assert output == pair['output']
        assert len(record['returns']) == len(policies)
    tests += 1

    ordinary = ordinary_pair()
    ambiguous = [[0]*8 for _ in range(8)]
    for r,c,v in ((2,1,1),(2,2,2),(5,4,2),(5,5,3)):
        ambiguous[r][c] = v
    impossible = [row[:] for row in ordinary['input']]
    impossible[1][2] = 0
    scenes = [pair['input'] for pair in pairs] + [ordinary['input'], ambiguous, impossible]
    for grid in scenes:
        for diagonal in (False, True):
            original_models, _ = old.enumerate_assemblies(grid, diagonal)
            new_models, _ = core.enumerate_assemblies(grid, diagonal)
            assert model_keys(original_models) == model_keys(new_models)
            assert {core.grid_key(m['output']) for m in original_models} == {
                core.grid_key(m['output']) for m in new_models}
        tests += 1

    # The same four ordinary controls used before input-only execution.
    ordinary_policies, _ = core.fit_teachers([ordinary])
    assert ordinary_policies == [False, True]
    palette = {0:9, 2:5, 4:1, 7:3}
    color = lambda grid: [[palette[v] for v in row] for row in grid]
    rotate = lambda grid: [list(row) for row in zip(*grid[::-1])]
    for transform in (lambda g: g, color, rotate):
        assert core.render(transform(ordinary['input']), policies)[0] == transform(ordinary['output'])
    tests += 1
    output, record = core.render(ambiguous, policies)
    assert output is None and record['output_count'] == 2
    assert [r['model_count'] for r in record['returns']] == [2, 2]
    tests += 1
    calls = []
    real_enumerate = core.enumerate_assemblies
    def returning(grid, diagonal, **kwargs):
        calls.append(diagonal)
        if not diagonal:
            return [], {'model_count': 0}
        return real_enumerate(grid, diagonal, **kwargs)
    with patch.object(core, 'enumerate_assemblies', returning):
        assert core.render(ordinary['input'], policies)[0] is None
    assert calls == [False, True]
    tests += 1
    raises(core.AssemblyIncomplete, lambda: core.render(ordinary['input'], policies, work_limit=1))
    for kind in (MemoryError, RuntimeError):
        with patch.object(core, 'enumerate_assemblies', side_effect=kind('control')):
            raises(kind, lambda: core.render(ordinary['input'], policies))
    tests += 1

    # Legacy positive output and record retain exactly the original path.
    legacy_grid = [[0]*7 for _ in range(3)]
    legacy_grid[1] = [1,2,0,0,2,3,0]
    legacy_output, _ = legacy.guarded_overlap_mosaic(legacy_grid)
    assert legacy_output == [[1,2,3]]
    legacy_pair = {'input': legacy_grid, 'output': legacy_output}
    original = original_type([legacy_pair])
    with patch.object(core, 'fit_teachers', side_effect=AssertionError('positive fallback')):
        wrapped = extended_type([legacy_pair])
    assert wrapped.記録() == original.記録()
    assert wrapped.候補(legacy_grid,{}) == original.候補(legacy_grid,{})
    tests += 1

    # No fallback is permitted from incomplete/error/unknown legacy returns.
    class NoFit:
        def __init__(self, teachers): self.全教師再現 = False
        def 記録(self): return {'全教師再現': False}
        def 候補(self, grid, policy): return None, {'failure': 'ordinary_no_fit'}
    for bad in ({'failure': 'placement conflict or no-op output', 'complete': False},
                {'failure': 'placement conflict or no-op output', 'detail': {'failure': 'budget_exhausted'}},
                {'failure': 'unknown_failure'}):
        wrapper = adapter.extend_overlap_family(NoFit, lambda grid, bad=bad: (None,bad))
        with patch.object(core, 'fit_teachers', side_effect=AssertionError('incomplete fallback')):
            raises(adapter.ExistingOverlapIncomplete, lambda: wrapper([ordinary]))
    for kind in (MemoryError, RuntimeError):
        def raising(grid, kind=kind): raise kind('legacy control')
        wrapper = adapter.extend_overlap_family(NoFit, raising)
        with patch.object(core, 'fit_teachers', side_effect=AssertionError('exception fallback')):
            raises(kind, lambda: wrapper([ordinary]))
    tests += 1
    print(json.dumps({'tests_run': tests, 'successful': True}, separators=(',', ':')))


if __name__ == '__main__':
    main()
