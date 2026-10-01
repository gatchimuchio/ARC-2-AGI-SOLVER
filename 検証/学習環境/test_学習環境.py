"""今回新設した検証。旧READMEの46試験の再現ではない。"""
import copy
from dataclasses import fields
import json
from pathlib import Path
import tempfile
import unittest

from 接続.学習環境.契約 import 格子化, 予測要求
from 接続.学習環境.HDS接続 import HDS学習機械
from 接続.学習環境.教師 import 公開教材, 教師
from 接続.学習環境.実験 import 実験する
from hds学習系統 import HDS学習系統, 外部入力


def 教材():
    # 機構対照。公開ARCの成績に算入しない。実装にこの写像は存在しない。
    return {'train': [{'input': [[x]], 'output': [[x]]} for x in (1, 2, 3)],
            'test': [{'input': [[9]], 'output': [[9]]}]}


def 学習済み():
    m = HDS学習機械()
    for x in (1, 2, 3):
        m.観測する(予測要求(((x,),)), ((x,),))
    return m


class 境界試験(unittest.TestCase):
    def test_予測契約に正解も識別子もない(self):
        self.assertEqual([f.name for f in fields(予測要求)], ['入力'])

    def test_格子は複製される(self):
        grid = [[1]]
        q = 予測要求(grid)
        grid[0][0] = 9
        self.assertEqual(q.入力, ((1,),))

    def test_不正格子を拒否(self):
        for value in ([], [[]], [[True]], [[10]], [[1], [1, 2]], [[1.0]], ['x']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                格子化(value)

    def test_非公開test形式を拒否(self):
        content = 教材()
        del content['test'][0]['output']
        with self.assertRaises(ValueError):
            公開教材(content)

    def test_予測前の教示を拒否(self):
        t = 教師(公開教材(教材()))
        with self.assertRaises(RuntimeError):
            t.教示(HDS学習機械(), 0)

    def test_正解を変えても予測は変わらない(self):
        a, b = 教材(), 教材()
        b['test'][0]['output'] = [[0]]
        m = 学習済み()
        ta, tb = 教師(公開教材(a)), 教師(公開教材(b))
        pa, oa = ta.評価(m, 'test', 0)
        pb, ob = tb.評価(m, 'test', 0)
        self.assertEqual(pa, pb)
        self.assertTrue(oa.正解)
        self.assertFalse(ob.正解)

    def test_評価では状態不変(self):
        m = 学習済み()
        before = m.状態署名()
        t = 教師(公開教材(教材()))
        t.評価(m, 'test', 0)
        t.評価(m, 'test', 0)
        self.assertEqual(before, m.状態署名())

    def test_同じtrainの再教示拒否(self):
        t, m = 教師(公開教材(教材())), HDS学習機械()
        t.評価(m, 'train', 0)
        t.教示(m, 0)
        with self.assertRaises(RuntimeError):
            t.教示(m, 0)

    def test_test予測ではtrain開示権が生じない(self):
        t, m = 教師(公開教材(教材())), HDS学習機械()
        t.評価(m, 'test', 0)
        with self.assertRaises(RuntimeError):
            t.教示(m, 0)

    def test_更新拒否は状態不変(self):
        m = HDS学習機械()
        before = m.状態署名()
        update = m.観測する(予測要求(((1,),)), ((1,),), 更新許可=False)
        self.assertEqual(update['採否'], 'REJECT')
        self.assertEqual(before, m.状態署名())

    def test_予算超過は黙って解かない(self):
        m = HDS学習機械(最大セル数=1)
        q = 予測要求(((1, 2),))
        before = m.状態署名()
        self.assertEqual(m.予測する(q).状態, 'HOLD')
        self.assertEqual(m.観測する(q, ((1, 2),))['採否'], 'HOLD')
        self.assertEqual(before, m.状態署名())

    def test_教師結果は正解格子を含まない(self):
        t, m = 教師(公開教材(教材())), HDS学習機械()
        _, outcome = t.評価(m, 'test', 0)
        self.assertEqual([f.name for f in fields(outcome)], ['正解', '予測状態'])


class 学習因果試験(unittest.TestCase):
    def test_未提示の値へ同値関係を適用(self):
        report, m = 実験する(教材())
        self.assertEqual((report['previous'], report['current'], report['記憶除去']), (0, 1, 0))
        self.assertEqual(m.概況()['経験数'], 3)
        text = json.dumps(m.状態(), ensure_ascii=False)
        # testの9は学習経験・対応値へ入らない。
        self.assertNotIn('"値": 9', text)

    def test_学習停止対照(self):
        report, m = 実験する(教材(), 学習有効=False)
        self.assertEqual(report['current'], 0)
        self.assertEqual(m.概況()['経験数'], 0)

    def test_同一観測は独立支持でない(self):
        m = HDS学習機械()
        for _ in range(5):
            m.観測する(予測要求(((1,),)), ((1,),))
        self.assertEqual(m.概況()['経験数'], 1)
        self.assertEqual(m.概況()['有効原理数'], 0)

    def test_学習後も未知値で答えを引かない(self):
        m = 学習済み()
        self.assertEqual(m.予測する(予測要求(((8,),))).出力, ((8,),))
        self.assertEqual(m.予測する(予測要求(((9,),))).出力, ((9,),))

    def test_保存復元後も未知値で同じ予測(self):
        m = 学習済み()
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d)
            restored = HDS学習機械.読み込む(d)
        self.assertEqual(m.状態署名(), restored.状態署名())
        self.assertEqual(m.予測する(予測要求(((9,),))), restored.予測する(予測要求(((9,),))))

    def test_別課題へ定値関係を自動転用しない(self):
        m = 学習済み()
        archive = m.新しい課題()
        self.assertTrue(archive['原理履歴'])
        self.assertEqual(m.予測する(予測要求(((9,),))).状態, 'HOLD')
        self.assertEqual(m.概況()['経験数'], 0)

    def test_反例で暫定原理が隔離される(self):
        m = 学習済み()
        m.観測する(予測要求(((4,),)), ((5, 5),))
        self.assertGreater(m.概況()['隔離原理数'], 0)
        self.assertTrue(m.状態()['失敗'])
        self.assertNotEqual(m.予測する(予測要求(((4,),))).出力, ((4,),))

    def test_定値は観測に由来する(self):
        m = HDS学習機械()
        for x in (1, 2, 3):
            m.観測する(予測要求(((x,),)), ((7,),))
        self.assertEqual(m.予測する(予測要求(((9,),))).出力, ((7,),))

    def test_出力競合は作用を拒否する(self):
        m = HDS学習機械()
        for x in (1, 2, 3):
            m.観測する(予測要求(((x, x),)), ((x,),))
        p = m.予測する(予測要求(((8, 9),)))
        self.assertEqual(p.状態, 'HOLD')
        self.assertIsNone(p.出力)
        self.assertIn('出力関係の競合', p.理由)


