"""明示的な非負整数数量だけの一次関係。schemaは開発バイアス、係数は観測由来。"""
from __future__ import annotations
from fractions import Fraction
from .型 import 原理候補, 検証結果, 判定状態

数量型 = '非負整数数量'
数量関係型 = '数量一次関係'


def 数量写像(experience):
    return {o.経路:o.値 for o in experience.観測群
            if o.推論対象 and o.値型 == 数量型 and type(o.値) is int and o.値 >= 0}


def 一次条件(points, minimum, *, 支持下限=3):
    distinct = sorted(set(points))
    xs = {x for x,y in distinct}
    if len(xs) < max(支持下限, minimum):
        return None
    x0,y0 = distinct[0]
    x1,y1 = next((x,y) for x,y in distinct if x != x0)
    slope = Fraction(y1-y0, x1-x0)
    offset = Fraction(y0)-slope*x0
    if slope == 0 or (slope == 1 and offset == 0):
        return None  # 既存の定値/同値の責任を重複しない。
    if any(slope*x+offset != y for x,y in distinct):
        return None
    lo,hi = min(xs),max(xs)
    return {'数量型':数量型,'傾き':(slope.numerator,slope.denominator),
            '切片':(offset.numerator,offset.denominator),'観測最小':lo,'観測最大':hi,
            '予測下限':max(0,lo-(hi-lo)),'予測上限':hi+(hi-lo),
            '予測制限':'観測幅一つまで外挿。整数・非負だけ。因果断定ではない'}


def 数量を計算する(principle, value, *, 予測制限=True):
    if type(value) is not int or value < 0 or principle.適用範囲.get('数量型') != 数量型:
        raise ValueError('宣言数量型の範囲外')
    if 予測制限 and not principle.適用範囲['予測下限'] <= value <= principle.適用範囲['予測上限']:
        raise ValueError('観測幅から定めた外挿上限外')
    a,b=Fraction(*principle.適用範囲['傾き']),Fraction(*principle.適用範囲['切片'])
    result=a*value+b
    if result.denominator != 1 or result < 0:
        raise ValueError('予測数量が非負整数に閉じない。丸めない')
    return result.numerator


def 数量証拠(principle, experiences):
    support,counters,points=[],[],[]
    excluded=set(getattr(principle,'除外反証参照群',getattr(principle,'除外経験参照群',())))
    for e in experiences:
        if e.対象系境界 != principle.対象系境界 or e.経験識別子 in excluded:
            continue
        values=数量写像(e)
        if len(principle.条件経路群)!=1 or principle.条件経路群[0] not in values or principle.結果経路 not in values:
            continue
        x,y=values[principle.条件経路群[0]],values[principle.結果経路]
        # 外挿上限は予測時の慎重さ。観測済みの反例を隠す理由にはしない。
        try:
            same=数量を計算する(principle,x,予測制限=False)==y
        except (ValueError,KeyError,TypeError,ZeroDivisionError):
            same=False
        if same:
            support.append(e.経験識別子);points.append((x,y))
        else:
            counters.append(e.経験識別子)
    return tuple(support),tuple(counters),points


def 数量検証(principle, experiences, minimum):
    support,counters,points=数量証拠(principle,experiences)
    expected=一次条件(points,minimum)
    valid=expected is not None and all(principle.適用範囲.get(k)==v for k,v in expected.items())
    verdict=判定状態.失敗 if counters else (判定状態.適合 if valid else 判定状態.断定保留)
    return 検証結果(verdict,'明示数量の異なる入力値・係数・外挿範囲を独立再検証',support,counters,len(set(points)),len({x for x,y in points}))


def 数量候補(experiences, skepticism_refs, minimum, identifier, authorized_paths):
    rows=[(e,数量写像(e)) for e in experiences]
    paths=sorted({p for e,row in rows for p in row},key=repr)
    if authorized_paths:
        paths=[p for p in paths if p in authorized_paths]
    result=[]
    for source in paths:
        for target in paths:
            if source==target:
                continue
            complete=[(e,row[source],row[target]) for e,row in rows if source in row and target in row]
            condition=一次条件([(x,y) for e,x,y in complete],minimum)
            if condition is None:
                continue
            result.append(原理候補(identifier('原理候補'),experiences[0].対象系境界,数量関係型,
                (source,),target,(),(),tuple(e.経験識別子 for e,x,y in complete),(),tuple(skepticism_refs),condition,
                {'作用':'懐疑→明示数量間の一次関係を観測から推定','因果断定':False,
                 '開発バイアス':'一次関係族・異なる入力3点以上・観測幅一つの外挿制限。係数は観測由来'}))
    return tuple(result)
