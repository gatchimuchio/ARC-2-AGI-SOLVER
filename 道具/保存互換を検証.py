#!/usr/bin/env python3
"""保存方式だけの変更について旧checkpointとのbyte同値を検証し、新規保存先へ明示移行。"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from 道具.観測表現を比較 import 旧状態を検証して読む
from 接続.学習環境.HDS接続 import 実装署名

旧保存実装='7aaf9b5cd4fd767e028844b81991839e61799f8186aed7f30a5522a521458265'


def filehash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def 互換移行(source,destination):
    source,destination=Path(source),Path(destination)
    frozen=実装署名()
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or any(destination.iterdir()))):
        raise FileExistsError('互換移行先は新規または空directoryのみ')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.互換検証-') as temporary:
        stage=Path(temporary)/'checkpoint'
        holder,meta=旧状態を検証して読む(source,旧保存実装)
        if meta['形式版']!=2 or holder.状態署名()!=meta['状態署名']:
            raise ValueError('今回のbyte互換検証は旧形式2の完全な論理状態のみ')
        old_hashes={name:filehash(source/name) for name in ('HDS.json','境界.json')}
        holder.保存する(stage)
        if filehash(stage/'HDS.json')!=old_hashes['HDS.json']:
            raise ValueError('旧HDSと新HDSのbytes不一致。互換を主張しない')
        fresh=json.loads((stage/'境界.json').read_text())
        changed=[key for key in set(meta)|set(fresh) if meta.get(key)!=fresh.get(key)]
        if changed!=['実装署名'] or any(filehash(source/name)!=value for name,value in old_hashes.items()):
            raise ValueError('実装署名以外の境界変更または元checkpoint変更を検出')
        audit={'責任':'DEVELOPMENTによる保存byte互換検証。内部学習ではない',
               '旧実装署名':旧保存実装,'新実装署名':frozen,'状態署名':holder.状態署名(),
               '旧ファイルSHA256':old_hashes,'新ファイルSHA256':{name:filehash(stage/name) for name in old_hashes},
               '経験数':holder.概況()['全課題保持経験数'],'新規世界観測':0,'境界変更':changed}
        if 実装署名()!=frozen:
            raise RuntimeError('互換検証中に実装が変更された')
        os.replace(stage,destination)
        return audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--旧状態',type=Path,required=True)
    p.add_argument('--新状態',type=Path,required=True)
    p.add_argument('--監査',type=Path,required=True)
    args=p.parse_args()
    audit=互換移行(args.旧状態,args.新状態)
    args.監査.parent.mkdir(parents=True,exist_ok=True)
    args.監査.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(audit,ensure_ascii=False))

if __name__=='__main__':
    main()
