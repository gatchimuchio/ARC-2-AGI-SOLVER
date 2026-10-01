"""入力凡例の関係・教師分岐証拠・役割候補合意の対照。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ルート=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ルート),str(ルート/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.HDS接続 import 課題を解く
from 接続.ARC2.凡例穴対応 import 凡例穴教材
from 接続.ARC2.既存凡例穴対応 import legend_hole_prototype_components, render_legend_hole_count_recolorer


def 形(穴):
    if 穴==0:
        return {(r,c) for r in range(2) for c in range(2)}
    幅=2*穴+1
    return {(r,c) for r in range(3) for c in range(幅) if r in (0,2) or c%2==0}


def 教材(ずれ=0, payload=(0,1,2), legend=(0,1), colors=(2,3), marker=5, bg=0):
    x=[[bg]*30 for _ in range(16)]
    for i,(穴,色) in enumerate(zip(legend,colors)):
        for r,c in 形(穴):x[1+r][1+i*12+c]=色
    for i,穴 in enumerate(payload):
        for r,c in 形(穴):x[8+r][1+i*9+c+ずれ]=marker
    y=deepcopy(x);対応=dict(zip(legend,colors))
    for i,穴 in enumerate(payload):
        for r,c in 形(穴):y[8+r][1+i*9+c+ずれ]=対応.get(穴,bg)
    return {'input':x,'output':y}


class 凡例穴対応回帰(unittest.TestCase):
    def test_存在と不在はこの入力の凡例から判定(self):
        train=[教材(),教材(1)];test=教材(payload=(0,1,2),legend=(1,2),colors=(3,4))
        r=課題を解く({'train':train,'test':[{'input':test['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],test['output'])
        self.assertEqual(r['legend_learning']['役割候補群'][0]['消去支持教師数'],2)
        self.assertTrue(r['results'][0]['equality_admitted'])

    def test_凡例色と背景と対象色を固定しない(self):
        train=[教材(marker=7,bg=9,colors=(1,6)),教材(1,marker=7,bg=9,colors=(6,1))]
        test=教材(payload=(0,1),marker=7,bg=9,colors=(4,2))
        r=課題を解く({'train':train,'test':[{'input':test['input']}]},[])
        self.assertEqual(r['results'][0]['answer'],test['output'])

    def test_消去未観測なら新しい不在穴数を消さない(self):
        m=凡例穴教材([教材(payload=(0,1)),教材(1,payload=(0,1))],2)
        self.assertTrue(m.候補群)
        self.assertIsNone(m.候補(教材(payload=(2,))['input'],{})[0])

    def test_重複教師を分岐支持へ水増ししない(self):
        p=教材();m=凡例穴教材([p,deepcopy(p)],2)
        self.assertEqual(m.候補群[0]['消去支持教師数'],1)
        self.assertIsNone(m.候補(p['input'],{})[0])

    def test_課題の支持三設定なら三教師の分岐証拠が必要(self):
        two=凡例穴教材([教材(),教材(1)],3)
        self.assertIsNone(two.候補(教材()['input'],{})[0])
        three=凡例穴教材([教材(),教材(1),教材(2)],3)
        self.assertEqual(three.候補(教材()['input'],{})[0],教材()['output'])

    def test_同じ穴数の異色凡例は競合(self):
        p=教材(legend=(0,0),payload=(0,))
        self.assertIsNone(render_legend_hole_count_recolorer(p['input'],5,0)[0])

    def test_役割代替を第一候補で決めない(self):
        m=凡例穴教材([],2)
        m.候補群=[{'marker':5,'background':b,'消去支持教師数':2} for b in (0,1)]
        def render(grid,marker,bg):return [[bg]],{'legend_removed_component_count':0}
        with patch('接続.ARC2.凡例穴対応.render_legend_hole_count_recolorer',render):
            self.assertIsNone(m.候補([[5]],{})[0])
        with patch('接続.ARC2.凡例穴対応.render_legend_hole_count_recolorer',lambda *a:([[2]],{'legend_removed_component_count':0})):
            self.assertEqual(m.候補([[5]],{})[0],[[2]])

    def test_元の線除外heuristic境界(self):
        for length,expected in ((10,1),(11,0)):
            grid=[[0]*25 for _ in range(5)];grid[2][1:1+length]=[2]*length
            self.assertEqual(len(legend_hole_prototype_components(grid,5,0)),expected)


if __name__=='__main__':unittest.main()
