# NEW current test binding: source root is the assembled candidate.
"""Read-only public check of the frozen candidate and existing-family adapter.

Usage: python check_adapter.py --root ACCEPTED_ROOT --teachers TEACHERS_JSON
Optional --source-root overrides the directory containing proposed 接続/ARC2 files.
The default source root is this checker's directory. No artifacts are written.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fixture():
    # Same ordinary fixture already used by the frozen proposal.
    grid = [[0]*18 for _ in range(14)]
    for r in range(1,6):
        for c in range(1,6):
            grid[r][c] = 8
    grid[3][2:5] = [1,1,2]
    for r in range(7,13):
        for c in range(2,16):
            if r in (7,12) or c in (2,15):
                grid[r][c] = 8
    for r in (9,10):
        for c in (4,5):
            grid[r][c] = 4
    expected = [row[:] for row in grid]
    for r in (9,10):
        for c in (4,5):
            expected[r][c] = 0
        for c in (13,14):
            expected[r][c] = 4
    return grid,expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--teachers',type=Path,default=Path(__file__).resolve().parent / '復旧現行資料/093096/teachers-only.json')
    parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    sys.path.insert(0,str(args.root.resolve()))
    directory = args.source_root/'接続'/'ARC2'
    core = load('接続.ARC2.凡例方向移動候補',directory/'凡例方向移動候補.py')
    adapter = load('接続.ARC2._proposal093_adapter',directory/'標識移動教材.py')
    from 接続.ARC2.既存格子操作 import transform_grid_by_name
    raw = args.teachers.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '99de67a4f060024056619b4b8f16ec32201e0df471cca2eb01d6e6421c7da7ea'
    teachers = json.loads(raw)['88e364bc']['train']
    tests = 0

    original = adapter._既存標識移動教材(teachers)
    assert original.方針 is None and original.適合方針数 == 0
    fitted = adapter.標識移動教材(teachers)
    assert fitted.凡例方向モデル is not None
    assert fitted.凡例方向fit記録['complete'] is True
    assert fitted.凡例方向fit記録['model_count'] == 480
    assert fitted.凡例方向fit記録['call_count'] == 1440
    assert len(fitted.凡例方向モデル.models) == 4
    tests += 1
    for pair in teachers:
        output,record = fitted.候補(pair['input'],None)
        assert output == pair['output'] and len(record['returns']) == 4
        tests += 1

    grid,expected = fixture()
    for transform in ('identity','rot90'):
        output,record = fitted.候補(transform_grid_by_name(grid,transform),None)
        assert output == transform_grid_by_name(expected,transform)
        assert len(record['returns']) == 4
        tests += 1
    broken = [row[:] for row in grid]
    broken[12][7] = 0
    output,record = fitted.候補(broken,None)
    assert output is None and len(record['returns']) == 4
    assert all(x['record']['failure'] == 'marker_without_enclosing_wall' for x in record['returns'])
    tests += 1
    obstructed = [row[:] for row in grid]
    for r in (9,10):
        for c in (4,5):
            obstructed[r][c] = 0
    obstructed[9][4] = obstructed[9][8] = 4
    output,record = fitted.候補(obstructed,None)
    assert output is None and len(record['returns']) == 4
    assert sum(x['output'] is None for x in record['returns']) == 2
    tests += 1

    # Basic delegation preservation, without unrelated task data or new fixtures.
    base = adapter._既存標識移動教材
    for policy,count in (({'accepted':True},1),(None,2),(None,1)):
        def accepted_init(self,unused):
            self.方針,self.適合方針数,self.接触消去教師数 = policy,count,0
        accepted_output = ([[8]],{'existing_record':True})
        accepted_record = {'policy':policy,'count':count}
        with patch.object(base,'__init__',accepted_init), \
             patch.object(base,'候補',return_value=accepted_output), \
             patch.object(base,'記録',return_value=accepted_record), \
             patch.object(core,'fit_teachers',side_effect=AssertionError('unexpected extension call')):
            instance = adapter.標識移動教材(teachers)
            assert instance.候補([[0]],None) == accepted_output
            assert instance.記録() == accepted_record
        tests += 1

    def no_fit_init(self,unused):
        self.方針,self.適合方針数,self.接触消去教師数 = None,0,0
    for ineligible in ([{'input':[[0]],'output':[[0,0]]}],
                       [{'input':[[0]],'output':[[4]]}]):
        with patch.object(base,'__init__',no_fit_init), \
             patch.object(core,'fit_teachers',side_effect=AssertionError('ineligible models executed')):
            instance = adapter.標識移動教材(ineligible)
            assert instance.凡例方向fit記録 is None
        tests += 1
    for target in (base,core):
        method = '__init__' if target is base else 'fit_teachers'
        with patch.object(target,method,side_effect=MemoryError('propagation check')):
            try:
                adapter.標識移動教材(teachers)
            except MemoryError:
                pass
            else:
                raise AssertionError('resource exception swallowed')
        tests += 1
    with patch.object(core,'fit_teachers',return_value=(None,{'complete':False})):
        try:
            adapter.標識移動教材(teachers)
        except RuntimeError:
            pass
        else:
            raise AssertionError('incomplete fitting converted to ordinary failure')
    tests += 1
    print(json.dumps({'tests_run':tests,'successful':True},separators=(',',':')))


if __name__ == '__main__':
    main()
