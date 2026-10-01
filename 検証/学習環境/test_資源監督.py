import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from 道具.資源制限つき継続評価 import 監督, 次状態を選ぶ
from 接続.学習環境.HDS接続 import HDS学習機械


class 資源監督試験(unittest.TestCase):
    def test_正常終了(self):
        self.assertEqual(監督([sys.executable, '-c', 'print(1)'], 2, 128)['分類'], '完了')

    def test_時間超過を成功扱いしない(self):
        self.assertEqual(監督([sys.executable, '-c', 'import time; time.sleep(2)'], .05, 128)['分類'], '時間上限')

    def test_メモリ超過を別区分にする(self):
        self.assertEqual(監督([sys.executable, '-c', 'x=bytearray(128*1024*1024)'], 2, 64)['分類'], 'メモリ上限')

    def test_他の失敗をメモリ不足と捏造しない(self):
        self.assertEqual(監督([sys.executable, '-c', 'raise ValueError("fixture")'], 2, 128)['分類'], '実行失敗')

    def test_途中checkpointが存在しても失敗時は採用しない(self):
        with tempfile.TemporaryDirectory() as d:
            old, new = Path(d)/'old', Path(d)/'new'
            (new/'checkpoint').mkdir(parents=True)
            (new/'checkpoint'/'境界.json').write_text(json.dumps({'状態署名':'same'}))
            (new/'report.json').write_text(json.dumps({'終了':{'状態署名':'same'}}))
            for failure in ('時間上限','メモリ上限','実行失敗'):
                self.assertEqual(次状態を選ぶ({'分類':failure},new,old),old)
            with self.assertRaises(ValueError):
                次状態を選ぶ({'分類':'完了'},new,old)
            (new/'checkpoint'/'HDS.json').write_text('{}')
            self.assertEqual(次状態を選ぶ({'分類':'完了'},new,old),new/'checkpoint')
            (new/'report.json').write_text(json.dumps({'終了':{'状態署名':'different'}}))
            with self.assertRaises(ValueError):
                次状態を選ぶ({'分類':'完了'},new,old)

    def test_workerは元checkpointを変更せず完了物を別保存(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, output = root / 'old', root / 'new'
            HDS学習機械(64, 観測表現='配列階層').保存する(source)
            before = {p.name:p.read_bytes() for p in source.iterdir()}
            task = root / 'fixture.json'
            task.write_text(json.dumps({'train':[{'input':[[x]], 'output':[[x]]} for x in (1,2,3)],
                                        'test':[{'input':[[9]],'output':[[9]]}]}))
            r = 監督([sys.executable,str(ROOT/'道具/資源制限つき継続評価.py'),'worker','--task',str(task),
                     '--task-sha256',hashlib.sha256(task.read_bytes()).hexdigest(),'--checkpoint',str(source),'--output',str(output)], 5, 256)
            self.assertEqual(r['分類'],'完了',r)
            self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})
            self.assertEqual(HDS学習機械.読み込む(output/'checkpoint').概況()['全課題保持経験数'],3)

if __name__ == '__main__':
    unittest.main()
