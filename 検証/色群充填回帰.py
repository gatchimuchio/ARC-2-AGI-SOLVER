"""既存候補不在の適用域・色群曖昧性・既存exact-coverの境界対照。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ルート=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ルート),str(ルート/'HDS/学習系統/v0.4.2')]
from 接続.ARC2 import 色群充填 as view
from 接続.ARC2.HDS接続 import 課題を解く
from 接続.ARC2.既存穴充填 import _template_hole_pack_output


def 教材(壁=2,中=3):
    grid=[[0]*9 for _ in range(9)]
    for r,c in ((1,1),(1,3),(3,1),(3,3)):grid[r][c]=壁
    for r,c in ((5,6),(6,5),(6,6),(6,7),(7,6)):grid[r][c]=中
    return {'input':grid,'output':[[壁,中,壁],[中,中,中],[壁,中,壁]]}


class 色群充填回帰(unittest.TestCase):
    def test_断片と複数分割の同一解を既存核で確認(self):
        p=教材();out,detail=view.色群候補(p['input'])
        self.assertEqual(out,p['output'])
        self.assertEqual(len(detail['candidates']),2)
        self.assertEqual(detail['output_count'],1)

    def test_同一HDSの全教師再現と同値gate(self):
        test=教材(7,8)
        result=課題を解く({'train':[教材(),教材(4,5)],'test':[{'input':test['input']}]},[])
        self.assertTrue(result['grouped_packing']['適用可'])
        self.assertEqual(result['results'][0]['answer'],test['output'])
        self.assertTrue(result['results'][0]['equality_admitted'])

    def test_既存候補が誤答や曖昧でも新viewを使わない(self):
        for results in (([],[{'output':[[9]]}]),([{},{}],[]),([{}],[{}])):
            with patch.object(view,'_template_hole_pack_candidates',side_effect=results):
                self.assertFalse(view.色群充填教材([教材(),教材(4,5)]).適用可)

    def test_教師出力とtestは適用域選択に使わない(self):
        before=[教材(),教材(4,5)];after=deepcopy(before)
        after[0]['output']=[[9]];after[1]['output']=[[8,8]]
        with patch.object(view,'_template_hole_pack_candidates',return_value=[]):
            self.assertEqual(view.色群充填教材(before).記録(),view.色群充填教材(after).記録())
        traces=[課題を解く({'train':before,'test':[{'input':教材(a,b)['input']}]},[])['grouped_packing']
                for a,b in ((7,8),(8,9))]
        self.assertEqual(traces[0],traces[1])

    def test_元探索の例外を空候補へ変えない(self):
        for error in (RuntimeError('search'),MemoryError(),TimeoutError()):
            with patch.object(view,'_template_hole_pack_candidates',side_effect=error):
                with self.assertRaises(type(error)):view.色群充填教材([教材()])

    def test_複数の異なる完全出力は保留(self):
        def conflict(template,source,bg):return [[[2 if template[0][0] else 3]]]
        with patch.object(view,'_template_hole_pack_output',side_effect=conflict) as solve:
            self.assertIsNone(view.色群候補(教材()['input'])[0])
            self.assertEqual(solve.call_count,2)

    def test_十二部品上限を越えた解釈を無視しない(self):
        g=[[0]*12 for _ in range(12)]
        for r,c in ((1,1),(1,4),(4,1)):g[r][c]=2
        for r,c in [(r,c)for r in (6,8,10)for c in (0,2,4,6,8,10)][:13]:g[r][c]=3
        with patch.object(view,'_template_hole_pack_output') as solve:
            out,detail=view.色群候補(g)
            self.assertIsNone(out);self.assertEqual(detail['pieces'],13)
            solve.assert_not_called()

    def test_部品を重複使用して穴を埋めない(self):
        template=[[0,0],[0,0]]
        source=[[2,2,0,0,3],[0,0,0,0,3]]
        self.assertEqual(_template_hole_pack_output(template,source,0),[])


if __name__=='__main__':unittest.main()
