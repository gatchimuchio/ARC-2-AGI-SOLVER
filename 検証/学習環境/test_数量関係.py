import json
import hashlib
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from 接続.学習環境.HDS接続 import HDS学習機械
from hds学習系統 import HDS学習系統, 外部入力
from hds学習系統.数量関係 import 数量関係型, 数量型, 数量検証, 数量を計算する, 数量候補
from hds学習系統.型 import 判定状態


def incoming(row, quantities=('a','b')):
    return 外部入力(row,'quantity-probe',文脈={'数量経路群':[(x,) for x in quantities]})


def train(points, quantities=('a','b')):
    s=HDS学習系統(最大条件数=1)
    for row in points:
        s.処理する(incoming(row,quantities))
    return s


def predict(s,row,quantities=('a','b')):
    return s.エンジン.照会(s.吸気系.取り込む(incoming(row,quantities)))


def numbers(s):
    return [p for p in s.エンジン._有効原理群() if p.関係型==数量関係型]


class 数量関係試験(unittest.TestCase):
    def linear(self):
        return train([{'a':x,'b':2*x+1} for x in (1,2,3)])

    def test_三つの異なる入力から未見数量へ(self):
        s=self.linear();r=predict(s,{'a':4})
        self.assertIn(9,[p.予測値 for p in r.予測群 if p.結果経路==('b',)])
        p=next(p for p in numbers(s) if p.結果経路==('b',))
        self.assertEqual(p.適用範囲['傾き'],(2,1))
        self.assertEqual(p.適用範囲['切片'],(1,1))

    def test_新数量経験で観測範囲を改訂する(self):
        s=self.linear()
        for x in (4,5,6):
            s.処理する(incoming({'a':x,'b':2*x+1}))
        p=next(p for p in numbers(s) if p.結果経路==('b',))
        self.assertEqual(p.適用範囲['観測最大'],6)
        self.assertEqual(len(p.根拠参照群),6)
        self.assertIn(15,[p.予測値 for p in predict(s,{'a':7}).予測群 if p.結果経路==('b',)])
        revision=p.版
        s.処理する(incoming({'a':6,'b':13}))
        self.assertEqual(next(p for p in numbers(s) if p.結果経路==('b',)).版,revision)

    def test_数値に見えるカテゴリから算術関係を作らない(self):
        s=train([{'a':x,'b':2*x+1} for x in (1,2,3)],())
        self.assertEqual(numbers(s),[])
        self.assertEqual([p for p in predict(s,{'a':4},()).予測群 if p.結果経路==('b',)],[])

    def test_数量とカテゴリの混合を算術にしない(self):
        s=train([{'a':x,'b':2*x+1} for x in (1,2,3)],('a',))
        self.assertEqual(numbers(s),[])

    def test_二点では保留(self):
        self.assertEqual(numbers(train([{'a':x,'b':2*x+1} for x in (1,2)])),[])

    def test_文脈だけの変化は三入力点にならない(self):
        s=train([{'a':x,'b':2*x+1,'context':k} for k,x in enumerate((1,2,1,2,1,2))])
        self.assertEqual(numbers(s),[])

    def test_非線形観測は一次に押し込めない(self):
        self.assertEqual(numbers(train([{'a':x,'b':x*x} for x in (1,2,3)])),[])

    def test_異なる係数の反例で隔離(self):
        s=self.linear();s.処理する(incoming({'a':4,'b':99}))
        self.assertEqual(numbers(s),[])
        self.assertTrue(any(p.関係型==数量関係型 for p in s.エンジン._係争中原理群()))

    def test_審査済み除外は当該数量系譜だけで再学習(self):
        s=self.linear()
        s.処理する(incoming({'a':4,'b':99}))
        disputed=next(p for p in s.エンジン._係争中原理群() if p.関係型==数量関係型 and p.結果経路==('b',))
        s.係争を解決する(disputed.原理識別子,'復帰','fixtureで明示審査した反例だけ除外','HDS')
        for x in (5,6):
            s.処理する(incoming({'a':x,'b':2*x+1}))
        p=next(p for p in numbers(s) if p.結果経路==('b',))
        self.assertEqual(p.適用範囲['観測最大'],6)
        self.assertTrue(p.除外反証参照群)
        self.assertIn(15,[p.予測値 for p in predict(s,{'a':7}).予測群 if p.結果経路==('b',)])
        self.assertFalse(any(p.結果経路==('a',) for p in numbers(s)))

    def test_審査済み継続も現在の懐疑権限を越えない(self):
        from hds学習系統.型 import 懐疑記録
        s=self.linear();s.処理する(incoming({'a':4,'b':99}))
        disputed=next(p for p in s.エンジン._係争中原理群() if p.関係型==数量関係型 and p.結果経路==('b',))
        s.係争を解決する(disputed.原理識別子,'復帰','fixture exclusion','HDS')
        skepticism=懐疑記録('s','e','probe','probe',(),'fixture',(('focus',),),('条件関係生成',),'fixture')
        ids=iter(range(100))
        candidates=s.エンジン.推論器.導出する(s.エンジン._経験群(),(skepticism,),3,lambda _:str(next(ids)),s.エンジン._有効原理群())
        self.assertFalse(any(c.関係型==数量関係型 for c in candidates))

    def test_外挿上限外でも観測済み反例を隠さない(self):
        s=self.linear();s.処理する(incoming({'a':100,'b':999}))
        self.assertEqual(numbers(s),[])

    def test_外挿は観測幅一つまで(self):
        s=self.linear();r=predict(s,{'a':100})
        self.assertEqual([p for p in r.予測群 if p.結果経路==('b',)],[])

    def test_分数係数は厳密に保持し丸めない(self):
        s=train([{'a':x,'b':x//2} for x in (2,4,6)])
        self.assertIn(4,[p.予測値 for p in predict(s,{'a':8}).予測群 if p.結果経路==('b',)])
        self.assertEqual([p for p in predict(s,{'a':7}).予測群 if p.結果経路==('b',)],[])

    def test_負の予測数量は保留(self):
        s=train([{'a':x,'b':5-x} for x in (1,3,5)])
        self.assertEqual([p for p in predict(s,{'a':7}).予測群 if p.結果経路==('b',)],[])

    def test_不正な数量型を吸気で拒否(self):
        for value in (True,-1,1.0,'2'):
            with self.subTest(value=value),self.assertRaises(TypeError):
                HDS学習系統().処理する(incoming({'a':value,'b':3}))

    def test_キー名の変更で意味を変えない(self):
        s=train([{'長さ':x,'結果':2*x+1} for x in (1,2,3)],('長さ','結果'))
        self.assertIn(9,[p.予測値 for p in predict(s,{'長さ':4},('長さ','結果')).予測群 if p.結果経路==('結果',)])

    def test_懐疑が許可しない経路を生成しない(self):
        s=self.linear();counter=iter(range(100))
        self.assertEqual(数量候補(s.エンジン._経験群(),(),3,lambda _:str(next(counter)),{('a',)}),())

    def test_宣言係数の改変は検証器が拒否(self):
        s=self.linear();p=next(p for p in numbers(s) if p.結果経路==('b',))
        p=replace(p,適用範囲={**p.適用範囲,'傾き':(9,1)})
        self.assertEqual(数量検証(p,s.エンジン._経験群(),3).判定,判定状態.失敗)

    def test_宣言外挿幅の拡張は検証器が許可しない(self):
        s=self.linear();p=next(p for p in numbers(s) if p.結果経路==('b',))
        p=replace(p,適用範囲={**p.適用範囲,'予測上限':999})
        self.assertEqual(数量検証(p,s.エンジン._経験群(),3).判定,判定状態.断定保留)

    def test_二つの支持された説明が未知入力で割れたら競合(self):
        s=train([{'a':x,'other':2*x,'b':2*x+1} for x in (1,2,3)],('a','other','b'))
        r=predict(s,{'a':4,'other':10},('a','other','b'))
        self.assertTrue(any(c.結果経路==('b',) for c in r.競合群))
        self.assertEqual([p for p in r.予測群 if p.結果経路==('b',)],[])

    def test_数量型と係数は保存復元する(self):
        s=self.linear()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';s.保存する(p);restored=HDS学習系統.読み込む(p)
        self.assertIn(9,[p.予測値 for p in predict(restored,{'a':4}).予測群 if p.結果経路==('b',)])

    def test_学習前後と記憶除去の因果対照(self):
        s=HDS学習系統(最大条件数=1)
        self.assertEqual([p for p in predict(s,{'a':4}).予測群 if p.結果経路==('b',)],[])
        for x in (1,2,3):
            s.処理する(incoming({'a':x,'b':2*x+1}))
        self.assertIn(9,[p.予測値 for p in predict(s,{'a':4}).予測群 if p.結果経路==('b',)])
        erased=HDS学習系統(最大条件数=1)
        self.assertEqual([p for p in predict(erased,{'a':4}).予測群 if p.結果経路==('b',)],[])

    def test_数量無効でも観測型を変えず生成を止める(self):
        s=HDS学習系統(最大条件数=1,数量関係有効=False)
        for x in (1,2,3):s.処理する(incoming({'a':x,'b':2*x+1}))
        self.assertEqual(numbers(s),[])
        self.assertTrue(all(o.値型==数量型 for e in s.エンジン._経験群() for o in e.観測群 if o.推論対象))
        self.assertEqual([p for p in predict(s,{'a':4}).予測群 if p.結果経路==('b',)],[])

    def test_数量無効は既存原理の使用も止め設定を保存(self):
        s=self.linear();s.エンジン.数量関係有効=False
        self.assertTrue(any(p.関係型==数量関係型 for p in s.エンジン._現行原理群()))
        self.assertEqual(numbers(s),[])
        self.assertEqual([p for p in predict(s,{'a':4}).予測群 if p.結果経路==('b',)],[])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';s.保存する(path);s=HDS学習系統.読み込む(path)
        self.assertFalse(s.エンジン.数量関係有効)
        self.assertEqual([p for p in predict(s,{'a':4}).予測群 if p.結果経路==('b',)],[])

    def test_Adapter数量除去設定は状態署名と保存に含む(self):
        m=HDS学習機械(観測表現='配列階層',数量関係有効=False)
        before=m.状態署名()
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d);restored=HDS学習機械.読み込む(d)
        self.assertFalse(restored.系.エンジン.数量関係有効)
        self.assertEqual(before,restored.状態署名())
        restored.系.エンジン.数量関係有効=True
        self.assertNotEqual(before,restored.状態署名())

    def test_除去比較CLIは同じFrameで四対照を保存(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);task=root/'fixture.json'
            task.write_text(json.dumps({'train':[{'input':[[x]],'output':[[x]]} for x in (1,2,3)],'test':[{'input':[[9]],'output':[[9]]}]}))
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'教材':[{'ファイル':task.name,'SHA256':hashlib.sha256(task.read_bytes()).hexdigest()}]}))
            repo=Path(__file__).resolve().parents[2]
            result=subprocess.run([sys.executable,str(repo/'道具/数量除去を比較.py'),'--教材',str(root),
                '--固定表',str(manifest),'--出力',str(root/'result'),'--壁時計秒','10','--仮想MiB','384'],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((root/'result'/'集計.json').read_text())
            self.assertEqual(report['評価例数'],1)
            self.assertEqual(list(report['正解数'].values()),[1,1,1,1])
            for mode,row in report['課題別'][0]['比較'].items():
                self.assertEqual(row['初期']['観測表現'],'配列階層')
                self.assertEqual(row['終了']['数量関係有効'],mode.startswith('数量有効'))

    def test_無効数量原理で別候補の採用を抑止しない(self):
        s=self.linear();p=next(p for p in numbers(s) if p.結果経路==('b',))
        candidate=replace(p,条件経路群=(('a',),('context',)))
        self.assertTrue(s.エンジン._より単純な同等原理がある(candidate))
        s.エンジン.数量関係有効=False
        self.assertFalse(s.エンジン._より単純な同等原理がある(candidate))
        self.assertTrue(any(p.関係型==数量関係型 for p in s.エンジン._現行原理群()))

    def test_無効中も反証履歴は保持し再有効化で誤復帰しない(self):
        s=self.linear();s.エンジン.数量関係有効=False
        s.処理する(incoming({'a':4,'b':99}))
        self.assertEqual(numbers(s),[])
        self.assertEqual([p for p in s.エンジン._係争中原理群() if p.関係型==数量関係型],[])
        s.エンジン.数量関係有効=True
        self.assertEqual(numbers(s),[])
        self.assertTrue(any(p.関係型==数量関係型 for p in s.エンジン._係争中原理群()))

    def test_ARC色と寸法の役割は分離(self):
        facts=HDS学習機械(観測表現='配列階層')._入力({'入力':{'行数':1,'列数':2,'セル':[[1,2]]}}).観測群
        self.assertTrue(all(o.値型==数量型 for o in facts if o.経路 in {('入力','行数'),('入力','列数')}))
        self.assertTrue(all(o.値型!=数量型 for o in facts if o.経路[:2]==('入力','セル')))

if __name__=='__main__':
    unittest.main()
