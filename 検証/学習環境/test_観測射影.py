"""同じ格子の二つの観測Frameと、観測された長さ変動だけの一般化。"""
import random
import tempfile
import unittest
from 接続.学習環境.HDS接続 import HDS学習機械, 観測射影
from 接続.学習環境.契約 import 予測要求
from 接続.学習環境.実験 import 実験する
from hds学習系統 import HDS学習系統, 外部入力
from hds学習系統.構造関係 import 形状条件を学ぶ, 形状条件に適合


class 形状条件試験(unittest.TestCase):
    def test_観測済みの長さ変動だけを一般化(self):
        p = 形状条件を学ぶ([[1, 2], [1, 2, 3], [1, 2, 3, 4]])
        self.assertTrue(形状条件に適合(p, [1, 2, 3, 4, 5]))
        self.assertFalse(形状条件に適合(p, [[1], [2]]))

    def test_固定長は一般化しない(self):
        p = 形状条件を学ぶ([[1, 2], [3, 4], [5, 6]])
        self.assertFalse(形状条件に適合(p, [9, 8, 7]))
        self.assertTrue(形状条件に適合(p, [9, 8]))

    def test_固定鍵は保持する(self):
        p = 形状条件を学ぶ([{'a': 1}, {'a': 2}, {'a': 3}])
        self.assertFalse(形状条件に適合(p, {'b': 1}))
        self.assertTrue(形状条件に適合(p, {'a': 9}))

    def test_変動した鍵の型範囲を保持する(self):
        p = 形状条件を学ぶ([{'a': 1}, {'b': 2}, {'c': 3}])
        self.assertTrue(形状条件に適合(p, {'new': 9, 'other': 8}))
        self.assertFalse(形状条件に適合(p, {1: 9}))

    def test_可変長の文脈で定値を適用(self):
        s = HDS学習系統()
        for n in (2, 3, 4):
            s.処理する(外部入力({'a': list(range(n)), 'b': 7}, '長さprobe'))
        result = s.エンジン.照会(s.吸気系.取り込む(外部入力({'a': [9, 8, 7, 6, 5]}, '長さprobe')))
        self.assertTrue(any(p.結果経路 == ('b',) and p.予測値 == 7 for p in result.予測群))

    def test_一般化文脈の中の反例は隔離(self):
        s = HDS学習系統()
        for n in (2, 3, 4):
            s.処理する(外部入力({'a': list(range(n)), 'b': 7}, '長さprobe'))
        s.処理する(外部入力({'a': [9, 8, 7, 6, 5], 'b': 8}, '長さprobe'))
        self.assertTrue(any(p.結果経路 == ('b',) for p in s.エンジン._係争中原理群()))


class 観測Frame試験(unittest.TestCase):
    def test_両表現は同じ値を保持する(self):
        grid = ((1, 2), (3, 4))
        a, b = 観測射影(grid), 観測射影(grid, '配列階層')
        self.assertEqual(a['行数'], b['行数'])
        self.assertEqual(a['列数'], b['列数'])
        self.assertEqual([a['セル'][f'{r},{c}'] for r in range(2) for c in range(2)], [x for row in b['セル'] for x in row])

    def test_Frameは状態署名に含む(self):
        self.assertNotEqual(HDS学習機械().状態署名(), HDS学習機械(観測表現='配列階層').状態署名())

    def test_Frameを途中で暗黙変更できない(self):
        m = HDS学習機械()
        with self.assertRaises(AttributeError):
            m.観測表現 = '配列階層'

    def test_配列Frame保存復元(self):
        m = HDS学習機械(観測表現='配列階層')
        for x in (1, 2, 3):
            m.観測する(予測要求(((x, 4),)), ((x, 4),))
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d)
            n = HDS学習機械.読み込む(d)
        self.assertEqual(n.観測表現, '配列階層')
        self.assertEqual(m.状態署名(), n.状態署名())

    def test_同じHDSで部分構造を未見幅へ適用(self):
        # 教師用の構造対照。実装は選択行も色も知らない。
        rng = random.Random(0)
        pairs = []
        for width in (2, 3, 4, 2, 3, 4, 2, 3):
            grid = tuple(tuple(rng.randrange(10) for _ in range(width)) for _ in range(3))
            pairs.append((grid, (grid[1],)))
        machines = {mode: HDS学習機械(観測表現=mode) for mode in ('座標辞書', '配列階層')}
        for m in machines.values():
            for x, y in pairs:
                m.観測する(予測要求(x), y)
        request = 予測要求(((1, 2, 3, 4, 5), (9, 8, 7, 6, 5), (2, 3, 4, 5, 6)))
        self.assertIsNone(machines['座標辞書'].予測する(request).出力)
        self.assertEqual(machines['配列階層'].予測する(request).出力, ((9, 8, 7, 6, 5),))

    def test_記憶除去も同じ配列Frame(self):
        content = {'train': [{'input': [[x]], 'output': [[x]]} for x in (1, 2, 3)],
                   'test': [{'input': [[9]], 'output': [[9]]}]}
        report, machine = 実験する(content, 観測表現='配列階層')
        self.assertEqual(machine.観測表現, '配列階層')
        self.assertEqual((report['current'], report['記憶除去']), (1, 0))


