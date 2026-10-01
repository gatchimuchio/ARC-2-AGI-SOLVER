"""既存原理の過去証拠と現在の再確認を分ける、HDS所有の再利用判断。"""
from copy import deepcopy
from dataclasses import asdict,replace
import hashlib,json
from .型 import 原理候補,原理状態,採用状態,判定状態,競合記録
from .構造関係 import ノード群,容器署名
from .数量関係 import 数量関係型,数量写像,数量候補,一次条件
from .添字関係 import 添字関係型,_観測対,_導出,添字候補を構成する,配列,モデルを適用,添字予測
from .適応 import 原理証拠を評価する
from .検証 import 共通検証器

再利用型=frozenset((数量関係型,添字関係型))


def 署名(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def 原理署名(principle):
    # 時刻は実験ごとに異なるが、同じ原理の意味・権威は変わらない。
    value=asdict(principle)
    value.pop('時点')
    return 署名(value)


def 契約を確認(contract):
    if not isinstance(contract,dict) or set(contract)!={'版','表現','数量単位','名義宣言'}:
        raise ValueError('再利用は版・表現・数量単位・名義宣言を明示する')
    value=json.loads(json.dumps(contract,ensure_ascii=False))
    if type(value['版']) is not int or value['版']!=1 or type(value['表現']) is not str or not value['表現']:
        raise ValueError('再利用契約の版/表現不正')
    for key in ('数量単位','名義宣言'):
        if not isinstance(value[key],list):raise ValueError('宣言は列')
        paths=set()
        for row in value[key]:
            if not isinstance(row,dict):raise ValueError('宣言は辞書')
            path=row.get('経路')
            if not isinstance(path,list) or not path or any(type(x) is not str for x in path):raise ValueError('宣言経路不正')
            if tuple(path) in paths:raise ValueError('宣言経路重複')
            paths.add(tuple(path))
            if key=='数量単位':
                if set(row)!={'経路','単位'} or type(row['単位']) is not str or not row['単位']:raise ValueError('数量単位を明示する')
            else:
                if set(row)!={'経路','容器型','葉型','値域'}:raise ValueError('名義型宣言不正')
                if not isinstance(row['容器型'],list) or not row['容器型'] or any(x not in ('list','tuple','dict') for x in row['容器型']):raise ValueError('名義容器型不正')
                if not isinstance(row['葉型'],list) or not row['葉型'] or any(x not in ('int','float','str','bool','NoneType') for x in row['葉型']):raise ValueError('名義葉型不正')
                if row['値域'] is not None and (not isinstance(row['値域'],list) or len(row['値域'])!=2 or any(type(x) is not int for x in row['値域']) or row['値域'][0]>row['値域'][1]):raise ValueError('名義値域不正')
    return value


def 契約が観測に適合(contract,experience):
    nodes=ノード群(experience.原入力);quantities=数量写像(experience)
    eligible={o.経路 for o in experience.観測群 if o.推論対象}
    for row in contract['数量単位']:
        path=tuple(row['経路'])
        if path in nodes and path not in quantities:return False
    def nominal(value,row,depth=0):
        if depth<len(row['容器型']):
            if type(value).__name__!=row['容器型'][depth]:return False
            children=value.values() if isinstance(value,dict) else value
            return all(nominal(x,row,depth+1) for x in children)
        if type(value).__name__ not in row['葉型']:return False
        bounds=row['値域']
        return bounds is None or (type(value) in (int,float) and bounds[0]<=value<=bounds[1])
    for row in contract['名義宣言']:
        path=tuple(row['経路'])
        if path not in nodes:continue
        if not nominal(nodes[path],row):return False
        if any(p not in eligible for p,v in nodes.items() if p[:len(path)]==path and not isinstance(v,(dict,list,tuple))):return False
    return True


def 契約が原理を覆う(contract,p):
    paths=(*p.条件経路群,p.結果経路)
    if p.関係型==数量関係型:
        declared={tuple(x['経路']) for x in contract['数量単位']}
        return all(x in declared for x in paths)
    declared=[tuple(x['経路']) for x in contract['名義宣言']]
    return all(any(path[:len(base)]==base for base in declared) for path in paths)


def 候補化(p):
    return 原理候補(p.原理識別子,p.対象系境界,p.関係型,p.条件経路群,p.結果経路,
        p.対応表,p.対応値表,p.根拠参照群,p.反証参照群,(),p.適用範囲,{},p.除外反証参照群)


def 元原理(engine,record):
    p=next((p for p in engine._現行原理群() if p.原理識別子==record['元原理']),None)
    if p is None or p.状態!=原理状態.適用範囲付き暫定原理 or p.採用状態!=採用状態.有効:return None
    if 原理署名(p)!=record['元原理署名']:return None
    return p


def 候補群(engine):
    return tuple(engine.台帳.取得('一般再利用候補'))


def 観測契約を記録する(engine,experience,contract):
    engine.台帳.追記('観測契約',{'経験参照':experience.経験識別子,'対象系境界':experience.対象系境界,
                               '観測契約':契約を確認(contract)})


def 証拠契約が一致(engine,experiences,contract):
    declared={x['経験参照']:x['観測契約'] for x in engine.台帳.取得('観測契約')}
    return all(declared.get(e.経験識別子)==contract and 契約が観測に適合(contract,e) for e in experiences)


def 登録する(engine,principle_id,contract):
    contract=契約を確認(contract)
    p=next((p for p in engine._現行原理群() if p.原理識別子==principle_id),None)
    if p is None or p.関係型 not in 再利用型 or p.採用状態!=採用状態.有効 or p.状態!=原理状態.適用範囲付き暫定原理:return None
    if not 契約が原理を覆う(contract,p):return None
    all_source=engine._経験群(p.対象系境界)
    source=tuple(e for e in all_source if e.経験識別子 in p.根拠参照群)
    if not 証拠契約が一致(engine,all_source,contract):return None
    if 共通検証器(max(3,engine.最小支持数)).検証する(候補化(p),source).判定!=判定状態.適合:return None
    if 原理証拠を評価する(p,all_source)[1]:return None
    semantic={k:p.適用範囲[k] for k in (('数量型','傾き','切片') if p.関係型==数量関係型 else ('rank','容器型','葉型'))}
    key=署名((p.関係型,p.条件経路群,p.結果経路,p.対応値表,semantic,contract))
    prior=候補群(engine)
    for r in prior:
        if r['意味署名']==key and 元原理(engine,r) is not None:return r['候補識別子']
    if len(prior)>=128:
        if not any(x.get('種別')=='一般再利用候補予算' for x in engine.台帳.取得('残差台帳') if isinstance(x,dict)):
            engine.台帳.追記('残差台帳',{'種別':'一般再利用候補予算','上限':128,'判定':'HOLD',
                                      '理由':'登録予算を超過。既存候補・証拠は削除しない'})
        return None
    record={'候補識別子':engine._次('一般再利用候補'),'意味署名':key,'元原理':p.原理識別子,
            '元原理署名':原理署名(p),'元境界':p.対象系境界,'過去支持参照':list(p.根拠参照群),'観測契約':contract,
            '責任':'過去にHDSが採用した一般関係の候補保持。新課題の正解保存ではない'}
    engine.台帳.追記('一般再利用候補',record)
    return record['候補識別子']


def 検証する(engine,candidate_id,boundary,contract):
    result={'候補識別子':candidate_id,'対象系境界':boundary,'状態':'HOLD','理由':'未確認',
            '過去支持参照':(), '現在支持参照':(), '反証参照':(), '現在対照':(), '許可原理':None}
    record=next((r for r in 候補群(engine) if r['候補識別子']==candidate_id),None)
    if record is None:result['理由']='HDS未登録候補';return result
    result['過去支持参照']=tuple(record['過去支持参照'])
    try:current_contract=契約を確認(contract)
    except (ValueError,TypeError,KeyError):result['理由']='現在の観測契約が不正';return result
    if current_contract!=record['観測契約']:result['理由']='観測表現・型・単位の契約不一致';return result
    p=元原理(engine,record)
    if p is None:result['理由']='過去原理の権威が失効';return result
    if boundary==p.対象系境界:result['理由']='同じscopeを課題間再利用と数えない';return result
    current=engine._経験群(boundary)
    if not 証拠契約が一致(engine,current,current_contract):result['理由']='現在観測の契約が欠落/変更、または宣言した型/単位と不一致';return result
    projected=replace(p,対象系境界=boundary)
    supports,counters=原理証拠を評価する(projected,current)
    if counters:
        result.update(状態='QUARANTINE',理由='現在scopeの反例。別scopeで自動承認しない',反証参照=tuple(counters));return result
    current=tuple(e for e in current if e.経験識別子 in supports)
    source_path=p.条件経路群[0]
    if p.関係型==数量関係型:
        values=[数量写像(e)[source_path] for e in current]
    else:values=[容器署名(ノード群(e.原入力)[source_path]) for e in current]
    if len(set(values))<2:result['理由']='現在の異なる支配入力が2件未満';return result
    result['現在支持参照']=tuple(e.経験識別子 for e in current)
    old_all=engine._経験群(p.対象系境界)
    if not 証拠契約が一致(engine,old_all,record['観測契約']):result['理由']='過去証拠の契約が不一致';return result
    if 原理証拠を評価する(p,old_all)[1]:result['理由']='過去scopeに未解決の反例';return result
    source=tuple(e for e in old_all if e.経験識別子 in record['過去支持参照'])
    if 共通検証器(max(3,engine.最小支持数)).検証する(候補化(p),source).判定!=判定状態.適合:result['理由']='過去支持が再検証不能';return result
    # 過去観測は検証中だけscopeを射影し、canonical経験を追加・書換えしない。
    combined=tuple(replace(e,対象系境界=boundary) for e in source)+current
    ident=lambda kind:'再確認:'+candidate_id
    if p.関係型==数量関係型:
        candidates=数量候補(combined,(),max(3,engine.最小支持数),ident,set(p.条件経路群)|{p.結果経路})
        candidate=next((x for x in candidates if x.条件経路群==p.条件経路群 and x.結果経路==p.結果経路),None)
        points=[(数量写像(e)[source_path],数量写像(e)[p.結果経路]) for e in current]
        contrast=一次条件(points,2,支持下限=2)
        if contrast is None:result['理由']='現在数量から対照関係が閉じない';return result
        if any(contrast[k]!=p.適用範囲[k] for k in ('傾き','切片')):result['理由']='過去係数と現在係数が異なる';return result
        result['現在対照']=(contrast,)
    else:
        rows=_観測対(combined,source_path,p.結果経路,p.除外反証参照群)
        candidate=添字候補を構成する(rows,source_path,p.結果経路,max(3,engine.最小支持数),ident,boundary)
        contrast=_導出(_観測対(current,source_path,p.結果経路),2,支持下限=2)
        if contrast is None:result['理由']='現在添字の対照仮説が閉じない';return result
        result['現在対照']=contrast[0]
    if candidate is None or 共通検証器(max(3,engine.最小支持数)).検証する(candidate,combined).判定!=判定状態.適合:
        result['理由']='過去と現在を結ぶ一般関係が検証不適合';return result
    updated=replace(projected,対応表=candidate.対応表,対応値表=candidate.対応値表,適用範囲=deepcopy(candidate.適用範囲),
                    根拠参照群=candidate.根拠参照群,親原理参照=p.原理識別子,改訂理由='過去証拠と現在2以上の支配入力による再確認')
    result.update(状態='ADMIT',理由='過去3支持以上・現在2種類以上の支配入力・契約一致・全反例監査',許可原理=updated)
    return result


def 監査を記録する(engine,boundary,contract):
    for record in 候補群(engine):
        result=検証する(engine,record['候補識別子'],boundary,contract)
        result['検証識別子']=engine._次('一般再利用検証')
        result['scope責任']='同一scopeの全経験を再検査。以前のscopeの反証を削除・復帰しない'
        engine.台帳.追記('一般再利用検証',result)


def 照会候補群(engine,experience,contract):
    """登録済み証拠だけを読む。現在対照が不一致なら、その出力を保留する。"""
    if not engine.一般再利用有効:return (),(),()
    try:contract=契約を確認(contract)
    except (ValueError,TypeError,KeyError):return (),(),()
    if not 契約が観測に適合(contract,experience):return (),(),()
    allowed=[];conflicts=[];used=[];nodes=ノード群(experience.原入力)
    for record in 候補群(engine):
        r=検証する(engine,record['候補識別子'],experience.対象系境界,contract)
        if r['状態']!='ADMIT':continue
        p=r['許可原理']
        if (p.関係型==数量関係型 and not engine.数量関係有効) or (p.関係型==添字関係型 and not engine.添字関係有効):continue
        if p.結果経路 in nodes:continue
        if p.関係型==添字関係型:
            try:
                添字予測(p,nodes[p.条件経路群[0]])  # 原理と同じrank/type境界
                source=配列(nodes[p.条件経路群[0]])
                values={容器署名(value):value for m in r['現在対照'] for value in (モデルを適用(m,source),)}
            except (ValueError,TypeError,KeyError):continue
            if len(values)>1:
                conflicts.append(競合記録(p.結果経路,tuple(values.values()),(p.原理識別子,)))
                continue
        allowed.append(p);used.append(record['候補識別子'])
    return tuple(allowed),tuple(conflicts),tuple(used)
