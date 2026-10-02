"""対応色の物理成分数、固定点列符号、消去証拠と三盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 枠計数教材 as module
from 接続.ARC2.枠計数教材 import guarded_render, 枠計数教材
from 接続.ARC2.既存枠計数 import render_frame_component_count_slots
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 枠を描く(grid, top, left, height, width, color):
    for r in range(top, top + height):
        for c in range(left, left + width):
            if r in (top, top + height - 1) or c in (left, left + width - 1):
                grid[r][c] = color


def 教材(shape=(5, 9), counts=(2, 1), unmatched=True):
    height, width = shape
    grid = [[0] * (width + 10) for _ in range(2 * height + 3)]
    expected = deepcopy(grid)
    for top, color in ((1, 1), (height + 2, 2)):
        枠を描く(grid, top, 1, height, width, color)
        枠を描く(expected, top, 1, height, width, color)
    # 独立に列挙した四つの符号盤の基準位置。
    centers, slots = {
        (5, 5): ((3, 9), (3,)),
        (5, 9): ((3, 9), (3, 5, 7)),
        (7, 9): ((4, 12), (3, 5, 7)),
        (6, 12): ((3, 10), (3, 5, 7, 9)),
    }[shape]
    for index, count in enumerate(counts):
        color = index + 1
        for item in range(count):
            row, col = 1 + 2 * item, width + 4 + 3 * index
            grid[row][col] = color
            if item % 2 == 0:
                grid[row][col + 1] = color  # 面積2でも一つの物理成分。
        for col in (slots[-count:] if count else ()):
            expected[centers[index]][col] = color
    if unmatched:
        grid[-2][width + 4] = grid[-2][width + 5] = 3
    return {'input': grid, 'output': expected}


def 教師(with_witness=True):
    return [教材(unmatched=with_witness), 教材((7, 9), (1, 2), False), 教材((6, 12), (3, 2), False)]


class 枠計数回帰(unittest.TestCase):
    def test_物理成分数を色別の右slotへ保存(self):
        pair = 教材(); output, record = guarded_render(pair['input'], removal_witness=True)
        self.assertEqual(output, pair['output'])
        cert = record['certificate']
        self.assertEqual(cert['encoded_by_color'], {1: 2, 2: 1})
        self.assertEqual(cert['represented_item_count'], 3)
        self.assertEqual(cert['physical_item_count'], 4)
        self.assertEqual(cert['unmatched_components'], 1)

    def test_可変寸法と偶数寸法のfloor位相を保持(self):
        for shape, counts in (((5, 5), (1, 1)), ((7, 9), (1, 2)), ((6, 12), (3, 2))):
            pair = 教材(shape, counts)
            self.assertEqual(guarded_render(pair['input'], removal_witness=True)[0], pair['output'])

    def test_配色変更でも入力内frame対応を使う(self):
        pair = 教材(); mapping = {0: 8, 1: 5, 2: 7, 3: 9}
        convert = lambda grid: [[mapping[v] for v in row] for row in grid]
        self.assertEqual(guarded_render(convert(pair['input']), removal_witness=True)[0], convert(pair['output']))

    def test_対応物体0のframeも保存する(self):
        pair = 教材(counts=(0, 2))
        output, record = guarded_render(pair['input'], removal_witness=True)
        self.assertEqual(output, pair['output'])
        self.assertEqual(record['certificate']['encoded_by_color'][1], 0)

    def test_同色frameでcountを複製しない(self):
        grid = 教材()['input']
        for r in range(7, 12):
            for c in range(1, 10):
                if grid[r][c] == 2:
                    grid[r][c] = 1
        self.assertIsNotNone(render_frame_component_count_slots(grid)[0])
        self.assertEqual(guarded_render(grid, removal_witness=True)[1]['failure'], 'duplicate_frame_color')

    def test_容量超過は他frameも部分排出しない(self):
        grid = 教材(counts=(4, 1))['input']
        self.assertIsNone(render_frame_component_count_slots(grid)[0])
        self.assertEqual(guarded_render(grid, removal_witness=True)[1]['failure'], 'slot_overflow')

    def test_未対応色の消去には教師証拠が必要(self):
        pair = 教材()
        self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'unmatched_removal_without_teacher_witness')
        self.assertEqual(guarded_render(pair['input'], removal_witness=True)[0], pair['output'])
        no_removal = 教材(unmatched=False)
        self.assertEqual(guarded_render(no_removal['input'])[0], no_removal['output'])

    def test_消去許可はframe不在という関係で色whitelistでない(self):
        view = 枠計数教材(教師()); self.assertEqual(view.消去証拠数, 1)
        pair = 教材(); pair['input'] = [[9 if v == 3 else v for v in row] for row in pair['input']]
        self.assertEqual(view.候補(pair['input'], {})[0], pair['output'])
        view = 枠計数教材(教師(False)); self.assertTrue(view.適合); self.assertEqual(view.消去証拠数, 0)
        self.assertEqual(view.候補(pair['input'], {})[1]['failure'], 'unmatched_removal_without_teacher_witness')

    def test_背景同率不正格子はHOLD(self):
        self.assertEqual(guarded_render([[0, 1], [1, 0]])[1]['failure'], 'background_tie')
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')

    def test_全rawframeと全成分のcoverageを省略しない(self):
        pair = 教材(); components = module.old.foreground_components(pair['input'], 0)
        for altered in (components[1:], components + [components[-1]]):
            with patch.object(module.old, 'foreground_components', return_value=altered):
                self.assertIsNone(guarded_render(pair['input'], removal_witness=True)[0])

    def test_元出力不一致を検証格子へ置換しない(self):
        pair = 教材(); output, record = render_frame_component_count_slots(pair['input'])
        output[0][0] = 9
        with patch.object(module.old, 'render_frame_component_count_slots', return_value=(output, record)):
            self.assertEqual(guarded_render(pair['input'], removal_witness=True)[1]['failure'], 'source_output_disagrees_or_no_candidate')

    def test_失敗教師重複教師から証拠を得ない(self):
        pairs = 教師(); pairs[-1]['output'][0][0] = 9
        view = 枠計数教材(pairs); self.assertFalse(view.適合); self.assertEqual(view.消去証拠数, 0)
        pair = 教材(); view = 枠計数教材([pair, pair]); self.assertFalse(view.適合)

    def test_native三盤面と消去witness一件を分ける(self):
        pairs = 教師(); view = 枠計数教材(pairs); boundary = '枠計数対照'
        self.assertTrue(view.適合); self.assertEqual(view.消去証拠数, 1)
        self.assertFalse(候補機構を学習(HDS学習実行系(), {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertEqual(record['現在観測数'], 3); self.assertEqual(record['事前観測数'], 0)
        query = 教材((6, 12), (2, 1))
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済み証拠なし消去queryは全体HOLD(self):
        task = {'train': 教師(False), 'test': [{'input': 教材()['input']}]}
        result = 課題を解く(task, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARC枠内成分計数')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])
        task['task_id'] = 'forbidden'
        with self.assertRaises(ValueError):
            課題を解く(task, [])
        task.pop('task_id'); task['test'][0]['output'] = [[1]]
        with self.assertRaises(ValueError):
            課題を解く(task, [])


if __name__ == '__main__':
    unittest.main()
