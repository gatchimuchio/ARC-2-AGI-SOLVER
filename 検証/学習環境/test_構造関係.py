"""汎用構造関係schemaの新規検証。特定ARC課題の解法を含めない。"""
import tempfile
import unittest
from 接続.学習環境.HDS接続 import HDS学習機械
from 接続.学習環境.契約 import 予測要求
from hds学習系統 import HDS学習系統, 外部入力


def train(pairs):
    s = HDS学習系統(最大条件数=1)
    for a, b in pairs:
        s.処理する(外部入力({'前': a, '後': b}, '構造probe'))
    return s


def structural(s, source):
    result = s.エンジン.照会(s.吸気系.取り込む(外部入力({'前': source}, '構造probe')))
    return [p.予測値 for p in result.予測群 if p.結果経路 == ('後',)]


def mapping_machine():
    seqs = [[1, 2, 1, 2], [2, 1, 2, 1], [1, 1, 2, 2]]
    return train([(x, [{1: 7, 2: 8}[v] for v in x]) for x in seqs])


class 汎用構造関係試験(unittest.TestCase):
    def test_同値を未見値と未見長へ適用(self):
        s = train([(x, x) for x in [[1, 2], [2, 3, 4], [4, 5]]])
        self.assertIn([9, 8, 7, 6], structural(s, [9, 8, 7, 6]))

    def test_同値を未見二次元形状へ適用(self):
        s = train([(x, x) for x in [[[1, 2]], [[3], [4]], [[5, 6], [7, 8]]]])
        self.assertIn([[9, 8, 7]], structural(s, [[9, 8, 7]]))

    def test_未知キーでも学習済み関係を使う(self):
        s = train([(x, x) for x in [{'a': 1, 'b': 2}, {'c': 3, 'd': 4}, {'e': 5, 'f': 6}]])
        self.assertIn({'新': 9, '別': 8}, structural(s, {'新': 9, '別': 8}))

    def test_辞書の列挙順を意味にしない(self):
        s = train([({'a': x, 'b': y}, {'b': y, 'a': x}) for x, y in [(1, 2), (3, 4), (5, 6)]])
        self.assertIn({'b': 8, 'a': 9}, structural(s, {'b': 8, 'a': 9}))

    def test_混在型辞書キーでも列挙順に依存しない(self):
        s = train([({1: x, 'x': y}, {'x': y, 1: x}) for x, y in [(1, 2), (3, 4), (5, 6)]])
        self.assertIn({'z': 9, 2: 8}, structural(s, {'z': 9, 2: 8}))

    def test_要素対応を未見の並びと長さへ適用(self):
        s = mapping_machine()
        self.assertIn([8, 7, 7, 8, 8], structural(s, [2, 1, 1, 2, 2]))

    def test_有限要素対応の未知値は保留(self):
        self.assertEqual(structural(mapping_machine(), [1, 3, 2]), [])

    def test_未見の葉型を黙って同一視しない(self):
        s = train([(x, x) for x in [[1, 2], [2, 3], [4, 5]]])
        self.assertEqual(structural(s, ['a', 'b']), [])

    def test_未見の根容器型を黙って同一視しない(self):
        s = mapping_machine()
        self.assertEqual(structural(s, {'a': 1, 'b': 2}), [])

    def test_位置依存対応を一様対応と誤認しない(self):
        s = train([([1, 2], [7, 8]), ([2, 1], [7, 8]), ([1, 1], [7, 8])])
        self.assertEqual(structural(s, [1, 2]), [])

    def test_一位置だけでは添字一般へ昇格しない(self):
        s = train([([x], [x]) for x in (1, 2, 3)])
        self.assertEqual(structural(s, [9, 8]), [])

    def test_形状変更例を構造保全と誤認しない(self):
        s = train([([x, x], [x]) for x in (1, 2, 3)])
        self.assertEqual(structural(s, [9, 8]), [])

    def test_反例を既存HDSが隔離する(self):
        s = mapping_machine()
        s.処理する(外部入力({'前': [1, 2, 1], '後': [8, 7, 8]}, '構造probe'))
        self.assertTrue(any(p.関係型 == '構造要素対応関係' for p in s.エンジン._係争中原理群()))
        self.assertEqual(structural(s, [1, 2, 1]), [])

    def test_構造型保存復元(self):
        s = mapping_machine()
        with tempfile.TemporaryDirectory() as d:
            s.保存する(d + '/hds.json')
            restored = HDS学習系統.読み込む(d + '/hds.json')
        self.assertEqual(structural(s, [2, 1, 2]), structural(restored, [2, 1, 2]))

    def test_ARC変数形状の同値予測(self):
        m = HDS学習機械()
        for grid in (((1, 2), (3, 4)), ((2, 4), (6, 8)), ((5, 1), (2, 7))):
            m.観測する(予測要求(grid), grid)
        self.assertEqual(m.予測する(予測要求(((9, 8, 7),))).出力, ((9, 8, 7),))

    def test_ARC変数形状の要素対応(self):
        m = HDS学習機械()
        for grid in (((1, 2), (1, 2)), ((2, 1), (2, 1)), ((1, 1), (2, 2))):
            dest = tuple(tuple({1: 7, 2: 8}[v] for v in row) for row in grid)
            m.観測する(予測要求(grid), dest)
        self.assertEqual(m.予測する(予測要求(((2, 1, 1, 2, 2),))).出力, ((8, 7, 7, 8, 8),))

    def test_定値の適用範囲を結果側で隠さない(self):
        m = HDS学習機械()
        for x in (1, 2, 3):
            m.観測する(予測要求(((x,),)), ((7,),))
        m.観測する(予測要求(((4,),)), ((8, 8),))
        self.assertGreater(m.概況()['隔離原理数'], 0)


