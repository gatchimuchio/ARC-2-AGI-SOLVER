"""過去支持と現在再確認を別記録で保持する中核回帰。"""
import unittest
from copy import deepcopy
from dataclasses import asdict
from 接続.学習環境.HDS接続 import HDS学習機械
from hds学習系統 import HDS学習系統, 外部入力
from hds学習系統.再利用 import 候補群

CONTRACT={'版':1,'表現':'typed-sequence','数量単位':[],
          '名義宣言':[{'経路':[x],'容器型':['list'],'葉型':['int'],'値域':None} for x in ('a','b')]}
def inp(a,b=None,scope='new',contract=CONTRACT):
    data={'a':a}
    if b is not None:data['b']=b
    return 外部入力(data,scope,文脈={'一般再利用契約':deepcopy(contract)} if contract is not None else {})
def trained():
    s=HDS学習系統(最大条件数=1,一般再利用有効=True)
    for a in ([1,2,3],[4,5,6,7],[8,9,10,11,12]):s.処理する(inp(a,a[::-1],'old'))
    p=next(p for p in s.エンジン._有効原理群() if p.関係型=='添字アフィン関係' and p.結果経路==('b',))
    ident=s.エンジン.一般再利用候補を登録する(p.原理識別子,CONTRACT)
    assert ident
    return s,ident
def query(s,a,contract=CONTRACT):
    return s.エンジン.照会(s.吸気系.取り込む(inp(a,contract=contract)))