class HDS新規回帰試験(unittest.TestCase):
    def test_既存同値推論(self):
        s = HDS学習系統()
        for x in (1, 2, 3):
            s.処理する(外部入力({'a': x, 'b': x}, '検証'))
        result = s.エンジン.照会(s.吸気系.取り込む(外部入力({'a': 9}, '検証')))
        self.assertTrue(any(p.結果経路 == ('b',) and p.予測値 == 9 for p in result.予測群))

    def test_定値候補も重複支持で成立しない(self):
        s = HDS学習系統()
        for _ in range(5):
            s.処理する(外部入力({'a': 1, 'b': 7}, '検証'))
        self.assertFalse(any(p.関係型 == '定値関係' for p in s.エンジン._有効原理群()))

    def test_対象系境界を越えない(self):
        s = HDS学習系統()
        for x in (1, 2, 3):
            s.処理する(外部入力({'a': x, 'b': 7}, '教材A'))
        result = s.エンジン.照会(s.吸気系.取り込む(外部入力({'a': 9}, '教材B')))
        self.assertEqual(result.予測群, ())

    def test_原理採用までの必要経験数(self):
        m = HDS学習機械()
        for i in (1, 2):
            m.観測する(予測要求(((i,),)), ((i,),))
            self.assertEqual(m.予測する(予測要求(((9,),))).状態, 'HOLD')
        m.観測する(予測要求(((3,),)), ((3,),))
        self.assertEqual(m.予測する(予測要求(((9,),))).状態, 'COMMIT')


class 再現性試験(unittest.TestCase):
    def test_同じ経験順で同じ論理状態(self):
        self.assertEqual(学習済み().状態署名(), 学習済み().状態署名())

    def test_低すぎる支持数を拒否(self):
        with self.assertRaises(ValueError):
            HDS学習機械(最小学習経験=1)

    def test_違う実装の保存物を無言で読み込まない(self):
        with tempfile.TemporaryDirectory() as d:
            学習済み().保存する(d)
            p = Path(d) / '境界.json'
            data = json.loads(p.read_text())
            data['実装署名'] = '別版'
            p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                HDS学習機械.読み込む(d)

    def test_入力順の対照でも学習する(self):
        content = 教材()
        content['train'].reverse()
        report, _ = 実験する(content)
        self.assertEqual(report['current'], 1)

    def test_教師がtestを教示できるAPIはない(self):
        t = 教師(公開教材(教材()))
        with self.assertRaises(TypeError):
            t.教示(HDS学習機械(), 'test', 0)

