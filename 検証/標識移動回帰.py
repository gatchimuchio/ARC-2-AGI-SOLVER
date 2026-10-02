"""標識優先の固定protocol・同時描画・教師branch証拠を確認する。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

根 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(根), str(根 / 'HDS/学習系統/v0.4.2')]
from 接続.ARC2.標識移動教材 import 標識移動教材, guarded_guided_box
from 接続.ARC2.既存標識移動 import _guided_box_marker_compaction_render
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く, HDS学習実行系, 候補機構を学習, 出力格子, 観測へ

方針 = {'roles': {'marker_color': 9, 'interior_color': 0, 'fuel_color': 5, 'filled_color': 7}}


def 教材(top=3, fuel=2, stop=True):
    grid = [[6] * 14 for _ in range(12)]
    cells = {(r, c) for r in range(top, top + 5) for c in range(2, 5)}
    for r, c in cells:
        grid[r][c] = 9 if r == top else 0
    grid[top + 4][4] = 7
    fuel_cells = sorted(cell for cell in cells if grid[cell[0]][cell[1]] == 0)[:fuel]
    for r, c in fuel_cells:
        grid[r][c] = 5
    if stop:
        grid[0][2:5] = [9] * 3
    move = min(top if stop else 1, fuel)
    output = deepcopy(grid)
    if move:
        for r, c in cells:
            output[r][c] = 6
        for r, c in cells:
            if not stop and r == top:
                continue
            output[r - move][c] = 7 if (r, c) in set(fuel_cells[:move]) else grid[r][c]
    return {'input': grid, 'output': output}


def 教師():
    return [教材(), 教材(4, 6), 教材(2, 4, False)]


def 衝突場面(stationary=False):
    grid = [[6] * 13 for _ in range(5)]
    for r in range(1, 4):
        for c in range(4):
            grid[r][c] = 9 if c == 3 else 0
        for c in range(8, 12):
            grid[r][c] = 9 if c == 8 else 0
    for r, c in [(1, 0), (1, 1), (1, 2), (2, 0), (2, 2)]:
        grid[r][c] = 5
    if stationary:
        grid[2][7] = 0
    else:
        for r, c in [(2, 9), (2, 10), (2, 11), (3, 10), (3, 11)]:
            grid[r][c] = 5
    return grid


class 標識移動回帰(unittest.TestCase):
    def test_燃料数と標識距離から全格子を再現(self):
        for pair in 教師() + [教材(5, 8)]:
            self.assertEqual(guarded_guided_box(pair['input'], 方針, allow_contact_deletion=True)[0], pair['output'])

    def test_近い背景帯より遠い標識を優先する元protocol(self):
        pair = 教材(4, 6)
        out, record = guarded_guided_box(pair['input'], 方針)
        self.assertEqual(out, pair['output'])
        actor = record['guided_box_component_records'][0]
        self.assertEqual((actor['distance'], actor['move']), (4, 4))
        self.assertTrue(all(v == 6 for v in pair['input'][3][2:5]))

    def test_回転と配色変更でも同じ役割関係(self):
        pair = 教材(4, 6)
        for name in ('rot90', 'rot180', 'rot270'):
            self.assertEqual(guarded_guided_box(transform_grid_by_name(pair['input'], name), 方針)[0], transform_grid_by_name(pair['output'], name))
        mapping = {6: 1, 9: 2, 0: 3, 5: 4, 7: 8}
        recolor = lambda grid: [[mapping[v] for v in row] for row in grid]
        policy = {'roles': {k: mapping[v] for k, v in 方針['roles'].items()}}
        self.assertEqual(guarded_guided_box(recolor(pair['input']), policy)[0], recolor(pair['output']))

    def test_接触消去は現教師の証拠が必要(self):
        pair = 教材(2, 4, False)
        self.assertEqual(guarded_guided_box(pair['input'], 方針)[1]['failure'], 'contact_deletion_without_teacher_witness')
        out, record = guarded_guided_box(pair['input'], 方針, allow_contact_deletion=True)
        self.assertEqual(out, pair['output']); self.assertEqual(record['contact_marker_deletions'], 3)
        view = 標識移動教材(教師()[:2])
        self.assertIsNotNone(view.方針); self.assertEqual(view.接触消去教師数, 0)
        self.assertIsNone(view.候補(pair['input'], {})[0])

    def test_零燃料actorと標識だけの停止点は保存(self):
        grid = 教材()['input']
        actor = 教材(3, 0)['input']
        for r in range(12):
            for c in range(2, 5):
                grid[r][c + 6] = actor[r][c]
        out, record = guarded_guided_box(grid, 方針)
        self.assertEqual(record['actor_count'], 2); self.assertEqual(record['moved_actor_count'], 1)
        self.assertTrue(all(out[r][8:11] == grid[r][8:11] for r in range(12)))

    def test_背景同率と孤立した役割成分は保留(self):
        grid = 教材()['input']; cells = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == 6]
        # Odd background count: remove one cell to keep an exact tie.
        if len(cells) % 2:
            r, c = cells.pop(); grid[r][c] = 7
        for r, c in cells[:len(cells) // 2]:
            grid[r][c] = 2
        self.assertEqual(guarded_guided_box(grid, 方針)[1]['failure'], 'travel_background_not_unique')
        grid = 教材()['input']; grid[11][13] = 0
        self.assertEqual(guarded_guided_box(grid, 方針)[1]['failure'], 'unparsed_nonmarker_role_component')

    def test_方向同率と解析不能actorを黙って飛ばさない(self):
        grid = [[6] * 5 for _ in range(5)]
        grid[2][1:4] = [9] * 3; grid[1][2] = 5; grid[3][2] = 0
        self.assertEqual(guarded_guided_box(grid, 方針)[1]['failure'], 'actor_side_tie')
        grid[1][1:3] = [9] * 2; grid[2][1:3] = [9] * 2; grid[2][3] = 6
        self.assertEqual(guarded_guided_box(grid, 方針)[1]['failure'], 'unparsed_actor')

    def test_画面外を切り落として答えにしない(self):
        grid = [[6] * 7 for _ in range(7)]
        grid[1][2:5] = [9] * 3; grid[0][2] = 5
        for r in range(2, 6):
            grid[r][2:5] = [0] * 3
        self.assertEqual(guarded_guided_box(grid, 方針, allow_contact_deletion=True)[1]['failure'], 'out_of_bounds_target')

    def test_変換後の色競合と静止物体上書きを保留(self):
        self.assertEqual(guarded_guided_box(衝突場面(), 方針)[1]['failure'], 'conflicting_final_color_proposals')
        self.assertEqual(guarded_guided_box(衝突場面(True), 方針)[1]['failure'], 'different_stationary_overwrite')

    def test_教師反例と重複は方針を採用しない(self):
        pairs = 教師(); pairs[1]['output'][0][0] = 1
        self.assertIsNone(標識移動教材(pairs).方針)
        pair = 教材(); self.assertIsNone(標識移動教材([pair, deepcopy(pair)]).方針)

    def test_三教師だけをnative支持として観測(self):
        pair = 教材(5, 8)
        result = 課題を解く({'train': 教師(), 'test': [{'input': pair['input']}]}, [])
        self.assertEqual(result['results'][0]['answer'], pair['output'])
        family = next(x for x in result['families'] if x['境界'] == 'ARC標識移動')
        self.assertEqual(family['現在観測数'], 3); self.assertEqual(family['事前観測数'], 0)
        self.assertTrue(family['同値採用']); self.assertEqual(result['guided_compaction']['接触消去教師数'], 1)

    def test_native支持不足と後発反例は保留(self):
        pairs = 教師(); view = 標識移動教材(pairs); boundary = '標識移動対照'
        engine = HDS学習実行系()
        self.assertFalse(候補機構を学習(engine, {'train': pairs[:2]}, [], boundary, view.候補)['同値採用'])
        engine = HDS学習実行系()
        self.assertTrue(候補機構を学習(engine, {'train': pairs}, [], boundary, view.候補)['同値採用'])
        engine.実行(観測へ({'候補': pairs[0]['output'], '出力': [[3]]}, boundary))
        self.assertIsNone(出力格子(engine, 観測へ({'候補': pairs[1]['output']}, boundary), 同値必須=True)['answer'])


if __name__ == '__main__':
    unittest.main()