def outputs(r):return [p.予測値 for p in r.予測群 if p.結果経路==('b',)]
class 一般再利用試験(unittest.TestCase):
    def test_過去三現在二で未見長へ純粋照会(self):
        s,ident=trained();before=deepcopy(候補群(s.エンジン))
        fresh=HDS学習系統(最大条件数=1,一般再利用有効=True)
        for a in ([20,21,22,23],[30,31,32,33,34]):
            s.処理する(inp(a,a[::-1]));fresh.処理する(inp(a,a[::-1]))
        state=deepcopy(s.エンジン.__dict__)
        r=query(s,[40,41,42,43,44,45])
        self.assertEqual(outputs(r),[[45,44,43,42,41,40]])
        self.assertEqual(outputs(query(fresh,[40,41,42,43,44,45])),[])
        self.assertEqual(候補群(s.エンジン),before)
        self.assertEqual(len(s.エンジン._経験群()),5)
        self.assertEqual(s.エンジン.台帳.全取得(),state['台帳'].全取得())
        self.assertEqual(s.エンジン.識別子.__dict__,state['識別子'].__dict__)
        self.assertEqual(r.追跡情報['一般再利用参照'],(ident,))
    def test_現在だけで曖昧なら過去で消さない(self):
        s,_=trained()
        for a in ([20,21,20],[30,31,30]):s.処理する(inp(a,a))
        r=query(s,[40,41,42]);self.assertEqual(outputs(r),[]);self.assertTrue(r.競合群)
    def test_契約欠落変更を後付けで救済しない(self):
        for contract in (None,{**CONTRACT,'表現':'other'}):
            s,ident=trained()
            for a in ([20,21,22],[30,31,32]):s.処理する(inp(a,a[::-1],contract=contract))
            self.assertEqual(outputs(query(s,[40,41,42])),[])
            self.assertEqual(s.エンジン.一般再利用を検証する(ident,'new',CONTRACT)['状態'],'HOLD')
    def test_反例記録は保持(self):
        s,ident=trained()
        s.処理する(inp([20,21,22],[20,21,22]))
        r=s.エンジン.一般再利用を検証する(ident,'new',CONTRACT)
        self.assertEqual(r['状態'],'QUARANTINE');self.assertTrue(r['反証参照'])
        self.assertEqual(outputs(query(s,[40,41,42])),[])
    def test_無効化(self):
        s,_=trained()
        for a in ([20,21,22],[30,31,32]):s.処理する(inp(a,a[::-1]))
        s.エンジン.一般再利用有効=False
        self.assertEqual(outputs(query(s,[40,41,42])),[])
    def test_保存往復と旧設定既定無効(self):
        import tempfile,json
        from pathlib import Path
        from hds学習系統 import 永続化
        s,_=trained()
        for a in ([20,21,22],[30,31,32]):s.処理する(inp(a,a[::-1]))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.json';s.保存する(p)
            restored=HDS学習系統.読み込む(p)
            self.assertEqual(outputs(query(restored,[40,41,42])),[[42,41,40]])
            self.assertEqual(候補群(s.エンジン),候補群(restored.エンジン))
            decoded=永続化._復号(json.loads(p.read_text()))
            self.assertEqual(decoded['形式版'],9)
            decoded['形式版']=8;decoded.pop('一般再利用有効')
            p.write_text(json.dumps(永続化._符号化(decoded)))
            self.assertFalse(HDS学習系統.読み込む(p).エンジン.一般再利用有効)

    def test_数量単位と支配値の独立性(self):
        contract={'版':1,'表現':'quantities','数量単位':[{'経路':[x],'単位':'cells'} for x in ('a','b')],'名義宣言':[]}
        def data(x,scope,noise=0,unit=None):
            c=deepcopy(contract)
            if unit:c['数量単位'][0]['単位']=unit
            return 外部入力({'a':x,'b':2*x+1,'noise':noise},scope,文脈={'数量経路群':[('a',),('b',)],'一般再利用契約':c})
        s=HDS学習系統(最大条件数=1,一般再利用有効=True)
        for x in (1,2,3):s.処理する(data(x,'old'))
        p=next(p for p in s.エンジン._有効原理群() if p.関係型=='数量一次関係' and p.結果経路==('b',))
        ident=s.エンジン.一般再利用候補を登録する(p.原理識別子,contract)
        self.assertTrue(ident)
        s.処理する(data(4,'new',1));s.処理する(data(4,'new',2))
        self.assertEqual(s.エンジン.一般再利用を検証する(ident,'new',contract)['状態'],'HOLD')
        s.処理する(data(5,'new',3))
        r=s.エンジン.一般再利用を検証する(ident,'new',contract)
        self.assertEqual(r['状態'],'ADMIT')
        q=外部入力({'a':6},'new',文脈={'数量経路群':[('a',)],'一般再利用契約':contract})
        self.assertIn(13,outputs(s.エンジン.照会(s.吸気系.取り込む(q))))
        s.処理する(data(6,'new',unit='seconds'))
        self.assertEqual(s.エンジン.一般再利用を検証する(ident,'new',contract)['状態'],'HOLD')

    def test_異なるscopeで再確認しても過去反例を消さない(self):
        s,ident=trained();s.処理する(inp([20,21,22],[20,21,22]))
        old=deepcopy(s.エンジン.台帳.取得('一般再利用検証'))
        for a in ([30,31,32],[40,41,42]):s.処理する(inp(a,a[::-1],'third'))
        self.assertEqual(s.エンジン.一般再利用を検証する(ident,'third',CONTRACT)['状態'],'ADMIT')
        self.assertEqual(s.エンジン.一般再利用を検証する(ident,'new',CONTRACT)['状態'],'QUARANTINE')
        self.assertEqual(s.エンジン.台帳.取得('一般再利用検証')[:len(old)],old)

    def test_元原理の反証で再利用権威も失効(self):
        s,ident=trained()
        for a in ([20,21,22],[30,31,32]):s.処理する(inp(a,a[::-1]))
        s.処理する(inp([50,51,52],[50,51,52],'old'))
        self.assertEqual(outputs(query(s,[40,41,42])),[])
        self.assertEqual(s.エンジン.一般再利用を検証する(ident,'new',CONTRACT)['状態'],'HOLD')

    def test_ARC未見形状の再利用と初期化対照(self):
        from 接続.学習環境.契約 import 予測要求
        import tempfile
        from pathlib import Path
        def grid(h,w,k):return [[(r*w+c+k)%10 for c in range(w)] for r in range(h)]
        m=HDS学習機械(最大セル数=64,観測表現='配列階層',一般再利用有効=True)
        fresh=HDS学習機械(最大セル数=64,観測表現='配列階層',一般再利用有効=True)
        for h,w,k in [(2,3,0),(3,4,1),(4,5,2)]:
            a=grid(h,w,k);m.観測する(予測要求(a),list(map(list,zip(*a))))
        m.新しい課題()
        for h,w,k in [(2,4,5),(3,5,6)]:
            a=grid(h,w,k)
            for learner in (m,fresh):learner.観測する(予測要求(a),list(map(list,zip(*a))))
        a=grid(4,6,7);before=m.状態署名()
        self.assertEqual(m.予測する(予測要求(a)).出力,tuple(zip(*a)))
        self.assertIsNone(fresh.予測する(予測要求(a)).出力)
        self.assertEqual(m.状態署名(),before)
        with tempfile.TemporaryDirectory() as d:
            m.保存する(Path(d)/'saved');loaded=HDS学習機械.読み込む(Path(d)/'saved')
        self.assertEqual(loaded.状態署名(),before)
        self.assertEqual(loaded.予測する(予測要求(a)).出力,tuple(zip(*a)))

    def test_全八添字教師fixtureを固定seedで比較(self):
        import random
        rng=random.Random(1731)
        contract=deepcopy(CONTRACT)
        for row in contract['名義宣言']:row['容器型']=['list','list']
        # 開発試験の教師だけが8通りの係数を指定。学習器には入力と経験のみ。
        for transpose in (False,True):
            for flip0 in (False,True):
                for flip1 in (False,True):
                    s=HDS学習系統(最大条件数=1,一般再利用有効=True)
                    fresh=HDS学習系統(最大条件数=1,一般再利用有効=True)
                    def transform(a):
                        b=[list(x) for x in zip(*a)] if transpose else deepcopy(a)
                        if flip0:b=b[::-1]
                        if flip1:b=[r[::-1] for r in b]
                        return b
                    for phase,shapes in [('old',[(2,3),(3,4),(4,5)]),('new',[(2,4),(3,5)])]:
                        for h,w in shapes:
                            a=[[rng.randrange(10) for _ in range(w)] for _ in range(h)]
                            s.処理する(inp(a,transform(a),phase,contract))
                            if phase=='new':fresh.処理する(inp(a,transform(a),phase,contract))
                        if phase=='old':
                            for p in s.エンジン._有効原理群():
                                if p.関係型=='添字アフィン関係' and p.結果経路==('b',):
                                    s.エンジン.一般再利用候補を登録する(p.原理識別子,contract)
                    a=[[rng.randrange(10) for _ in range(6)] for _ in range(4)]
                    self.assertIn(transform(a),outputs(query(s,a,contract)))
                    self.assertEqual(outputs(query(fresh,a,contract)),[])

    def test_再利用有効の評価入力と正解を変更しても状態同一(self):
        from 接続.学習環境.実験 import 実験する
        from 接続.学習環境.契約 import 予測要求
        first=HDS学習機械(64,観測表現='配列階層',一般再利用有効=True)
        for h,w,k in [(2,3,0),(3,4,1),(4,5,2)]:
            a=[[(r*w+c+k)%10 for c in range(w)] for r in range(h)]
            first.観測する(予測要求(a),list(map(list,zip(*a))))
        first.新しい課題();second=deepcopy(first)
        tasks={'train':[],'test':[{'input':[[1,2],[3,4]],'output':[[3,1],[4,2]]}]}
        for h,w,k in [(2,4,5),(3,5,6)]:
            a=[[(r*w+c+k)%10 for c in range(w)] for r in range(h)]
            tasks['train'].append({'input':a,'output':[list(x) for x in zip(*a)]})
        実験する(tasks,64,学習機械=first)
        tasks['test']=[{'input':[[9,8,7],[6,5,4]],'output':[[0]]}]
        実験する(tasks,64,学習機械=second)
        self.assertEqual(first.状態署名(),second.状態署名())

    def test_不正契約は取込前拒否(self):
        s,_=trained();before=deepcopy(s.エンジン.台帳.全取得())
        for mutation in ({'名義宣言':[2]}, {'名義宣言':[{'経路':['a'],'容器型':'list','葉型':['int'],'値域':None}]}):
            with self.assertRaises(ValueError):s.処理する(inp([1,2],[2,1],contract={**CONTRACT,**mutation}))
        self.assertEqual(before,s.エンジン.台帳.全取得())

    def test_四群評価CLIの設定を固定(self):
        import json,hashlib,subprocess,sys,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);task=root/'fixture.json'
            task.write_text(json.dumps({'train':[{'input':[[x]],'output':[[x]]} for x in (1,2,3)],'test':[{'input':[[9]],'output':[[9]]}]}))
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps({'教材':[{'ファイル':task.name,'SHA256':hashlib.sha256(task.read_bytes()).hexdigest()}]}))
            repo=Path(__file__).resolve().parents[2]
            result=subprocess.run([sys.executable,str(repo/'道具/数量除去を比較.py'),'--関係族','再利用','--教材',str(root),
                '--固定表',str(manifest),'--出力',str(root/'result'),'--壁時計秒','10','--仮想MiB','384'],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((root/'result'/'集計.json').read_text())
            self.assertEqual(report['除去関係族'],'再利用')
            self.assertEqual(list(report['正解数'].values()),[1,1,1,1])
            for mode,row in report['課題別'][0]['比較'].items():
                for stage in ('初期','終了'):
                    self.assertEqual(row[stage]['一般再利用有効'],'無効' not in mode)
                    self.assertTrue(row[stage]['数量関係有効']);self.assertTrue(row[stage]['添字関係有効'])
                    self.assertFalse(row[stage]['関係合成有効'])
                    self.assertEqual(row[stage]['観測表現'],'配列階層')

    def test_現在の推論対象外の葉を再利用しない(self):
        from dataclasses import replace
        s,_=trained()
        for a in ([20,21,22],[30,31,32]):s.処理する(inp(a,a[::-1]))
        q=s.吸気系.取り込む(inp([40,41,42]))
        q=replace(q,観測群=tuple(replace(o,推論対象=False) for o in q.観測群))
        self.assertEqual(outputs(s.エンジン.照会(q)),[])

    def test_現在対照の競合は合成にも使わない(self):
        s,_=trained()
        for a in ([20,21,20],[30,31,30]):s.処理する(inp(a,a))
        s.エンジン.関係合成有効=True
        self.assertEqual(outputs(query(s,[40,41,42])),[])
        self.assertTrue(query(s,[40,41,42]).競合群)

    def test_数量添字の無効化を迂回しない(self):
        s,_=trained()
        for a in ([20,21,22],[30,31,32]):s.処理する(inp(a,a[::-1]))
        s.エンジン.添字関係有効=False
        self.assertEqual(outputs(query(s,[40,41,42])),[])
        s.処理する(inp([50,51,52],[50,51,52]))
        self.assertEqual(s.エンジン.台帳.取得('一般再利用検証')[-1]['状態'],'QUARANTINE')

    def test_独立再実行の論理状態は同一(self):
        from 接続.学習環境.HDS接続 import 正規化
        a,_=trained();b,_=trained()
        for learner in (a,b):
            for x in ([20,21,22],[30,31,32]):learner.処理する(inp(x,x[::-1]))
        self.assertEqual(正規化(a.エンジン.台帳.全取得()),正規化(b.エンジン.台帳.全取得()))
        self.assertEqual(a.エンジン.識別子.状態を書き出す(),b.エンジン.識別子.状態を書き出す())
        self.assertEqual(outputs(query(a,[40,41,42])),outputs(query(b,[40,41,42])))

if __name__=='__main__':unittest.main()
