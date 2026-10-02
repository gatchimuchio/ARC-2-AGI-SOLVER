"""全modal選択の検査・旧目的関数・panel/HDS全体の保留を確認する。"""
from collections import Counter
from copy import deepcopy
from itertools import product
from pathlib import Path
import random
import sys
import unittest

根=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(根),str(根/'HDS/学習系統/v0.4.2')]
from 接続.ARC2.周期組修復教材 import 周期組修復教材,certify_sequence,guarded_tuple_repair
from 接続.ARC2.既存周期組修復 import repair_tuple_sequence,periodic_panel_tuple_repair
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.HDS接続 import 課題を解く,HDS学習実行系,候補機構を学習,出力格子,観測へ


def frame(sequence,outer=8,inner=9):
    h=len(sequence[0]);w=len(sequence);g=[[outer]*(w+4)for _ in range(h+4)]
    for r in range(1,h+3):
        for c in range(1,w+3):g[r][c]=inner
    for c,values in enumerate(sequence,2):
        for r,v in enumerate(values,2):g[r][c]=v
    return g


def 教材(kind=0):
    clean=([(1,),(3,)]*6 if kind==0 else [(2,5),(5,2),(2,2)]*6)
    noisy=clean[:];noisy[3 if kind==0 else 7]=(4,)if kind==0 else(5,4)
    return {'input':frame(noisy),'output':frame(clean)}


def 教師():return [教材(),教材(1)]


class 周期組修復回帰(unittest.TestCase):
    def test_周期修復とframe保存(self):
        for p in 教師():self.assertEqual(guarded_tuple_repair(p['input'])[0],p['output'])

    def test_最適modal同率は先着で決めない(self):
        seq=[(v,)for v in [0,2,3,4,1,2,3,4,0,2,3,4,1,2,3,4]]
        out,rec=certify_sequence(seq)
        self.assertIsNone(out);self.assertEqual(rec,{'failure':'tied_optimal_modal_tuples','score':(2,2,4)})

    def test_別の唯一最適解で元の答えを置き換えない(self):
        a=(0,0,0);b=(1,0,0);c=(1,1,0);d=(1,0,1);e=(2,2,2);f=(3,3,3);g=(4,4,4)
        seq=[a,e,f,g,b,e,f,g,c,e,f,g,d,e,f,g]
        out,rec=certify_sequence(seq)
        self.assertIsNone(out);self.assertEqual(rec['score'],(3,3,4));self.assertEqual(rec['source_score'],(3,5,4))
        self.assertEqual(rec['failure'],'source_choice_not_unique_optimum')
        self.assertIsNone(guarded_tuple_repair(frame(seq))[0])

    def test_同じ誤差なら元の短い周期を選ぶ(self):
        seq=[(1,),(3,)]*6;seq[3]=(4,)
        out,rec=certify_sequence(seq)
        self.assertEqual(out,[(1,),(3,)]*6);self.assertEqual(rec['score'],(1,1,2))

    def test_元の三分の一budgetを超えた修復を保留(self):
        row=[0,1,1,0,2,0,0,0,0,0,0,0,0,0,1,0,1,2,2,0,0,2,1,2,0,0,1,0,2,1]
        out,rec=guarded_tuple_repair([row])
        self.assertIsNone(out);self.assertEqual(rec['failure'],'panel_exceeds_original_noise_budget')
        self.assertEqual(rec['certificate']['score'],(11,11,4))

    def test_一panelでも未解決なら部分修復しない(self):
        good=[(1,),(3,)]*8;good[3]=(4,)
        bad=[(v,)for v in [0,2,3,4,1,2,3,4,0,2,3,4,1,2,3,4]]
        g=frame(good)+frame(bad)[1:]
        self.assertTrue(periodic_panel_tuple_repair(g)[1])
        self.assertIsNone(guarded_tuple_repair(g)[0])

    def test_形状で決める軸と正方形時columnsを保持(self):
        p=教材(1)
        self.assertEqual(guarded_tuple_repair(transform_grid_by_name(p['input'],'transpose'))[0],transform_grid_by_name(p['output'],'transpose'))
        clean=[tuple([1 if i%2==0 else 3]*12)for i in range(12)];noisy=clean[:];v=list(noisy[5]);v[4]=4;noisy[5]=tuple(v)
        out,rec=guarded_tuple_repair(frame(noisy))
        self.assertEqual(out,frame(clean));self.assertEqual(rec['certificates'][0]['axis'],'columns')

    def test_修復なしと不正格子は候補なし(self):
        for g in (教材()['output'],[],[[1]*31],[[1,2],[1]]):self.assertIsNone(guarded_tuple_repair(g)[0])

    def test_小規模全modal直積列挙と証明器が一致(self):
        rng=random.Random(31)
        for _ in range(64):
            seq=[rng.choice(((0,0),(1,0),(1,1)))for _ in range(9)]
            candidates=[]
            for period in range(1,7):
                modes=[]
                for offset in range(period):
                    counts=Counter(seq[offset::period]);maximum=max(counts.values())
                    modes.append([v for v,n in counts.items()if n==maximum])
                for motif in product(*modes):
                    candidate=tuple(motif[i%period]for i in range(len(seq)))
                    score=(sum(a!=b for a,b in zip(seq,candidate)),sum(x!=y for a,b in zip(seq,candidate)for x,y in zip(a,b)),period)
                    candidates.append((score,candidate))
            score=min(s for s,_ in candidates);outputs={c for s,c in candidates if s==score}
            raw,rec=repair_tuple_sequence(seq);raw_score=(rec['tuple_mismatch'],rec['cell_mismatch'],rec['period'])
            expected=(raw if len(outputs)==1 and tuple(raw)in outputs and raw_score==score and score[0]<=max(1,len(seq)//3)else None)
            self.assertEqual(certify_sequence(seq)[0],expected)

    def test_教師反例と重複を支持へ入れない(self):
        ps=教師();ps[1]['output'][0][0]=1
        self.assertFalse(周期組修復教材(ps).全教師再現)
        p=教材();self.assertFalse(周期組修復教材([p,deepcopy(p)]).全教師再現)

    def test_二教師の最終格子だけを同一HDSへ観測(self):
        p=教材(1);g=transform_grid_by_name(p['input'],'transpose');y=transform_grid_by_name(p['output'],'transpose')
        r=課題を解く({'train':教師(),'test':[{'input':g}]},[])
        self.assertEqual(r['results'][0]['answer'],y);self.assertEqual(r['minimum_support'],2)
        f=next(f for f in r['families']if f['境界']=='ARC周期組修復')
        self.assertEqual(f['現在観測数'],2);self.assertEqual(f['事前観測数'],0);self.assertTrue(f['同値採用'])

    def test_中核既定支持3と後発反例gateは無変更(self):
        v=周期組修復教材(教師());b='周期対照';e=HDS学習実行系()
        r=候補機構を学習(e,{'train':教師()},[],b,v.候補);self.assertFalse(r['同値採用'])
        e=HDS学習実行系(最小支持数=2);候補機構を学習(e,{'train':教師()},[],b,v.候補)
        e.実行(観測へ({'候補':教師()[0]['output'],'出力':[[3]]},b))
        self.assertIsNone(出力格子(e,観測へ({'候補':教師()[1]['output']},b),同値必須=True)['answer'])


if __name__=='__main__':unittest.main()
