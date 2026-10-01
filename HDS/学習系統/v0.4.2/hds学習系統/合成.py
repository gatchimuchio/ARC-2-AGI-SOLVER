"""照会専用の派生事実。予測を経験/観測/支持として登録しない。"""
from dataclasses import dataclass, replace
from copy import deepcopy
from itertools import product
from .型 import 原理状態, 採用状態, 予測記録, 競合記録, 追加観測要求
from .構造関係 import ノード群, 容器群, 容器署名, 予測重複を監査する
from .推論 import 経験写像, 値キー
from .数量関係 import 数量写像, 数量関係型


def _鍵(value):
    try:return 容器署名(value) if isinstance(value,(dict,list,tuple)) else 値キー(value)
    except ValueError:return 値キー(value)


@dataclass(frozen=True)
class 派生事実:
    経路: tuple
    値: object
    数量: bool
    根: frozenset
    前提: tuple
    原理群: tuple
    段数: int

    def 鍵(self):
        return (self.経路,_鍵(self.値),self.数量,self.前提)


def 証明が包含する(a,b):
    """同一結論を、より少ない前提と同等以下の深さで支える場合だけ。"""
    return (a.経路==b.経路 and _鍵(a.値)==_鍵(b.値) and a.数量==b.数量
            and a.段数<=b.段数 and set(a.前提).issubset(b.前提))


def 競合循環核(records,unstable):
    """循環の子孫というだけの経路を、循環の当事者と混同しない。"""
    paths={records[i][1].結果経路 for i in unstable}
    graph={p:set() for p in paths}
    for i in unstable:
        fact,prediction=records[i]
        graph[prediction.結果経路].update(path for path,_ in fact.前提 if path in paths)
    reverse={p:set() for p in paths}
    for p,others in graph.items():
        for q in others:reverse[q].add(p)
    visited=set();order=[]
    for root in sorted(paths,key=repr):
        if root in visited:continue
        stack=[(root,False)]
        while stack:
            p,done=stack.pop()
            if done:order.append(p);continue
            if p in visited:continue
            visited.add(p);stack.append((p,True))
            stack.extend((q,False) for q in graph[p] if q not in visited)
    visited=set();core=set()
    for root in reversed(order):
        if root in visited:continue
        component=set();stack=[root]
        while stack:
            p=stack.pop()
            if p in visited:continue
            visited.add(p);component.add(p);stack.extend(reverse[p]-visited)
        if len(component)>1 or any(p in graph[p] for p in component):core.update(component)
    return core or paths