class 継続転用試験(unittest.TestCase):
    def test_別機械へ予測済み権限を移せない(self):
        t, a, b = 教師(公開教材(教材())), HDS学習機械(), HDS学習機械()
        t.評価(a, 'train', 0)
        with self.assertRaises(RuntimeError):
            t.教示(b, 0)

    def test_課題切替後の古い予測を使えない(self):
        t, m = 教師(公開教材(教材())), HDS学習機械()
        t.評価(m, 'train', 0)
        m.新しい課題()
        with self.assertRaises(RuntimeError):
            t.教示(m, 0)

    def test_内部更新後の古い予測を使えない(self):
        t, m = 教師(公開教材(教材())), HDS学習機械()
        t.評価(m, 'train', 0)
        m.観測する(予測要求(((2,),)), ((2,),))
        with self.assertRaises(RuntimeError):
            t.教示(m, 0)

    def test_後続課題へ関係を転用し必要経験が減る(self):
        retained, reset = 学習済み(), HDS学習機械()
        retained.新しい課題()
        self.assertEqual(retained.概況()['全課題保持経験数'], 3)
        for x in (4, 5):
            for m in (retained, reset):
                m.観測する(予測要求(((x,),)), ((x,),))
        self.assertEqual(retained.予測する(予測要求(((9,),))).出力, ((9,),))
        self.assertIsNone(reset.予測する(予測要求(((9,),))).出力)
        self.assertEqual(retained.概況()['全課題保持経験数'], 5)
        reset.観測する(予測要求(((6,),)), ((6,),))
        self.assertEqual(reset.予測する(予測要求(((9,),))).出力, ((9,),))

    def test_同形状でも別関係なら過去関係を隔離(self):
        m = 学習済み()
        m.新しい課題()
        for x in (4, 5):
            m.観測する(予測要求(((x,),)), ((7,),))
        self.assertGreater(m.概況()['転用隔離数'], 0)
        self.assertIsNone(m.予測する(予測要求(((9,),))).出力)
        self.assertTrue(any(c['反証参照'] for c in m._転用候補.values()))

    def test_関係条件が同じ2例は転用支持にならない(self):
        m = 学習済み()
        m.新しい課題()
        for _ in range(2):
            m.観測する(予測要求(((4,),)), ((4,),))
        self.assertIsNone(m.予測する(予測要求(((9,),))).出力)

    def test_定値だけの答えを転用しない(self):
        m = HDS学習機械()
        for x in (1, 2, 3):
            m.観測する(予測要求(((x,),)), ((7,),))
        m.新しい課題()
        self.assertEqual(m.概況()['転用候補数'], 0)

    def test_未確認形状へ転用しない(self):
        m = 学習済み()
        m.新しい課題()
        for x in (4, 5):
            m.観測する(予測要求(((x,),)), ((x,),))
        self.assertIsNone(m.予測する(予測要求(((8, 9),))).出力)

    def test_転用状態の保存復元(self):
        m = 学習済み()
        m.新しい課題()
        for x in (4, 5):
            m.観測する(予測要求(((x,),)), ((x,),))
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d)
            n = HDS学習機械.読み込む(d)
        self.assertEqual(n.状態署名(), m.状態署名())
        self.assertEqual(n.予測する(予測要求(((9,),))).出力, ((9,),))

    def test_転用予測も正解格子に依存しない(self):
        m = 学習済み()
        m.新しい課題()
        for x in (4, 5):
            m.観測する(予測要求(((x,),)), ((x,),))
        a, b = 教材(), 教材()
        b['test'][0]['output'] = [[0]]
        pa, _ = 教師(公開教材(a)).評価(m, 'test', 0)
        pb, _ = 教師(公開教材(b)).評価(m, 'test', 0)
        self.assertEqual(pa, pb)

