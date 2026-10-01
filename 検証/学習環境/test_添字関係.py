"""教師fixtureだけが変換を知る。実装は対応するカテゴリから添字係数を推定する。"""
import unittest
import tempfile
from dataclasses import replace
from 接続.学習環境.HDS接続 import HDS学習機械
from hds学習系統 import HDS学習系統, 外部入力
from hds学習系統.添字関係 import 添字関係型, 添字予測, 添字検証, 配列
from hds学習系統.型 import 判定状態


def train(pairs, enabled=True):
    s=HDS学習系統(最大条件数=1,添字関係有効=enabled)
    for a,b in pairs: s.処理する(外部入力({'a':a,'b':b},'index-fixture'))
    return s


def rules(s):
    return [p for p in s.エンジン._有効原理群() if p.関係型==添字関係型 and p.結果経路==('b',)]


def outputs(s,a):
    r=s.エンジン.照会(s.吸気系.取り込む(外部入力({'a':a},'index-fixture')))
    return [p.予測値 for p in r.予測群 if p.結果経路==('b',)]


def reverse_machine():
    return train([(a,a[::-1]) for a in ([1,2,3],[4,5,6,7],[8,9,10,11,12])])


class 添字関係試験(unittest.TestCase):
    def test_三経験から未見長と値へ(self):
        s=reverse_machine()
        self.assertEqual(outputs(s,[20,21,22,23,24,25]),[[25,24,23,22,21,20]])
        self.assertEqual(len(rules(s)),1)

    def test_二次元の未見形状へ(self):
        pairs=[]
        for k,(h,w) in enumerate(((2,3),(3,5),(5,4))):
            a=[[100*k+r*w+c for c in range(w)] for r in range(h)]
            pairs.append((a,[list(row) for row in zip(*a)]))
        s=train(pairs);a=[[400+r*6+c for c in range(6)] for r in range(4)]
        self.assertIn([list(row) for row in zip(*a)],outputs(s,a))

    def test_反復値の曖昧性を保持し追加経験で解く(self):
        s=train([(a,a) for a in ([1,2,1],[3,4,3],[5,6,5])])
        self.assertEqual(len(rules(s)[0].対応値表),2)
        self.assertEqual(len(添字予測(rules(s)[0],[7,8,9])),2)
        self.assertEqual(outputs(s,[7,8,9]),[]) # HDSが不一致仮説をHOLDする
        s.処理する(外部入力({'a':[7,8,9],'b':[9,8,7]},'index-fixture'))
        self.assertEqual(len(rules(s)[0].対応値表),1)
        self.assertEqual(outputs(s,[10,11,12]),[[12,11,10]])
        # 固定長経験だけでは旧スカラー位置関係と未見長で競合し、HOLDが正しい。
        self.assertEqual(outputs(s,[10,11,12,13]),[])
        s.処理する(外部入力({'a':[10,11,12,13],'b':[13,12,11,10]},'index-fixture'))
        self.assertEqual(outputs(s,[20,21,22,23,24]),[[24,23,22,21,20]])

    def test_未知値を含む既知矛盾は隔離(self):
        s=reverse_machine()
        s.処理する(外部入力({'a':[1,99,3],'b':[3,99,9]},'index-fixture'))
        self.assertEqual(rules(s),[])
        self.assertTrue(any(p.関係型==添字関係型 for p in s.エンジン._係争中原理群()))

    def test_非全単射は学習しない(self):
        s=train([(a,[a[0]]*len(a)) for a in ([1,2,3],[4,5,6],[7,8,9])])
        self.assertEqual(rules(s),[])

    def test_重複経験は三経験へ水増ししない(self):
        s=train([([1,2,3],[3,2,1])]*5)
        self.assertEqual(rules(s),[])

    def test_葉型と容器型の範囲(self):
        s=reverse_machine();p=rules(s)[0]
        for raw in (['a','b'],(1,2,3),[[1,2],[3,4]]):
            with self.assertRaises(ValueError):添字予測(p,raw)

    def test_不整形と非配列を拒む(self):
        for raw in ([[1,2],[3]],{'0':1,'1':2},[1],[[[1,2],[3,4]],[[5,6],[7,8]]]):
            with self.assertRaises(ValueError):配列(raw)

    def test_無関係なmetadataを解析しない(self):
        s=reverse_machine()
        s.処理する(外部入力({'a':[20,21,22],'b':[22,21,20],'metadata':{99}},'index-fixture'))
        self.assertTrue(rules(s))

    def test_無効化と保存復元(self):
        s=reverse_machine();s.エンジン.添字関係有効=False
        self.assertEqual(rules(s),[])
        self.assertEqual(outputs(s,[20,21,22,23]),[])
        with tempfile.TemporaryDirectory() as d:
            s.保存する(d+'/state.json');t=HDS学習系統.読み込む(d+'/state.json')
        self.assertFalse(t.エンジン.添字関係有効)
        t.エンジン.添字関係有効=True
        self.assertEqual(outputs(t,[20,21,22,23]),[[23,22,21,20]])

    def test_無効化中も共同反例を捨てない(self):
        s=train([(a,a) for a in ([1,2,1],[3,4,3],[5,6,5])])
        s.エンジン.添字関係有効=False
        for a,b in (([7,8,9],[9,8,7]),([10,11,12],[10,11,12])):
            s.処理する(外部入力({'a':a,'b':b},'index-fixture'))
        s.エンジン.添字関係有効=True
        self.assertEqual(rules(s),[])


    def test_曖昧候補の恣意的間引きを検証が拒む(self):
        s=train([(a,a) for a in ([1,2,1],[3,4,3],[5,6,5])]);p=rules(s)[0]
        forged=replace(p,対応表=p.対応表[:1],対応値表=p.対応値表[:1],適用範囲={**p.適用範囲,'仮説数':1})
        self.assertNotEqual(添字検証(forged,s.エンジン._経験群(),3).判定,判定状態.適合)

    def test_懐疑の対象外から生成しない(self):
        from hds学習系統.型 import 懐疑記録
        s=reverse_machine()
        skepticism=懐疑記録('s','e','index-fixture','probe',(),'fixture',(('focus',),),('条件関係生成',),'fixture')
        ids=iter(range(1000))
        candidates=s.エンジン.推論器.導出する(s.エンジン._経験群(),(skepticism,),3,lambda kind:kind+str(next(ids)),())
        self.assertFalse(any(p.関係型==添字関係型 for p in candidates))

    def test_キー改名と辞書順序で添字意味を変えない(self):
        s=HDS学習系統(最大条件数=1)
        for a in ([1,2,3],[4,5,6,7],[8,9,10,11,12]):
            s.処理する(外部入力({'後':a[::-1],'前':a},'index-fixture'))
        r=s.エンジン.照会(s.吸気系.取り込む(外部入力({'前':[20,21,22,23]},'index-fixture')))
        self.assertIn([23,22,21,20],[p.予測値 for p in r.予測群 if p.結果経路==('後',)])

    def test_現行保存形式を旧数量runtimeは拒む(self):
        import subprocess,sys,os
        from pathlib import Path
        old=Path('/workspace/shared/arc2_eed_frozen/HDS/学習系統/v0.4.2')
        if not old.exists():self.skipTest('旧6runtime fixture未配布。形式番号契約は別試験')
        with tempfile.TemporaryDirectory() as d:
            path=d+'/state.json';reverse_machine().保存する(path)
            result=subprocess.run([sys.executable,'-c','from hds学習系統 import HDS学習系統; HDS学習系統.読み込む('+repr(path)+')'],env={**os.environ,'PYTHONPATH':str(old)},cwd=d,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('ValueError',result.stderr)

    def test_ARC配列Frameから未見矩形へ(self):
        from 接続.学習環境.契約 import 予測要求
        m=HDS学習機械(64,観測表現='配列階層')
        for k,(h,w) in enumerate(((2,3),(3,5),(5,4))):
            a=tuple(tuple((k*3+r*w+c)%10 for c in range(w)) for r in range(h))
            m.観測する(予測要求(a),tuple(zip(*a)))
        a=tuple(tuple((4+r*6+c)%10 for c in range(6)) for r in range(4));before=m.状態署名()
        self.assertEqual(m.予測する(予測要求(a)).出力,tuple(zip(*a)))
        self.assertEqual(m.状態署名(),before)
        m.系.エンジン.添字関係有効=False
        self.assertIsNone(m.予測する(予測要求(a)).出力)

    def test_最終正解変更は学習状態を変えない(self):
        from 接続.学習環境.実験 import 実験する
        tasks={'train':[],'test':[{'input':[[1,2],[3,4]],'output':[[3,1],[4,2]]}]}
        for k,(h,w) in enumerate(((2,3),(3,5),(5,4))):
            a=[[(k*3+r*w+c)%10 for c in range(w)] for r in range(h)]
            tasks['train'].append({'input':a,'output':[list(row) for row in zip(*a)]})
        first=HDS学習機械(64,観測表現='配列階層');second=HDS学習機械(64,観測表現='配列階層')
        実験する(tasks,64,学習機械=first)
        tasks['test']=[{'input':[[9,8,7],[6,5,4]],'output':[[0]]}]
        実験する(tasks,64,学習機械=second)
        self.assertEqual(first.状態署名(),second.状態署名())


    def test_添字除去CLIは同じFrameで四対照を保存(self):
        import json,hashlib,subprocess,sys
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);task=root/'fixture.json'
            task.write_text(json.dumps({'train':[{'input':[[x]],'output':[[x]]} for x in (1,2,3)],'test':[{'input':[[9]],'output':[[9]]}]}))
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'教材':[{'ファイル':task.name,'SHA256':hashlib.sha256(task.read_bytes()).hexdigest()}]}))
            repo=Path(__file__).resolve().parents[2]
            result=subprocess.run([sys.executable,str(repo/'道具/数量除去を比較.py'),'--関係族','添字','--教材',str(root),
                '--固定表',str(manifest),'--出力',str(root/'result'),'--壁時計秒','10','--仮想MiB','384'],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((root/'result'/'集計.json').read_text())
            self.assertEqual(report['除去関係族'],'添字')
            self.assertEqual(list(report['正解数'].values()),[1,1,1,1])
            for mode,row in report['課題別'][0]['比較'].items():
                for stage in ('初期','終了'):
                    self.assertEqual(row[stage]['添字関係有効'],'無効' not in mode)
                    self.assertTrue(row[stage]['数量関係有効'])
                    self.assertEqual(row[stage]['観測表現'],'配列階層')

    def test_Adapter設定と状態の保存(self):
        m=HDS学習機械(観測表現='配列階層',添字関係有効=False);before=m.状態署名()
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d);r=HDS学習機械.読み込む(d)
        self.assertFalse(r.系.エンジン.添字関係有効)
        self.assertEqual(before,r.状態署名())
        r.系.エンジン.添字関係有効=True
        self.assertNotEqual(before,r.状態署名())


    def test_審査済み除外は当該系譜と懐疑範囲だけ(self):
        from hds学習系統.型 import 懐疑記録
        s=reverse_machine()
        s.処理する(外部入力({'a':[20,21,22],'b':[0,0,0]},'index-fixture'))
        p=next(p for p in s.エンジン._係争中原理群() if p.関係型==添字関係型 and p.結果経路==('b',))
        s.係争を解決する(p.原理識別子,'復帰','fixtureで当該経験を明示除外','HDS')
        s.処理する(外部入力({'a':[30,31,32,33],'b':[33,32,31,30]},'index-fixture'))
        active=rules(s)[0]
        self.assertTrue(active.除外反証参照群)
        self.assertEqual(outputs(s,[40,41,42,43,44]),[[44,43,42,41,40]])
        self.assertFalse(any(p.関係型==添字関係型 and p.結果経路==('a',) for p in s.エンジン._有効原理群()))
        skepticism=懐疑記録('s','e','index-fixture','probe',(),'fixture',(('focus',),),('条件関係生成',),'fixture')
        ids=iter(range(1000))
        candidates=s.エンジン.推論器.導出する(s.エンジン._経験群(),(skepticism,),3,lambda kind:kind+str(next(ids)),s.エンジン._有効原理群())
        self.assertFalse(any(p.関係型==添字関係型 for p in candidates))

if __name__=='__main__':unittest.main()