def 関係を合成する(adapter,principles,experience,depth_limit,candidate_limit):
    direct,initial_conflicts,requests=adapter._直接予測する(principles,experience)
    original_nodes=ノード群(experience.原入力)
    original_leaves=経験写像(experience)
    original_quantities=数量写像(experience)
    active=[p for p in principles if p.対象系境界==experience.対象系境界
            and p.状態==原理状態.適用範囲付き暫定原理 and p.採用状態==採用状態.有効
            and (adapter.数量関係有効 or p.関係型!=数量関係型)
            and (adapter.添字関係有効 or p.関係型!='添字アフィン関係')]
    def eligible(path,value):
        if not isinstance(value,(dict,list,tuple)):return path in original_leaves
        # 生構造の存在と、推論に利用してよい観測葉を混同しない。
        return all(p in original_leaves for p,v in original_nodes.items()
                   if p[:len(path)]==path and not isinstance(v,(dict,list,tuple)))
    pool={p:[派生事実(p,v,p in original_quantities,frozenset((p,)),(),(),0)]
          for p,v in original_nodes.items() if eligible(p,v)}
    known=set()
    records=[];calls=0;budget=None
    for depth in range(1,depth_limit+2):
        added=[]
        for rule in active:
            target=rule.結果経路
            if target in original_nodes:continue
            choices=[pool.get(p,()) for p in rule.条件経路群]
            if any(not group for group in choices):continue
            combinations=product(*choices) if choices else [()]
            for facts in combinations:
                calls+=1
                if calls>candidate_limit:
                    budget='合成候補数上限';break
                if 1+max((f.段数 for f in facts),default=0)!=depth:continue
                dependencies={};consistent=True
                for f in facts:
                    for path,key in f.前提:
                        if path in dependencies and dependencies[path]!=key:consistent=False
                        dependencies[path]=key
                    if f.段数:
                        if f.経路 in dependencies and dependencies[f.経路]!=_鍵(f.値):consistent=False
                        dependencies[f.経路]=_鍵(f.値)
                if not consistent or target in dependencies:continue
                nodes=dict(original_nodes);leaves=dict(original_leaves);quantities=dict(original_quantities)
                for f in facts:
                    nodes.update(ノード群(f.値,f.経路))
                    if not isinstance(f.値,(dict,list,tuple)):leaves[f.経路]=f.値
                    if f.数量:quantities[f.経路]=f.値
                view={'ノード':nodes,'葉':leaves,'数量':quantities,
                      '容器':{p:v for p,v in nodes.items() if isinstance(v,(dict,list,tuple))}}
                predictions,conflicts,_=adapter._直接予測する((rule,),experience,view)
                # 一つの原理内の曖昧仮説も失わず、後段の依存競合監査へ渡す。
                values=[p.予測値 for p in predictions if p.結果経路==target]
                values.extend(v for c in conflicts if c.結果経路==target for v in c.候補値群)
                roots=frozenset(p for f in facts for p in f.根)
                if rule.関係型=='定値関係':
                    roots=roots | frozenset(tuple(path) for path,_ in rule.適用範囲.get('構造文脈',()))
                lineage=tuple(dict.fromkeys(x for f in facts for x in f.原理群))+(rule.原理識別子,)
                premises=tuple(sorted(dependencies.items(),key=repr))
                for value in values:
                    value=deepcopy(value)
                    fact=派生事実(target,value,rule.関係型==数量関係型,roots,premises,lineage,depth)
                    if fact.鍵() in known:continue
                    prior=list(pool.get(target,()))+[f for f in added if f.経路==target]
                    if any(証明が包含する(other,fact) for other in prior):continue
                    if depth>depth_limit:
                        budget='合成深さ上限';break
                    known.add(fact.鍵())
                    added=[other for other in added if not 証明が包含する(fact,other)]
                    added.append(fact)
                    if len(known)>candidate_limit:
                        budget='合成派生事実数上限';break
                    records.append((fact,予測記録(rule.原理識別子,target,value,tuple(f.値 for f in facts),
                         lineage,tuple(sorted(roots,key=repr)),tuple(sorted(dependencies,key=repr)),depth)))
                if budget:break
            if budget:break
        if budget:break
        if not added:break
        for f in added:
            pool[f.経路]=[other for other in pool.get(f.経路,()) if not 証明が包含する(f,other)]
            pool[f.経路].append(f)
            if isinstance(f.値,(dict,list,tuple)):
                for path,value in ノード群(f.値,f.経路).items():
                    if path==f.経路 or path in original_nodes:continue
                    premises=dict(f.前提);premises[f.経路]=_鍵(f.値)
                    child=replace(f,経路=path,値=value,数量=False,前提=tuple(sorted(premises.items(),key=repr)))
                    if child.鍵() not in known and not any(証明が包含する(other,child) for other in pool.get(path,())):
                        known.add(child.鍵())
                        pool[path]=[other for other in pool.get(path,()) if not 証明が包含する(child,other)]
                        pool[path].append(child)
                        if len(known)>candidate_limit:
                            return (),(),(追加観測要求((),(),(),'合成派生事実数上限。探索未閉包'),)
    if budget:
        return (),tuple(initial_conflicts),(追加観測要求((),(),(),budget+'。探索未閉包のため予測を保留'),)
    active_keys={f.鍵() for group in pool.values() for f in group if f.段数}
    records=[(f,p) for f,p in records if f.鍵() in active_keys]
    if not records:return direct,initial_conflicts,requests
    valid=set(range(len(records)));seen={};history=[];conflicts=();permanent=set();notices=()
    for _ in range(len(records)+2):
        signature=frozenset(valid)
        if signature in seen:
            cycle=history[seen[signature]:]
            unstable=set.union(*cycle)-set.intersection(*cycle)
            permanent.update(競合循環核(records,unstable))
            notices=tuple(追加観測要求(path,(),(),'依存競合の循環が未解決。独立経路は保持') for path in sorted(permanent,key=repr))
            valid={i for i,(f,p) in enumerate(records) if p.結果経路 not in permanent and not any(path in permanent for path,_ in f.前提)}
            seen={};history=[]
            continue
        seen[signature]=len(history);history.append(set(valid))
        candidates=[records[i][1] for i in sorted(valid)]
        grouped={}
        for p in candidates:grouped.setdefault(p.結果経路,{}).setdefault(_鍵(p.予測値),[]).append(p)
        collisions=[競合記録(path,tuple(group[0].予測値 for group in values.values()),
                            tuple(p.原理参照 for group in values.values() for p in group))
                    for path,values in grouped.items() if len(values)>1]
        overlap,excluded=予測重複を監査する(candidates)
        collisions.extend(overlap)
        blocked={c.結果経路 for c in collisions}
        for i in excluded:blocked.add(candidates[i].結果経路)
        blocked.update(permanent);conflicts=tuple(collisions)
        updated={i for i,(f,p) in enumerate(records) if p.結果経路 not in permanent and not any(path in blocked for path,_ in f.前提)}
        if updated==valid:
            conflicts=tuple(collisions)
            result=tuple(p for i,(f,p) in enumerate(records) if i in valid and p.結果経路 not in blocked)
            present={p.結果経路 for p in result}
            return result,conflicts,notices+tuple(r for r in requests if r.結果経路 not in present)
        valid=updated
    return (),(),(追加観測要求((),(),(),'依存競合監査の上限'),)
