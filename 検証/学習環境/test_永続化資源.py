from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from 接続.学習環境.HDS接続 import HDS学習機械
from 接続.学習環境.契約 import 予測要求
from hds学習系統 import 永続化


class 永続化資源試験(unittest.TestCase):
    def machine(self):
        m = HDS学習機械(64, 観測表現='配列階層')
        for x in (1,2,3):
            m.観測する(予測要求(((x,x+1),)),((x,x+1),))
        return m

    def test_旧文字列方式と同一bytes(self):
        m = self.machine()
        e = m.系.エンジン
        value = {'形式版':7, '最小支持数':e.最小支持数, '最大条件数':e.最大条件数,
                 '数量関係有効':e.数量関係有効, '添字関係有効':e.添字関係有効, '識別子状態':e.識別子.状態を書き出す(), '台帳':e.台帳.全取得(),
                 '状態履歴':e.状態.履歴(), '原理履歴':e._原理履歴}
        expected = json.dumps(永続化._符号化(value),ensure_ascii=False,indent=2).encode()
        before = m.状態署名()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'state.json'
            永続化.書き出す(e,path)
            self.assertEqual(path.read_bytes(),expected)
            restored = 永続化.読み込む(path,type(e))
            m.系.エンジン=restored
        self.assertEqual(m.状態署名(),before)

    def test_一括dumpsを保存経路で使わない(self):
        m=self.machine()
        with tempfile.TemporaryDirectory() as d, patch.object(永続化.json,'dumps',side_effect=AssertionError('巨大文字列禁止')):
            永続化.書き出す(m.系.エンジン,Path(d)/'state.json')

    def test_途中書込み失敗で既存fileを破壊しない(self):
        m=self.machine()
        def fail(value, stream, **kwargs):
            stream.write('partial')
            raise OSError('injected write failure')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_bytes(b'previous')
            with patch.object(永続化.json,'dump',side_effect=fail), self.assertRaises(OSError):
                永続化.書き出す(m.系.エンジン,path)
            self.assertEqual(path.read_bytes(),b'previous')
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()),['state.json'])

    def test_単一file置換失敗も元を保持(self):
        m=self.machine()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_bytes(b'previous')
            with patch.object(永続化.os,'replace',side_effect=OSError('replace failure')), self.assertRaises(OSError):
                永続化.書き出す(m.系.エンジン,path)
            self.assertEqual(path.read_bytes(),b'previous')
            self.assertEqual(len(list(Path(d).iterdir())),1)

    def test_非空checkpoint保存先を変更前に拒否(self):
        m=self.machine()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'checkpoint';m.保存する(path)
            before={p.name:p.read_bytes() for p in path.iterdir()}
            with self.assertRaises(FileExistsError):
                m.保存する(path)
            self.assertEqual(before,{p.name:p.read_bytes() for p in path.iterdir()})
            self.assertEqual(HDS学習機械.読み込む(path).状態署名(),m.状態署名())

    def test_境界書込み失敗は片方だけを公開しない(self):
        m=self.machine();original=json.dump
        def fail(value, stream, **kwargs):
            if '実装署名' in value:
                stream.write('partial');raise OSError('boundary failure')
            return original(value,stream,**kwargs)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'checkpoint';path.mkdir()
            with patch.object(json,'dump',side_effect=fail),self.assertRaises(OSError):
                m.保存する(path)
            self.assertEqual(list(path.iterdir()),[])
            self.assertEqual(list(Path(d).iterdir()),[path])

    def test_directory置換失敗は完成組を公開しない(self):
        m=self.machine();original=永続化.os.replace
        def fail(source,target):
            if Path(source).is_dir():
                raise OSError('directory replace failure')
            return original(source,target)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'checkpoint'
            with patch.object(永続化.os,'replace',side_effect=fail),self.assertRaises(OSError):
                m.保存する(path)
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_保存中に非空になった宛先を削除しない(self):
        m=self.machine();original=json.dump
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'checkpoint'
            def race(value,stream,**kwargs):
                result=original(value,stream,**kwargs)
                if '実装署名' in value:
                    path.mkdir();(path/'other').write_text('keep')
                return result
            with patch.object(json,'dump',side_effect=race),self.assertRaises(OSError):
                m.保存する(path)
            self.assertEqual((path/'other').read_text(),'keep')
            self.assertEqual(list(Path(d).iterdir()),[path])

    def test_明示互換変換はHDSbytesと論理状態を保つ(self):
        from 道具.保存互換を検証 import 互換移行, 旧保存実装
        m=self.machine()
        with tempfile.TemporaryDirectory() as d:
            source,target=Path(d)/'old',Path(d)/'new'
            m.保存する(source)
            meta=json.loads((source/'境界.json').read_text());meta['実装署名']=旧保存実装
            (source/'境界.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
            before={p.name:p.read_bytes() for p in source.iterdir()}
            audit=互換移行(source,target)
            self.assertEqual(audit['新規世界観測'],0)
            self.assertEqual(audit['境界変更'],['実装署名'])
            self.assertEqual((source/'HDS.json').read_bytes(),(target/'HDS.json').read_bytes())
            self.assertEqual(HDS学習機械.読み込む(target).状態署名(),m.状態署名())
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})

    def test_互換byte不一致で宛先を公開しない(self):
        from 道具.保存互換を検証 import 互換移行, 旧保存実装
        m=self.machine()
        with tempfile.TemporaryDirectory() as d:
            source,target=Path(d)/'old',Path(d)/'new'
            m.保存する(source)
            meta=json.loads((source/'境界.json').read_text());meta['実装署名']=旧保存実装
            (source/'境界.json').write_text(json.dumps(meta))
            # 空白差だけでもexact bytes互換の主張は拒否する。
            path=source/'HDS.json';path.write_text(path.read_text()+'\n')
            with self.assertRaises(ValueError):
                互換移行(source,target)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(d).iterdir()),[source])

    def test_互換meta不一致で宛先を公開しない(self):
        from 道具.保存互換を検証 import 互換移行, 旧保存実装
        m=self.machine();original=HDS学習機械.保存する
        with tempfile.TemporaryDirectory() as d:
            source,target=Path(d)/'old',Path(d)/'new'
            original(m,source)
            meta=json.loads((source/'境界.json').read_text());meta['実装署名']=旧保存実装
            (source/'境界.json').write_text(json.dumps(meta))
            before={p.name:p.read_bytes() for p in source.iterdir()}
            def changed(obj,path):
                original(obj,path)
                p=Path(path)/'境界.json';data=json.loads(p.read_text());data['最大セル数']=63
                p.write_text(json.dumps(data))
            with patch.object(HDS学習機械,'保存する',changed),self.assertRaises(ValueError):
                互換移行(source,target)
            self.assertFalse(target.exists())
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})

    def test_復号型表は一回の読込内だけ再利用(self):
        value={'a':list(range(30)),'b':({'nested':[1,2,3]},)}
        encoded=永続化._符号化(value)
        with patch.object(永続化,'_型表',wraps=永続化._型表) as registry:
            self.assertEqual(永続化._復号(encoded),value)
            self.assertEqual(registry.call_count,1)
            self.assertEqual(永続化._復号(encoded),value)
            self.assertEqual(registry.call_count,2)
        self.assertEqual(永続化._符号化(永続化._復号(encoded)),encoded)

    def test_別読込で型登録変更を見落とさない(self):
        from dataclasses import make_dataclass
        custom=make_dataclass('FixtureValue',[('x',int)],frozen=True)
        encoded={'__データ型__':'FixtureValue','値':{'x':3}}
        with patch.object(永続化.型定義,'FixtureValue',custom,create=True):
            self.assertEqual(永続化._復号(encoded),custom(3))
        with self.assertRaises(KeyError):
            永続化._復号(encoded)

    def test_旧形式5から数量形式6を保存だけの互換と呼ばない(self):
        from 道具.保存互換を検証 import 互換移行, 旧保存実装
        m=self.machine()
        with tempfile.TemporaryDirectory() as d:
            source,target=Path(d)/'old',Path(d)/'new'
            m.保存する(source)
            p=source/'HDS.json';state=永続化._復号(json.loads(p.read_text()));state['形式版']=5
            p.write_text(json.dumps(永続化._符号化(state),ensure_ascii=False,indent=2))
            meta=json.loads((source/'境界.json').read_text());meta['実装署名']=旧保存実装
            (source/'境界.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
            with self.assertRaises(ValueError):
                互換移行(source,target)
            self.assertFalse(target.exists())

if __name__ == '__main__':
    unittest.main()