class 射影拒否試験(unittest.TestCase):
    def test_壊れた全格子を他の寸法で切り取らない(self):
        from hds学習系統.型 import 予測記録
        m = HDS学習機械(観測表現='配列階層')
        rows = [予測記録('p', ('出力', 'セル'), [[1, 2], [3]], ()),
                予測記録('h', ('出力', '行数'), 1, ()), 予測記録('w', ('出力', '列数'), 2, ())]
        self.assertEqual(m._予測を格子化(rows, ()).状態, 'HOLD')

    def test_形状の外のセル予測を黙って捨てない(self):
        from hds学習系統.型 import 予測記録
        m = HDS学習機械()
        rows = [予測記録('h', ('出力', '行数'), 1, ()), 予測記録('w', ('出力', '列数'), 1, ()),
                予測記録('a', ('出力', 'セル', '0,0'), 1, ()), 予測記録('b', ('出力', 'セル', '1,0'), 2, ())]
        self.assertEqual(m._予測を格子化(rows, ()).状態, 'HOLD')

    def test_巨大座標を展開する前に拒否(self):
        from hds学習系統.型 import 予測記録
        m = HDS学習機械()
        self.assertEqual(m._予測を格子化([予測記録('p', ('出力', 'セル'), {'100000000,0': 1}, ())], ()).状態, 'HOLD')

    def test_再観測移行は元経験を水増ししない(self):
        from 道具.観測表現を比較 import 旧経験を検証して取り出す, 再観測する
        from 接続.学習環境.HDS接続 import 実装署名
        m = HDS学習機械()
        for x in (1, 2, 3):
            m.観測する(予測要求(((x,),)), ((x,),))
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d)
            records, audit = 旧経験を検証して取り出す(d, 実装署名())
        n, trace = 再観測する(records, '配列階層')
        self.assertEqual(audit['旧経験数'], 3)
        self.assertEqual(len(trace), 3)
        self.assertEqual(n.概況()['全課題保持経験数'], 3)
        self.assertEqual(n.予測する(予測要求(((9,),))).出力, ((9,),))

    def test_再観測は二つの課題境界と六経験を保存(self):
        from 道具.観測表現を比較 import 旧経験を検証して取り出す, 再観測する
        from 接続.学習環境.HDS接続 import 実装署名
        m = HDS学習機械()
        for episode in range(2):
            if episode:
                m.新しい課題()
            for x in (1, 2, 3):
                m.観測する(予測要求(((x,),)), ((x,),))
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d)
            records, _ = 旧経験を検証して取り出す(d, 実装署名())
        n, trace = 再観測する(records, '配列階層')
        self.assertEqual(n.概況()['全課題保持経験数'], 6)
        self.assertEqual(n.概況()['経験数'], 3)
        self.assertEqual(len({t['旧経験参照'] for t in trace}), 6)
        self.assertEqual(len({t['新経験参照'] for t in trace}), 6)
        self.assertEqual([trace[i]['新境界'] == trace[0]['新境界'] for i in range(6)],
                         [True, True, True, False, False, False])

    def test_再観測で未知の旧実装を受理しない(self):
        from 道具.観測表現を比較 import 旧経験を検証して取り出す
        with tempfile.TemporaryDirectory() as d:
            HDS学習機械().保存する(d)
            with self.assertRaises(ValueError):
                旧経験を検証して取り出す(d, '別の実装')

    def test_学習設定の変更も状態署名に現れる(self):
        m = HDS学習機械()
        before = m.状態署名()
        m.学習有効 = False
        self.assertNotEqual(before, m.状態署名())

if __name__ == '__main__':
    unittest.main()