class 適用範囲回帰試験(unittest.TestCase):
    def test_適用範囲外の観測は反例ではない(self):
        m = 学習済み()
        m.新しい課題()
        m.観測する(予測要求(((1, 2), (3, 4))), ((1, 2), (3, 4)))
        self.assertEqual(m.概況()['転用隔離数'], 0)
        m.新しい課題()
        for x in (4, 5):
            m.観測する(予測要求(((x,),)), ((x,),))
        self.assertEqual(m.予測する(予測要求(((9,),))).出力, ((9,),))

    def test_無関係な値だけ変わっても独立支持としない(self):
        m = HDS学習機械()
        for x in (1, 2, 3):
            m.観測する(予測要求(((x, 0),)), ((x,),))
        m.新しい課題()
        for nuisance in (1, 2):
            m.観測する(予測要求(((4, nuisance),)), ((4,),))
        self.assertIsNone(m.予測する(予測要求(((9, 3),))).出力)

    def test_軽量照会と既存全複製照会が一致する(self):
        m = 学習済み()
        intake = m._入力({'入力': {'行数': 1, '列数': 1, 'セル': {'0,0': 9}}})
        a = copy.deepcopy(m.系.エンジン).照会(intake)
        from copy import copy as shallow_copy
        engine = shallow_copy(m.系.エンジン)
        engine.識別子 = copy.deepcopy(engine.識別子)
        b = engine.照会(intake)
        self.assertEqual(a.予測群, b.予測群)
        self.assertEqual(a.競合群, b.競合群)
        self.assertEqual(a.追加観測要求群, b.追加観測要求群)


class 状態封鎖試験(unittest.TestCase):
    def test_test入力と正解の変更は学習状態を変えない(self):
        a, b = 教材(), 教材()
        b['test'] = [{'input': [[7, 8]], 'output': [[0], [0]]}]
        _, ma = 実験する(a)
        _, mb = 実験する(b)
        self.assertEqual(ma.状態署名(), mb.状態署名())

    def test_監査スナップショットの外部変更は機械を変えない(self):
        m = 学習済み()
        before = m.状態署名()
        snapshot = m.状態()
        snapshot['経験'].clear()
        snapshot['原理履歴'].clear()
        self.assertEqual(m.状態署名(), before)


class 条件別支持試験(unittest.TestCase):
    def test_一条件一観測の偶然対応は採用しない(self):
        s = HDS学習系統()
        for x, y in ((1, 4), (2, 8), (3, 5)):
            s.処理する(外部入力({'条件': x, '結果': y}, '支持probe'))
        self.assertFalse(any(p.関係型 == '決定的対応関係' for p in s.エンジン._有効原理群()))

    def test_条件毎に異なる観測がある対応は採用(self):
        s = HDS学習系統(最大条件数=1)
        for x, y, context in ((1, 4, 0), (2, 8, 1), (1, 4, 2), (2, 8, 3)):
            s.処理する(外部入力({'条件': x, '結果': y, '文脈': context}, '支持probe'))
        self.assertTrue(any(p.関係型 == '決定的対応関係' and p.条件経路群 == (('条件',),)
                            and p.結果経路 == ('結果',) for p in s.エンジン._有効原理群()))

    def test_同一観測を繰り返しても条件別支持を水増ししない(self):
        s = HDS学習系統(最大条件数=1)
        for x, y in ((1, 4), (2, 8), (1, 4), (2, 8)):
            s.処理する(外部入力({'条件': x, '結果': y}, '支持probe'))
        self.assertFalse(any(p.関係型 == '決定的対応関係' for p in s.エンジン._有効原理群()))

    def test_一方の条件だけ反復しても採用しない(self):
        s = HDS学習系統(最大条件数=1)
        for x, y, context in ((1, 4, 0), (2, 8, 1), (1, 4, 2)):
            s.処理する(外部入力({'条件': x, '結果': y, '文脈': context}, '支持probe'))
        self.assertFalse(any(p.関係型 == '決定的対応関係' and p.条件経路群 == (('条件',),)
                            and p.結果経路 == ('結果',) for p in s.エンジン._有効原理群()))


class 支持数回帰試験(unittest.TestCase):
    def test_設定支持数を同一観測で水増しできない(self):
        s = HDS学習系統(最小支持数=5, 最大条件数=1)
        rows = ((1, 4, 0), (2, 8, 1), (1, 4, 2), (2, 8, 3), (1, 4, 0))
        for x, y, context in rows:
            s.処理する(外部入力({'条件': x, '結果': y, '文脈': context}, '支持probe'))
        self.assertFalse(any(p.関係型 == '決定的対応関係' and p.条件経路群 == (('条件',),)
                            and p.結果経路 == ('結果',) for p in s.エンジン._有効原理群()))

    def test_同値関係の全体支持数も水増しできない(self):
        s = HDS学習系統(最小支持数=3, 最大条件数=1)
        for x in (1, 2, 1):
            s.処理する(外部入力({'条件': x, '結果': x}, '支持probe'))
        self.assertFalse(s.エンジン._有効原理群())

if __name__ == '__main__':
    unittest.main()