class 構造反証回帰試験(unittest.TestCase):
    def test_未知値を含んでも既知位置の反例を隠さない(self):
        s = mapping_machine()
        s.処理する(外部入力({'前': [1, 3], '後': [9, 0]}, '構造probe'))
        self.assertTrue(any(p.関係型 == '構造要素対応関係' for p in s.エンジン._係争中原理群()))
        self.assertEqual(structural(s, [1, 2]), [])

    def test_未知値だけなら反例とは断定しない(self):
        s = mapping_machine()
        s.処理する(外部入力({'前': [3, 3], '後': [0, 0]}, '構造probe'))
        self.assertFalse(any(p.関係型 == '構造要素対応関係' for p in s.エンジン._係争中原理群()))

    def test_外側の文脈だけ変えて構造支持を水増ししない(self):
        s = HDS学習系統(最大条件数=1)
        for context in (1, 2, 3):
            s.処理する(外部入力({'前': [1, 2], '後': [1, 2], '文脈': context}, '構造probe'))
        self.assertFalse(any(p.関係型.startswith('構造') for p in s.エンジン._有効原理群()))

    def test_構造関係を後続課題の異なる形状へ再検証転用(self):
        m = HDS学習機械()
        for grid in (((1, 2), (1, 2)), ((2, 1), (2, 1)), ((1, 1), (2, 2))):
            dest = tuple(tuple({1: 7, 2: 8}[v] for v in row) for row in grid)
            m.観測する(予測要求(grid), dest)
        m.新しい課題()
        for grid in (((1, 2, 1, 2),), ((2, 1, 2, 1),)):
            dest = tuple(tuple({1: 7, 2: 8}[v] for v in row) for row in grid)
            m.観測する(予測要求(grid), dest)
        self.assertEqual(m.概況()['経験数'], 2)
        self.assertEqual(m.予測する(予測要求(((2, 2, 1, 1, 2),))).出力, ((8, 8, 7, 7, 8),))


