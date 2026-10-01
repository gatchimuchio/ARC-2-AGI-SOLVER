#!/usr/bin/env python3
"""同一数量型Frame・実装で、数量関係族だけの有効/無効を資源監督つき比較。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from 接続.学習環境.HDS接続 import HDS学習機械,実装署名
from 道具.資源制限つき継続評価 import 監督,保存,次状態を選ぶ


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('教材','固定表','出力'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--最大セル数',type=int,default=36)
    p.add_argument('--壁時計秒',type=int,default=240)
    p.add_argument('--仮想MiB',type=int,default=1536)
    args=p.parse_args()
    if args.出力.exists():p.error('既存実験を上書きしない')
    if not 1<=args.最大セル数<=64 or not 1<=args.壁時計秒<=240 or not 128<=args.仮想MiB<=1536:
        p.error('この比較の資源範囲外')
    manifest_bytes=args.固定表.read_bytes();manifest=json.loads(manifest_bytes)
    if not 1<=len(manifest['教材'])<=16:p.error('有界比較は1〜16課題')
    tasks=[]
    for item in manifest['教材']:
        name=item['ファイル']
        if Path(name).name!=name:p.error('教材path不正')
        path=args.教材/name;data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=item['SHA256']:p.error('教材hash不一致')
        content=json.loads(data)
        if not 3<=len(content['train'])<=8 or any(len(g)*len(g[0])>args.最大セル数 for row in content['train']+content['test'] for g in row.values()):
            p.error('教材の事前資源範囲不一致')
        tasks.append((name,path,item['SHA256'],len(content['test'])))
    worker=ROOT/'道具/資源制限つき継続評価.py'
    frozen=実装署名();evaluator=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    worker_hash=hashlib.sha256(worker.read_bytes()).hexdigest()
    modes={'数量有効_継続':True,'数量無効_継続':False,'数量有効_初期化':True,'数量無効_初期化':False}
    states={}
    for mode,enabled in modes.items():
        state=args.出力/'開始'/mode
        HDS学習機械(args.最大セル数,観測表現='配列階層',数量関係有効=enabled).保存する(state)
        states[mode]=state
    initial=dict(states)
    plan={'責任':'同じ数量型Frame・コード・資源で数量関係族だけを除去する開発比較',
          '実装署名':frozen,'評価器SHA256':evaluator,'workerSHA256':worker_hash,
          '固定表SHA256':hashlib.sha256(manifest_bytes).hexdigest(),'教材':manifest['教材'],
          '最大セル数':args.最大セル数,'壁時計秒':args.壁時計秒,'仮想MiB':args.仮想MiB,
          '観測表現':'配列階層','数量設定':modes,'課題数':len(tasks),'評価例数':sum(x[3] for x in tasks)}
    保存(args.出力/'事前設定.json',plan)
    results=[]
    for i,(name,path,task_hash,test_count) in enumerate(tasks):
        row={'教材':name,'比較':{}}
        for mode,enabled in modes.items():
            checkpoint=initial[mode] if mode.endswith('初期化') else states[mode]
            dest=args.出力/Path(name).stem/mode
            command=[sys.executable,str(worker),'worker','--task',str(path.resolve()),'--task-sha256',task_hash,
                     '--checkpoint',str(checkpoint.resolve()),'--output',str(dest.resolve())]
            status=監督(command,args.壁時計秒,args.仮想MiB)
            next_state=次状態を選ぶ(status,dest,checkpoint)
            if status['分類']=='完了':
                report=json.loads((dest/'report.json').read_text())
                if report['実装署名']!=frozen or report['初期']['数量関係有効']!=enabled or report['終了']['数量関係有効']!=enabled:
                    raise RuntimeError('worker実装・設定が不一致')
                states[mode]=next_state
                compact={k:report[k] for k in ('previous','current','評価例数','記憶除去','初期','終了','学習曲線','資源')}
            else:
                compact={'previous':None,'current':0,'評価例数':test_count,'状態':'HOLD',
                         '経験更新':'未完了課題の状態は採用しない。直前checkpointを保持'}
            compact['監督']=status
            row['比較'][mode]=compact
            保存(dest/'監督.json',compact)
        results.append(row)
        if 実装署名()!=frozen or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=evaluator or hashlib.sha256(worker.read_bytes()).hexdigest()!=worker_hash or args.固定表.read_bytes()!=manifest_bytes:
            raise RuntimeError('実験中に機械・評価器・教材固定表が変更された')
        summary={**plan,'完了課題数':len(results),'正解数':{m:sum(x['比較'][m]['current'] for x in results) for m in modes},
                 '課題別':results,'最終checkpoint':{m:str(v) for m,v in states.items()}}
        保存(args.出力/'集計.json',summary)
        print(json.dumps({'完了':i+1,'課題数':len(tasks),'正解数':summary['正解数']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
