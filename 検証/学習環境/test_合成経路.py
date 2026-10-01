import unittest,json,tempfile
from copy import deepcopy
from dataclasses import replace
from 接続.学習環境.HDS接続 import HDS学習機械,署名
from hds学習系統 import HDS学習系統,外部入力


def train(groups,quantity=False):
    s=HDS学習系統(最大条件数=1,関係合成有効=True)
    for source,target,points in groups:
        for a,b in points:
            context={'数量経路群':[(source,),(target,)]} if quantity else {}
            s.処理する(外部入力({source:a,target:b},'compose-fixture',文脈=context))
    return s


def chain():
    return train([('a','b',[(x,x) for x in (1,2,3)]),('b','c',[(x,x) for x in (4,5,6)])])


def query(s,row,quantity=False):
    context={'数量経路群':[(k,) for k in row]} if quantity else {}
    return s.エンジン.照会(s.吸気系.取り込む(外部入力(row,'compose-fixture',文脈=context)))


def values(result,path):return [p.予測値 for p in result.予測群 if p.結果経路==(path,)]


def state(s):
    e=s.エンジン
    return 署名((e.識別子.状態を書き出す(),e.台帳.全取得(),e.状態.履歴(),e._原理履歴))


class 合成経路試験(unittest.TestCase):
    def test_別経験で学んだ二関係を合成(self):
        s=chain();r=query(s,{'a':9})
        self.assertEqual(values(r,'c'),[9])
        p=next(p for p in r.予測群 if p.結果経路==('c',))
        self.assertEqual(p.合成段数,2);self.assertEqual(len(p.導出原理参照群),2)
        self.assertEqual(p.根観測経路群,(('a',),));self.assertEqual(p.依存経路群,(('b',),))

    def test_二段照会はIDを含め状態不変(self):
        s=chain();before=state(s);query(s,{'a':9});query(s,{'a':10})
        self.assertEqual(before,state(s));self.assertEqual(len(s.エンジン._経験群()),6)

    def test_offは直接原理だけを使う(self):
        s=chain();s.エンジン.関係合成有効=False;r=query(s,{'a':9})
        self.assertEqual(values(r,'b'),[9]);self.assertEqual(values(r,'c'),[])

    def test_数量二段の型と外挿境界(self):
        s=train([('a','b',[(x,2*x+1) for x in (1,2,3)]),('b','c',[(x,3*x+1) for x in (4,5,6)])],True)
        self.assertEqual(values(query(s,{'a':2},True),'c'),[16])
        self.assertEqual(values(query(s,{'a':2},False),'c'),[])
        self.assertEqual(values(query(s,{'a':4},True),'c'),[])

    def test_逆関係のcycleが独立した根を潰さない(self):
        s=chain()
        self.assertEqual(values(query(s,{'a':9}),'c'),[9])
        self.assertEqual(values(query(s,{'c':8}),'a'),[8])

    def test_深さ予算は未閉包をHOLD(self):
        s=chain();s.エンジン.最大合成段数=1;r=query(s,{'a':9})
        self.assertEqual(r.予測群,());self.assertTrue(any('深さ上限' in x.理由 for x in r.追加観測要求群))

    def test_候補予算は未閉包をHOLD(self):
        s=chain();s.エンジン.最大合成候補数=1;r=query(s,{'a':9})
        self.assertEqual(r.予測群,());self.assertTrue(any('候補数上限' in x.理由 for x in r.追加観測要求群))

    def test_反証された上流を子孫へ使わない(self):
        s=chain();self.assertEqual(values(query(s,{'a':9}),'c'),[9])
        s.処理する(外部入力({'a':4,'b':99},'compose-fixture'))
        self.assertEqual(values(query(s,{'a':9}),'c'),[])

    def test_構造容器を二段で保持(self):
        s=train([('a','b',[(x,x[::-1]) for x in ([1,2,3],[4,5,6,7],[8,9,10,11,12])]),
                 ('b','c',[(x,x) for x in ([20,21],[22,23,24],[25,26,27,28])])])
        self.assertIn([34,33,32,31,30],values(query(s,{'a':[30,31,32,33,34]}),'c'))

    def test_保存復元は合成設定と予算を保持(self):
        s=chain();s.エンジン.関係合成有効=False;s.エンジン.最大合成段数=2;s.エンジン.最大合成候補数=33
        with tempfile.TemporaryDirectory() as d:
            s.保存する(d+'/hds.json');r=HDS学習系統.読み込む(d+'/hds.json')
        self.assertFalse(r.エンジン.関係合成有効);self.assertEqual(r.エンジン.最大合成段数,2);self.assertEqual(r.エンジン.最大合成候補数,33)


    def arithmetic(self):
        return train([('a','b',[(x,2*x+1) for x in (1,2,3)]),
                      ('d','b',[(x,3*x+1) for x in (1,2,3)]),
                      ('b','c',[(x,2*x+1) for x in (3,5,7)]),
                      ('a','c',[(x,5*x+1) for x in (1,2,3)]),
                      ('c','e',[(x,2*x+1) for x in (7,11,15)])],True)

    def scoped(self,s,row,edges):
        from unittest.mock import patch
        chosen=[p for p in s.エンジン._有効原理群() if (p.条件経路群,p.結果経路) in {(((a,),),(b,)) for a,b in edges}]
        with patch.object(s.エンジン,'_有効原理群',return_value=chosen):return query(s,row,True)

    def test_曖昧な上流の全子孫を保留(self):
        s=self.arithmetic();r=self.scoped(s,{'a':2,'d':2},[('a','b'),('d','b'),('b','c'),('c','e')])
        self.assertEqual(values(r,'b'),[]);self.assertEqual(values(r,'c'),[]);self.assertEqual(values(r,'e'),[])
        self.assertTrue(any(x.結果経路==('b',) for x in r.競合群))

    def test_直接と二段の不一致を優先順位で隠さない(self):
        s=self.arithmetic();r=self.scoped(s,{'a':3},[('a','b'),('b','c'),('a','c')])
        self.assertEqual(values(r,'c'),[])
        self.assertTrue(any(x.結果経路==('c',) for x in r.競合群))

    def test_無効前提の枝だけを落として独立経路を残す(self):
        s=self.arithmetic();r=self.scoped(s,{'a':2,'d':2},[('a','b'),('d','b'),('b','c'),('a','c'),('c','e')])
        self.assertEqual(values(r,'b'),[])
        self.assertEqual(set(values(r,'c')),{11})
        self.assertEqual(set(values(r,'e')),{23})

    def test_同じ結論の独立経路とcycleを区別(self):
        s=chain();r=query(s,{'a':9,'c':9})
        self.assertEqual(set(values(r,'b')),{9})
        self.assertFalse(any('循環' in x.理由 for x in r.追加観測要求群))


    def test_競合循環が無関係な非循環経路を消さない(self):
        s=train([('a','b',[(x,2*x+1) for x in (1,2,3)]),
                 ('a','c',[(x,2*x+2) for x in (1,2,3)]),
                 ('b','c',[(x,x) for x in (3,5,7)]),
                 ('e','f',[(x,x) for x in (1,2,3)])],True)
        r=self.scoped(s,{'a':2,'e':9},[('a','b'),('a','c'),('b','c'),('c','b'),('e','f')])
        self.assertEqual(values(r,'b'),[]);self.assertEqual(values(r,'c'),[])
        self.assertEqual(values(r,'f'),[9])
        self.assertTrue(any('循環' in x.理由 for x in r.追加観測要求群))


    def test_Adapter設定と保存の署名境界(self):
        m=HDS学習機械(関係合成有効=False,最大合成段数=2,最大合成候補数=37);before=m.状態署名()
        with tempfile.TemporaryDirectory() as d:
            m.保存する(d);r=HDS学習機械.読み込む(d)
        self.assertEqual(r.状態署名(),before);self.assertFalse(r.系.エンジン.関係合成有効)
        self.assertEqual(r.系.エンジン.最大合成段数,2);self.assertEqual(r.系.エンジン.最大合成候補数,37)
        r.系.エンジン.関係合成有効=True;self.assertNotEqual(r.状態署名(),before)

    def test_旧7runtimeは新8を拒む(self):
        import subprocess,sys,os
        from pathlib import Path
        old=Path('/workspace/shared/arc2_index_frozen/HDS/学習系統/v0.4.2')
        if not old.exists():self.skipTest('旧runtime snapshotは外部検証fixture')
        with tempfile.TemporaryDirectory() as d:
            path=d+'/hds.json';chain().保存する(path)
            r=subprocess.run([sys.executable,'-c','from hds学習系統 import HDS学習系統; HDS学習系統.読み込む('+repr(path)+')'],cwd=d,env={**os.environ,'PYTHONPATH':str(old)},capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('未対応',r.stderr)

    def test_合成除去CLIの四対照(self):
        import subprocess,sys,hashlib
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);task=root/'fixture.json'
            task.write_text(json.dumps({'train':[{'input':[[x]],'output':[[x]]} for x in (1,2,3)],'test':[{'input':[[9]],'output':[[9]]}]}))
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'教材':[{'ファイル':task.name,'SHA256':hashlib.sha256(task.read_bytes()).hexdigest()}]}))
            repo=Path(__file__).resolve().parents[2]
            r=subprocess.run([sys.executable,str(repo/'道具/数量除去を比較.py'),'--関係族','合成','--教材',str(root),'--固定表',str(manifest),'--出力',str(root/'result'),'--壁時計秒','10','--仮想MiB','384'],capture_output=True,text=True,timeout=30)
            self.assertEqual(r.returncode,0,r.stderr)
            result=json.loads((root/'result/集計.json').read_text());self.assertEqual(list(result['正解数'].values()),[1,1,1,1])
            for mode,row in result['課題別'][0]['比較'].items():
                for stage in ('初期','終了'):
                    self.assertEqual(row[stage]['関係合成有効'],'無効' not in mode)
                    self.assertTrue(row[stage]['数量関係有効']);self.assertTrue(row[stage]['添字関係有効'])
                    self.assertEqual(row[stage]['最大合成段数'],4);self.assertEqual(row[stage]['最大合成候補数'],4096)

    def test_名義同値を数量へ昇格しない(self):
        s=train([('a','b',[(x,x) for x in (1,2,3)])])
        for x in (1,2,3):s.処理する(外部入力({'b':x,'c':2*x+1},'compose-fixture',文脈={'数量経路群':[('b',),('c',)]}))
        r=query(s,{'a':2},True)
        self.assertEqual(values(r,'b'),[2]);self.assertEqual(values(r,'c'),[])


    def test_棄却される組合せも探索予算に数える(self):
        from unittest.mock import patch
        s=chain();s.エンジン.最大合成候補数=5;examined=[]
        def rejected(*choices):
            for i in range(100):
                examined.append(i)
                yield tuple(replace(group[0],前提=((('b',),'cycle'),)) for group in choices)
        with patch('hds学習系統.合成.product',side_effect=rejected):r=query(s,{'a':9})
        self.assertEqual(len(examined),6)
        self.assertEqual(r.予測群,());self.assertTrue(any('候補数上限' in x.理由 for x in r.追加観測要求群))

    def test_単一原理の複数仮説も事実予算に数える(self):
        from unittest.mock import patch
        s=train([('a','b',[(x,x) for x in ([1,2,1],[3,4,3],[5,6,5])])])
        chosen=[p for p in s.エンジン._有効原理群() if p.関係型=='添字アフィン関係' and p.結果経路==('b',)]
        s.エンジン.最大合成候補数=1
        with patch.object(s.エンジン,'_有効原理群',return_value=chosen):r=query(s,{'a':[7,8,9]})
        self.assertEqual(r.予測群,());self.assertTrue(any('事実数上限' in x.理由 for x in r.追加観測要求群))


    def test_推論対象外の観測を生ノードから復活させない(self):
        s=chain();incoming=s.吸気系.取り込む(外部入力({'a':9},'compose-fixture'))
        incoming=replace(incoming,観測群=tuple(replace(o,推論対象=False) for o in incoming.観測群))
        self.assertEqual(s.エンジン.照会(incoming).予測群,())
        s.エンジン.関係合成有効=False
        self.assertEqual(s.エンジン.照会(incoming).予測群,())

    def test_容器派生の射影も推論対象外の葉を運ばない(self):
        s=train([('a','b',[(x,x) for x in ([1,2],[3,4],[5,6])]),
                 ('b','c',[(x,x) for x in ([7,8],[9,10],[11,12])])])
        incoming=s.吸気系.取り込む(外部入力({'a':[20,21]},'compose-fixture'))
        r=s.エンジン.照会(incoming);self.assertIn([20,21],values(r,'c'))
        blocked=replace(incoming,観測群=tuple(replace(o,推論対象=False) if o.推論対象 else o for o in incoming.観測群))
        self.assertEqual(values(s.エンジン.照会(blocked),'c'),[])


    def test_ARCのHOLDにも合成予算理由を残す(self):
        from 接続.学習環境.契約 import 予測要求
        m=HDS学習機械(観測表現='配列階層',最大合成候補数=1,関係合成有効=True)
        for x in (1,3,5):m.観測する(予測要求(((x,x+1),)),((x,x+1),))
        result=m.予測する(予測要求(((8,9),)))
        self.assertEqual(result.状態,'HOLD')
        self.assertTrue(any('上限' in x for x in result.理由))

    def test_返された容器の変更を記憶へ逆流させない(self):
        s=train([('a','b',[(x,x) for x in ([1,2],[3,4],[5,6])]),('b','c',[(x,x) for x in ([7,8],[9,10],[11,12])])])
        before=state(s);r=query(s,{'a':[20,21]})
        for p in r.予測群:
            if isinstance(p.予測値,list):p.予測値[0]=999
        self.assertEqual(before,state(s))
        self.assertIn([20,21],values(query(s,{'a':[20,21]}),'c'))


    def test_循環の子孫にも独立証明があれば保持(self):
        s=train([('a','b',[(x,2*x+1) for x in (1,2,3)]),('a','c',[(x,2*x+2) for x in (1,2,3)]),
                 ('b','c',[(x,x) for x in (3,5,7)]),('d','e',[(x,x) for x in (10,11,12)]),
                 ('b','e',[(x,x) for x in (3,5,7)])],True)
        r=self.scoped(s,{'a':2,'d':10},[('a','b'),('a','c'),('b','c'),('c','b'),('b','e'),('d','e')])
        self.assertEqual(values(r,'b'),[]);self.assertEqual(values(r,'c'),[])
        self.assertEqual(values(r,'e'),[10])
        self.assertEqual({x.結果経路 for x in r.追加観測要求群 if '循環' in x.理由},{('b',),('c',)})

    def test_密な同値グラフの冗長証明で深さを尽くさない(self):
        s=HDS学習系統(最大条件数=1,関係合成有効=True)
        for x in (1,2,3):s.処理する(外部入力({key:x for key in 'abcdef'},'compose-fixture'))
        r=query(s,{'a':9})
        self.assertEqual({p.結果経路:p.予測値 for p in r.予測群},{(x,):9 for x in 'bcdef'})
        self.assertTrue(all(p.合成段数==1 for p in r.予測群))
        self.assertFalse(any('上限' in x.理由 for x in r.追加観測要求群))

    def test_初期設定では合成を明示的に有効化する(self):
        self.assertFalse(HDS学習系統().エンジン.関係合成有効)
        self.assertFalse(HDS学習機械().系.エンジン.関係合成有効)

    def test_少前提でも深い証明は浅い証明を消さない(self):
        from hds学習系統.合成 import 派生事実,証明が包含する
        a=派生事実(('t',),9,False,frozenset(),((('b',),'1'),),(),3)
        b=replace(a,前提=a.前提+((('c',),'2'),),段数=2)
        self.assertFalse(証明が包含する(a,b))
        self.assertTrue(証明が包含する(replace(a,段数=2),b))
        self.assertFalse(証明が包含する(replace(a,値=8,段数=1),b))
        self.assertFalse(証明が包含する(replace(a,数量=True,段数=1),b))


    def test_最小証明化は無効経路と深さ予算ごとの値を保つ(self):
        import random,itertools
        from hds学習系統.合成 import 派生事実,証明が包含する
        rng=random.Random(20261002)
        for _ in range(50):
            proofs=[]
            for i in range(20):
                t=rng.randrange(4);v=rng.randrange(3);q=bool(rng.randrange(2));depth=rng.randrange(1,5)
                deps=tuple(((str(p),),str(rng.randrange(3))) for p in range(4) if p!=t and rng.randrange(2))
                proofs.append(派生事実((str(t),),v,q,frozenset(),deps,(),depth))
            minimal=[x for x in proofs if not any(証明が包含する(y,x) and not 証明が包含する(x,y) for y in proofs)]
            for bits in itertools.product((0,1),repeat=4):
                blocked={(str(i),) for i,b in enumerate(bits) if b}
                for limit in (1,2,3,4):
                    def valueset(rows):return {(x.経路,x.値,x.数量) for x in rows if x.段数<=limit and not any(p in blocked for p,k in x.前提)}
                    self.assertEqual(valueset(proofs),valueset(minimal))

    def test_定値の構造文脈も根のtraceへ残す(self):
        s=train([('a','b',[(x,7) for x in ([1,2],[3,4],[5,6])])])
        r=query(s,{'a':[8,9]})
        p=next(p for p in r.予測群 if p.結果経路==('b',))
        self.assertIn(('a',),p.根観測経路群)

if __name__=='__main__':unittest.main()