class 構造権限回帰試験(unittest.TestCase):
    def test_懐疑対象の外で構造候補を作らない(self):
        from hds学習系統.型 import 懐疑記録
        s = HDS学習系統(最大条件数=1)
        for x in (1, 2, 3):
            s.処理する(外部入力({'a': [x, x + 1], 'b': [x, x + 1], 'focus': x}, '構造probe'))
        e = s.エンジン
        req = 懐疑記録('限定', '経験', '限定', '限定', (), '', (('focus',),), ('条件関係生成',))
        candidates = e.推論器.導出する(e._経験群(), (req,), 3, e._次)
        self.assertFalse(any(x.関係型.startswith('構造') for x in candidates))

    def test_必要な構造文脈がない定値は保留(self):
        s = HDS学習系統(最大条件数=1)
        for x in (1, 2, 3):
            s.処理する(外部入力({'a': [x, x + 1], 'b': 7}, '構造probe'))
        result = s.エンジン.照会(s.吸気系.取り込む(外部入力({}, '構造probe')))
        self.assertFalse(any(p.結果経路 == ('b',) for p in result.予測群))

    def test_全構造と固定位置の矛盾をHDS内で検出(self):
        s = train([(x, x) for x in [[1, 2], [1, 3], [1, 4]]])
        result = s.エンジン.照会(s.吸気系.取り込む(外部入力({'前': [9, 5]}, '構造probe')))
        self.assertTrue(result.競合群)
        self.assertFalse(any(p.結果経路 == ('後',) for p in result.予測群))


class 構造結果型試験(unittest.TestCase):
    def test_容器予測に対するscalar結果を未観測扱いしない(self):
        s = mapping_machine()
        s.処理する(外部入力({'前': [1, 2], '後': 7}, '構造probe'))
        self.assertTrue(any(p.関係型 == '構造要素対応関係' for p in s.エンジン._係争中原理群()))

    def test_同じ値の混在キー容器を順序だけで競合させない(self):
        from hds学習系統.型 import 予測記録
        from hds学習系統.構造関係 import 予測重複を監査する, 容器署名
        a, b = {1: 7, 'x': 8}, {'x': 8, 1: 7}
        self.assertEqual(容器署名(a), 容器署名(b))
        records = (予測記録('a', ('結果',), a, ()), 予測記録('b', ('結果',), b, ()))
        self.assertEqual(予測重複を監査する(records)[0], ())


class 構造互換試験(unittest.TestCase):
    def test_無関係な非JSONメタ情報で構造学習を壊さない(self):
        s = train([(x, x) for x in [[1, 2], [2, 3], [3, 4]]])
        s.処理する(外部入力({'前': [4, 5], '後': [4, 5], 'metadata': {99}}, '構造probe'))
        self.assertIn([8, 9], structural(s, [8, 9]))

    def test_新添字関係の保存形式は7(self):
        import json
        from pathlib import Path
        from hds学習系統.永続化 import _復号
        s = mapping_machine()
        with tempfile.TemporaryDirectory() as d:
            s.保存する(d + '/hds.json')
            saved = _復号(json.loads(Path(d + '/hds.json').read_text()))
        self.assertEqual(saved['形式版'], 7)

    def test_既存形式3のスカラー原理を読める(self):
        import json
        from pathlib import Path
        from hds学習系統.永続化 import _復号, _符号化
        s = HDS学習系統()
        for x in (1, 2, 3):
            s.処理する(外部入力({'a': x, 'b': x}, '旧形式'))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'hds.json'
            s.保存する(p)
            saved = _復号(json.loads(p.read_text()))
            saved['形式版'] = 3
            p.write_text(json.dumps(_符号化(saved)))
            restored = HDS学習系統.読み込む(p)
        result = restored.エンジン.照会(restored.吸気系.取り込む(外部入力({'a': 9}, '旧形式')))
        self.assertTrue(any(p.結果経路 == ('b',) and p.予測値 == 9 for p in result.予測群))

if __name__ == '__main__':
    unittest.main()
