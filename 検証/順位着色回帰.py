"""固定header符号・全role適用・cue保存と三盤面支持を検証する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 順位着色教材 as module
from 接続.ARC2.順位着色教材 import guarded_render, 順位着色教材
from 接続.ARC2.既存順位着色 import apply_header_ranked_vertical_run_recolor
from 接続.ARC2.HDS接続 import HDS学習実行系, 候補機構を学習, 出力格子, 観測へ, 課題を解く


def 教材(rank=2, specs=((3, 5, 10), (5, 7, 1), (7, 9, 5), (9, 11, 3))):
    grid = [[0] * 14 for _ in range(18)]
    for r in range(rank):
        grid[r][0] = 2
    for col, top, length in specs:
        grid[top][col] = grid[top + length + 1][col] = 2
        for r in range(top + 1, top + length + 1):
            grid[r][col] = 5
    output = deepcopy(grid)
    col, top, length = sorted(specs, key=lambda s: (s[1], s[0]))[rank - 1]
    for r in range(top + 1, top + length + 1):
        output[r][col] = 2
    return {'input': grid, 'output': output}


def 教師():
    return [教材(rank) for rank in (1, 2, 3)]


class 順位着色回帰(unittest.TestCase):
    def test_rank1から4は長さでなく上順(self):
        for rank, length in enumerate((10, 1, 5, 3), 1):
            pair = 教材(rank)
            output, rec = guarded_render(pair['input'])
            self.assertEqual(output, pair['output'])
            self.assertEqual(rec['changed_count'], length)
            self.assertEqual(rec['actions'][0]['header_rank'], rank)

    def test_同じ上端なら左を先に数える(self):
        pair = 教材(1, ((9, 5, 2), (3, 5, 3)))
        output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(rec['actions'][0]['selected_candidate']['col'], 3)

    def test_headerは面積でなく高さ(self):
        pair = 教材(2)
        pair['input'][0][1] = pair['output'][0][1] = 2
        output, rec = guarded_render(pair['input'])
        self.assertEqual(output, pair['output'])
        self.assertEqual(len(rec['actions'][0]['header_component']), 3)
        self.assertEqual(rec['actions'][0]['header_rank'], 2)

    def test_色と空白配置を変えても同じ符号(self):
        pair = 教材(3)
        palette = {0: 8, 2: 1, 5: 4}
        change = lambda g: [[palette[v] for v in row] for row in g]
        self.assertEqual(guarded_render(change(pair['input']))[0], change(pair['output']))
        grid = deepcopy(pair['input']); expected = deepcopy(pair['output'])
        for row in grid:
            row.insert(2, 0)
        for row in expected:
            row.insert(2, 0)
        self.assertEqual(guarded_render(grid)[0], expected)

    def test_別headerの候補が無ければ部分出力しない(self):
        grid = 教材()['input']; grid[0][13] = 3
        self.assertIsNotNone(apply_header_ranked_vertical_run_recolor(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'header_and_run_target_sets_differ')

    def test_runのheader不足を黙殺しない(self):
        grid = 教材()['input']; grid[10][12] = grid[12][12] = 3; grid[11][12] = 5
        self.assertIsNotNone(apply_header_ranked_vertical_run_recolor(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'header_and_run_target_sets_differ')

    def test_同色topcomponent複数と順位範囲外(self):
        grid = 教材()['input']; grid[0][13] = 2
        self.assertEqual(guarded_render(grid)[1]['failure'], 'top_color_component_not_unique')
        grid = 教材()['input']
        for r in range(5):
            grid[r][0] = 2
        self.assertEqual(guarded_render(grid)[1]['failure'], 'header_rank_out_of_range')

    def test_別runの括り端点を変更する選択は保留(self):
        grid = [[0] * 9 for _ in range(9)]
        grid[0][0] = 2; grid[0][2] = 3
        for row, value in enumerate((2, 3, 2, 3, 2), 3):
            grid[row][5] = value
        self.assertIsNotNone(apply_header_ranked_vertical_run_recolor(grid)[0])
        self.assertEqual(guarded_render(grid)[1]['failure'], 'selected_run_overwrites_cue')

    def test_全header端点と非選択cellを保存(self):
        pair = 教材(2); output, rec = guarded_render(pair['input'])
        changed = {tuple(cell) for action in rec['actions'] for cell in action['changed_cells']}
        self.assertEqual(len(changed), 1)
        self.assertTrue(all(output[r][c] == v for r, row in enumerate(pair['input'])
                            for c, v in enumerate(row) if (r, c) not in changed))

    def test_元renderer出力不一致なら代替しない(self):
        pair = 教材(); output, rec = apply_header_ranked_vertical_run_recolor(pair['input'])
        bad = deepcopy(output); bad[-1][-1] = 9
        with patch.object(module, 'apply_header_ranked_vertical_run_recolor', return_value=(bad, rec)):
            self.assertEqual(guarded_render(pair['input'])[1]['failure'], 'source_output_disagrees')

    def test_不正格子と背景同率とheaderなし(self):
        for grid in ([], [[0], [0, 1]], [[True]], [[10]], [[0] * 31]):
            self.assertEqual(guarded_render(grid)[1]['failure'], 'invalid_arc_grid')
        self.assertEqual(guarded_render([[0, 1]])[1]['failure'], 'background_tie')
        self.assertEqual(guarded_render([[0] * 4 for _ in range(4)])[1]['failure'], 'no_header_colors')

    def test_教師反例と重複を支持にしない(self):
        pairs = 教師(); pairs[-1]['output'][-1][-1] = 9
        self.assertFalse(順位着色教材(pairs).全教師再現)
        pair = 教材()
        self.assertFalse(順位着色教材([pair, pair]).全教師再現)

    def test_native三盤面だけ支持し反例隔離を保持(self):
        pairs = 教師(); view = 順位着色教材(pairs); boundary = '順位対照'
        self.assertTrue(view.全教師再現)
        engine = HDS学習実行系()
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        record = 候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)
        self.assertTrue(record['同値採用']); self.assertEqual(record['現在観測数'], 3)
        self.assertEqual(record['事前観測数'], 0)
        query = 教材(4)
        self.assertEqual(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'], query['output'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[9]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': query['output']}, boundary), 同値必須=True)['answer'])

    def test_採用済みqueryの欠落roleは全体HOLD(self):
        grid = 教材()['input']; grid[0][13] = 3
        result = 課題を解く({'train': 教師(), 'test': [{'input': grid}]}, [])
        record = next(r for r in result['families'] if r['境界'] == 'ARCheader順位着色')
        self.assertTrue(record['採用可']); self.assertTrue(record['同値採用'])
        self.assertIsNone(result['results'][0]['answer'])


if __name__ == '__main__':
    unittest.main()
