"""カテゴリ値を保つ、正規化配列添字の経験的アフィン関係。"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import product
import json
from .型 import 原理候補, 検証結果, 判定状態
from .構造関係 import 容器群, ノード群, 葉写像, 容器署名

添字関係型='添字アフィン関係'


def _値鍵(value):
    if type(value) not in (str,int,float,bool,type(None)):
        raise ValueError('添字関係の葉はJSON相当のカテゴリ値だけ')
    return type(value).__name__+':'+json.dumps(value,ensure_ascii=False,sort_keys=True)


def 配列(value):
    if type(value) not in (list,tuple) or len(value)<2:
        raise ValueError('各軸長2以上の順序容器が必要')
    if all(type(x) not in (list,tuple) for x in value):
        shape=(len(value),); kinds=(type(value).__name__,)
        values={(i,):x for i,x in enumerate(value)}
    elif all(type(row) in (list,tuple) for row in value):
        width=len(value[0]);rowtype=type(value[0])
        if width<2 or any(type(row) is not rowtype or len(row)!=width for row in value):
            raise ValueError('矩形・同じ行容器型が必要')
        shape=(len(value),width);kinds=(type(value).__name__,rowtype.__name__)
        values={(r,c):x for r,row in enumerate(value) for c,x in enumerate(row)}
    else:
        raise ValueError('混在rankは扱わない')
    keys={pos:_値鍵(v) for pos,v in values.items()}
    return {'形状':shape,'容器型':kinds,'値':values,'鍵':keys,'度数':Counter(keys.values()),'葉型':tuple(sorted({type(v).__name__ for v in values.values()}))}


def _モデル鍵(model):
    return json.dumps(model,separators=(',',':'))


def _頂点(shape):
    return list(product(*[(0,n-1) for n in shape]))


def _正規化(pos,shape):
    return tuple(Fraction(i,n-1) for i,n in zip(pos,shape))


def _軸対応(model):
    matrix,offset=model
    rank=len(offset)
    if rank not in (1,2) or len(matrix)!=rank or any(len(row)!=rank for row in matrix):
        raise ValueError('添字係数のrank不一致')
    if any(type(x) is not int for row in matrix for x in row) or any(type(x) is not int for x in offset):
        raise ValueError('基底対応由来の整数係数だけ')
    vertices=set(product((0,1),repeat=rank))
    image={tuple(offset[i]+sum(matrix[i][j]*v[j] for j in range(rank)) for i in range(rank)) for v in vertices}
    if image!=vertices:
        raise ValueError('正規化矩形頂点の全単射でない')
    axes=[]
    for j in range(rank):
        nz=[i for i in range(rank) if matrix[i][j]!=0]
        if len(nz)!=1 or abs(matrix[nz[0]][j])!=1:
            raise ValueError('全単射の軸対応が閉じない')
        axes.append(nz[0])
    return tuple(axes)


def _候補モデル(source,target):
    rank=len(source['形状'])
    if len(target['形状'])!=rank or source['容器型']!=target['容器型'] or source['度数']!=target['度数']:
        return ()
    origin=(0,)*rank
    anchors=[origin]+[tuple(target['形状'][j]-1 if j==axis else 0 for j in range(rank)) for axis in range(rank)]
    corners=_頂点(source['形状'])
    matches=[[p for p in corners if source['鍵'][p]==target['鍵'][a]] for a in anchors]
    models={}
    for points in product(*matches):
        if len(set(points))!=rank+1:continue
        normalized=[_正規化(p,source['形状']) for p in points]
        offset=tuple(int(x) for x in normalized[0])
        matrix=tuple(tuple(int(normalized[j+1][i]-normalized[0][i]) for j in range(rank)) for i in range(rank))
        model=(matrix,offset)
        try:axes=_軸対応(model)
        except ValueError:continue
        if tuple(source['形状'][axis] for axis in axes)!=target['形状']:continue
        models[_モデル鍵(model)]=model
    return tuple(models[k] for k in sorted(models))


def モデルを適用(model,source):
    matrix,offset=model; axes=_軸対応(model)
    if len(axes)!=len(source['形状']):raise ValueError('入力rankが範囲外')
    shape=tuple(source['形状'][a] for a in axes)
    values={};used=set()
    for target in product(*[range(n) for n in shape]):
        u=_正規化(target,shape)
        point=tuple((offset[i]+sum(matrix[i][j]*u[j] for j in range(len(u))))*(n-1) for i,n in enumerate(source['形状']))
        if any(x.denominator!=1 or not 0<=x<n for x,n in zip(point,source['形状'])):
            raise ValueError('整数添字・範囲の閉包が未成立')
        pos=tuple(int(x) for x in point)
        if pos in used:raise ValueError('添字が一対一でない')
        used.add(pos);values[target]=deepcopy(source['値'][pos])
    if used!=set(source['値']):raise ValueError('全要素を被覆しない')
    def build(prefix):
        depth=len(prefix)
        if depth==len(shape):return values[prefix]
        children=[build(prefix+(i,)) for i in range(shape[depth])]
        return tuple(children) if source['容器型'][depth]=='tuple' else children
    return build(())


def _同じ出力(a,b):
    try:return 容器署名(a)==容器署名(b)
    except (ValueError,TypeError):return False


def _観測対(experiences,source_path,target_path,excluded=()):
    rows=[]
    for e in experiences:
        if e.経験識別子 in excluded:continue
        nodes=ノード群(e.原入力)
        if source_path not in nodes or target_path not in nodes:continue
        try:source=配列(nodes[source_path])
        except (ValueError,TypeError):continue
        rows.append((e,source,nodes[target_path],nodes[source_path]))
    return rows


def _導出(rows,minimum):
    if not rows:return None
    signature=(len(rows[0][1]['形状']),rows[0][1]['容器型'],rows[0][1]['葉型'])
    if any((len(s['形状']),s['容器型'],s['葉型'])!=signature for _,s,_,_ in rows):return None
    distinct={容器署名(raw) for _,s,t,raw in rows}
    if len(distinct)<max(3,minimum) or len({v for _,s,_,_ in rows for v in s['鍵'].values()})<2:return None
    try:target=配列(rows[0][2])
    except (ValueError,TypeError):return None
    seed=_候補モデル(rows[0][1],target)
    surviving=[]; rejected=[]
    for model in seed:
        failures=[]
        for e,source,observed,_ in rows:
            try:same=_同じ出力(モデルを適用(model,source),observed)
            except (ValueError,TypeError):same=False
            if not same:failures.append(e.経験識別子)
        if failures:rejected.append((_モデル鍵(model),tuple(failures)))
        else:surviving.append(model)
    if not surviving:return None
    return tuple(surviving),signature,tuple(rejected),len(distinct)


def 添字候補(experiences,skepticism_refs,minimum,identifier,authorized_paths):
    paths=sorted({p for e in experiences for p in 容器群(e.原入力) if p},key=repr)
    result=[]
    for source in paths:
        for target in paths:
            if source==target or source[:len(target)]==target or target[:len(source)]==source:continue
            rows=_観測対(experiences,source,target)
            if authorized_paths:
                try:
                    if any(not all(any((base+leaf)[:len(a)]==a for a in authorized_paths) for leaf in 葉写像(raw))
                           for e,s,t,raw_source in rows for base,raw in ((source,raw_source),(target,t))):continue
                except ValueError:continue
            learned=_導出(rows,minimum)
            if learned is None:continue
            models,signature,rejected,distinct=learned
            table=tuple(((_モデル鍵(m),),_モデル鍵(m)) for m in models)
            values=tuple(((_モデル鍵(m),),m) for m in models)
            result.append(原理候補(identifier('原理候補'),experiences[0].対象系境界,添字関係型,(source,),target,
                table,values,tuple(e.経験識別子 for e,_,_,_ in rows),(),tuple(skepticism_refs),
                {'rank':signature[0],'容器型':signature[1],'葉型':signature[2],'仮説数':len(models),'候補別反例':rejected,
                 '確認範囲':'各軸長2以上の同rank順序容器。正規化添字の整数全単射が閉じる形状'},
                {'作用':'カテゴリ対応→基底添字係数→全要素検証','因果断定':False,'異なる入力容器数':distinct,
                 '開発バイアス':'正規化添字アフィン族。名前付き変換一覧を使わない'}))
    return tuple(result)


def 添字予測(principle,raw):
    source=配列(raw)
    if len(source['形状'])!=principle.適用範囲['rank'] or source['容器型']!=tuple(principle.適用範囲['容器型']) or source['葉型']!=tuple(principle.適用範囲['葉型']):
        raise ValueError('入力容器のrank/typeが範囲外')
    result={}
    for _,model in principle.対応値表:
        value=モデルを適用(model,source);result[容器署名(value)]=value
    if not result:raise ValueError('添字仮説が空')
    return tuple(result.values())


def 添字証拠(principle,experiences):
    if len(principle.条件経路群)!=1:return (),()
    excluded=getattr(principle,'除外反証参照群',getattr(principle,'除外経験参照群',()))
    models=list(principle.対応値表)
    survivors=set(range(len(models)));observed=[]
    for e,s,t,raw in _観測対(experiences,principle.条件経路群[0],principle.結果経路,excluded):
        if e.対象系境界!=principle.対象系境界:continue
        if len(s['形状'])!=principle.適用範囲.get('rank') or s['容器型']!=tuple(principle.適用範囲.get('容器型',())) or s['葉型']!=tuple(principle.適用範囲.get('葉型',())):continue
        matched=set()
        for i,(_,model) in enumerate(models):
            try:same=_同じ出力(モデルを適用(model,s),t)
            except (ValueError,TypeError,KeyError):same=False
            if same:matched.add(i)
        observed.append((e.経験識別子,matched));survivors.intersection_update(matched)
    if not observed:return (),()
    if survivors:return tuple(ref for ref,_ in observed),()
    # 同じ一つの仮説が全経験に整合する必要がある。経験ごとに別仮説へ逃げない。
    all_models=set(range(len(models)))
    return (tuple(ref for ref,matched in observed if matched==all_models),
            tuple(ref for ref,matched in observed if matched!=all_models))


def 添字検証(principle,experiences,minimum):
    if len(principle.条件経路群)!=1:
        return 検証結果(判定状態.失敗,'添字schemaは入力容器一つを必要とする')
    support,counters=添字証拠(principle,experiences)
    excluded=getattr(principle,'除外反証参照群',getattr(principle,'除外経験参照群',()))
    rows=_観測対([e for e in experiences if e.対象系境界==principle.対象系境界],principle.条件経路群[0],principle.結果経路,excluded)
    learned=_導出(rows,minimum)
    valid=False;count=0
    if learned is not None:
        models,signature,rejected,count=learned
        expected=tuple(((_モデル鍵(m),),m) for m in models)
        table=tuple(((_モデル鍵(m),),_モデル鍵(m)) for m in models)
        valid=(principle.対応値表==expected and principle.対応表==table and principle.適用範囲.get('rank')==signature[0]
               and tuple(principle.適用範囲.get('容器型',()))==signature[1] and tuple(principle.適用範囲.get('葉型',()))==signature[2] and principle.適用範囲.get('仮説数')==len(models)
               and principle.適用範囲.get('候補別反例')==rejected)
    verdict=判定状態.失敗 if counters else (判定状態.適合 if valid else 判定状態.断定保留)
    return 検証結果(verdict,'全経験から添字仮説集合を再導出し、候補の選別漏れ・支持・全単射を検証',support,counters,count,0 if learned is None else len(learned[0]))
