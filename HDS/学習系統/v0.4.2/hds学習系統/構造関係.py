"""キー名や添字値に依存しない、同型コレクション内の要素関係。

操作schemaは開発者が与える帰納バイアス。具体的な要素対応と採否は観測から得る。
課題ID、ARC色番号、変換解法、外部モデルを参照しない。
"""
from __future__ import annotations
from copy import deepcopy
from collections import defaultdict
from .吸気系 import _辞書キー経路要素, 内部予約接頭辞
from .型 import 原理候補

構造関係型 = frozenset({'構造同値関係', '構造要素対応関係'})


def _項目(value):
    if isinstance(value, dict):
        return sorted(((_辞書キー経路要素(k), v) for k, v in value.items()), key=lambda x: x[0])
    if isinstance(value, (list, tuple)):
        return [(f'{内部予約接頭辞}索引:{i}', v) for i, v in enumerate(value)]
    return None


def 容器群(value, path=()):
    items = _項目(value)
    if items is None:
        return {}
    result = {path: value}
    for key, child in items:
        result.update(容器群(child, path + (key,)))
    return result


def 葉写像(value, path=()):
    items = _項目(value)
    if items is None:
        if type(value) not in (int, float, str, bool, type(None)):
            raise ValueError('構造関係が扱う葉はJSON相当の値だけ')
        return {path: value}
    result = {}
    for key, child in items:
        result.update(葉写像(child, path + (key,)))
    return result


def 骨格(value):
    items = _項目(value)
    if items is None:
        return '葉'
    return (type(value).__name__, tuple((key, 骨格(child)) for key, child in items))


def 構造を予測する(principle, source):
    from .推論 import 値キー
    if type(source).__name__ != principle.適用範囲['根容器型']:
        raise ValueError('容器型が適用範囲外')
    mapping = dict(principle.対応値表)
    types = set(principle.適用範囲['葉値型群'])
    def apply(value):
        if isinstance(value, dict):
            return {k: apply(v) for k, v in value.items()}
        if isinstance(value, list):
            return [apply(v) for v in value]
        if isinstance(value, tuple):
            return tuple(apply(v) for v in value)
        if type(value).__name__ not in types:
            raise ValueError('葉の型が適用範囲外')
        if principle.関係型 == '構造同値関係':
            return deepcopy(value)
        return deepcopy(mapping[(値キー(value),)])
    return apply(source)


def 構造証拠を評価する(principle, experiences):
    from .推論 import 値キー
    support, counters = [], []
    excluded = set(getattr(principle, '除外反証参照群', getattr(principle, '除外経験参照群', ())))
    for experience in experiences:
        if experience.対象系境界 != principle.対象系境界 or experience.経験識別子 in excluded:
            continue
        containers = 容器群(experience.原入力)
        source = containers.get(principle.条件経路群[0])
        targets = ノード群(experience.原入力)
        if source is None or principle.結果経路 not in targets:
            continue
        if type(source).__name__ != principle.適用範囲['根容器型']:
            continue
        target = targets[principle.結果経路]
        try:
            a, b = 葉写像(source), 葉写像(target)
        except ValueError:
            continue
        mapping = dict(principle.対応値表)
        allowed_types = set(principle.適用範囲['葉値型群'])
        complete, contradiction = True, False
        for position, value in a.items():
            if type(value).__name__ not in allowed_types:
                complete = False
                continue
            if principle.関係型 == '構造同値関係':
                expected = value
            elif (値キー(value),) in mapping:
                expected = mapping[(値キー(value),)]
            else:
                complete = False
                continue
            if position not in b or 値キー(expected) != 値キー(b[position]):
                contradiction = True
        if complete and 骨格(source) != 骨格(target):
            contradiction = True
        if contradiction:
            counters.append(experience.経験識別子)
        elif complete and a:
            support.append(experience.経験識別子)
    return tuple(support), tuple(counters)


def 構造候補を導出する(experiences, skepticism_refs, minimum, identifier, authorized_paths=None):
    from .推論 import 値キー, 経験写像
    observed = [(e, 容器群(e.原入力)) for e in experiences]
    paths = sorted({p for _, row in observed for p in row if p}, key=repr)
    result = []
    for source_path in paths:
        for target_path in paths:
            if source_path == target_path or source_path[:len(target_path)] == target_path or target_path[:len(source_path)] == source_path:
                continue
            complete = [(e, row[source_path], row[target_path]) for e, row in observed
                        if source_path in row and target_path in row]
            def permitted(path, value):
                if not authorized_paths:
                    return True
                try:
                    return all(any((path + leaf)[:len(a)] == a for a in authorized_paths)
                               for leaf in 葉写像(value))
                except ValueError:
                    return False
            if any(not permitted(source_path, a) or not permitted(target_path, b) for _, a, b in complete):
                continue
            distinct = {値キー(sorted(経験写像(e).items(), key=repr)) for e, _, _ in complete}
            try:
                source_count = len({容器署名(a) for _, a, _ in complete})
            except ValueError:
                continue
            if len(distinct) < minimum or source_count < minimum:
                continue
            mapping, values, positions, types, roots = {}, {}, set(), set(), set()
            identity, valid = True, True
            per_value_positions = defaultdict(set)
            for experience, source, target in complete:
                if 骨格(source) != 骨格(target):
                    valid = False
                    break
                roots.add(type(source).__name__)
                try:
                    a, b = 葉写像(source), 葉写像(target)
                except ValueError:
                    valid = False
                    break
                for position, value in a.items():
                    key, dest = (値キー(value),), 値キー(b[position])
                    if key in mapping and mapping[key] != dest:
                        valid = False
                        break
                    mapping[key], values[key] = dest, deepcopy(b[position])
                    identity = identity and 値キー(value) == dest
                    positions.add(position)
                    per_value_positions[key].add(position)
                    types.add(type(value).__name__)
                if not valid:
                    break
            # 単一位置の値表を、添字一般の関係へ無条件に昇格させない。
            if not valid or len(roots) != 1 or len(positions) < 2 or len(mapping) < 2:
                continue
            if not identity and any(len(p) < 2 for p in per_value_positions.values()):
                continue
            result.append(原理候補(
                identifier('原理候補'), experiences[0].対象系境界,
                '構造同値関係' if identity else '構造要素対応関係', (source_path,), target_path,
                tuple(sorted(mapping.items())), tuple(sorted(values.items())),
                tuple(e.経験識別子 for e, _, _ in complete), (), tuple(skepticism_refs),
                {'確認範囲': '根容器型と葉型を保つ同型構造。未知の長さ・キーも候補範囲',
                 '根容器型': next(iter(roots)), '葉値型群': sorted(types),
                 '観測相対位置数': len(positions), '異なる観測数': len(distinct)},
                {'作用': '懐疑→相対位置間で一貫する要素関係の抽象', '因果断定': False,
                 '開発バイアス': '同型構造の一様要素関係schema。関係値自体は観測から導出'},
            ))
    return tuple(result)


def 形状条件を学ぶ(values):
    """観測された長さの変動だけを反復へ抽象化。固定の長さは消さない。"""
    if all(_項目(v) is None for v in values):
        return {'型': '葉'}
    kinds = {type(v).__name__ if _項目(v) is not None else '葉' for v in values}
    if len(kinds) != 1:
        return {'型': '選択', '候補': [形状条件を学ぶ([v for v in values if (type(v).__name__ if _項目(v) is not None else '葉') == kind]) for kind in sorted(kinds)]}
    kind = next(iter(kinds))
    if kind == 'dict':
        rows = [dict(_項目(v)) for v in values]
        keys = [set(row) for row in rows]
        if all(k == keys[0] for k in keys):
            return {'型': kind, '固定鍵': {k: 形状条件を学ぶ([r[k] for r in rows]) for k in sorted(keys[0])}}
        children = [v for row in rows for v in row.values()]
        return {'型': kind, '反復値': 形状条件を学ぶ(children) if children else {'型': '葉'},
                '鍵型': sorted({type(k).__name__ for value in values for k in value})}
    lengths = {len(v) for v in values}
    if len(lengths) == 1:
        size = next(iter(lengths))
        return {'型': kind, '固定位置': [形状条件を学ぶ([v[i] for v in values]) for i in range(size)]}
    children = [child for value in values for child in value]
    return {'型': kind, '反復要素': 形状条件を学ぶ(children) if children else {'型': '葉'}}


def 形状条件に適合(pattern, value):
    kind = pattern['型']
    if kind == '葉':
        return _項目(value) is None
    if kind == '選択':
        return any(形状条件に適合(p, value) for p in pattern['候補'])
    if type(value).__name__ != kind:
        return False
    if kind == 'dict':
        row = dict(_項目(value))
        if '固定鍵' in pattern:
            return set(row) == set(pattern['固定鍵']) and all(形状条件に適合(p, row[k]) for k, p in pattern['固定鍵'].items())
        return all(type(k).__name__ in pattern['鍵型'] for k in value) and all(形状条件に適合(pattern['反復値'], x) for x in row.values())
    if '固定位置' in pattern:
        return len(value) == len(pattern['固定位置']) and all(形状条件に適合(p, x) for p, x in zip(pattern['固定位置'], value))
    return all(形状条件に適合(pattern['反復要素'], x) for x in value)


def 定値の構造文脈(experiences, result_path):
    # 最上位の入力枝の条件は子の構造も含むため、同じ条件を全子へ重複保存しない。
    shapes = defaultdict(list)
    for e in experiences:
        for path, container in 容器群(e.原入力).items():
            if len(path) != 1 or path[0] == result_path[0]:
                continue
            shapes[path].append(container)
    return [(path, 形状条件を学ぶ(values)) for path, values in sorted(shapes.items())]


def 定値文脈が適合(principle, raw):
    from .推論 import 値キー
    import hashlib
    containers = 容器群(raw)
    for path, condition in principle.適用範囲.get('構造文脈', ()):
        path = tuple(path)
        if path not in containers:
            return False
        if isinstance(condition, dict):
            if not 形状条件に適合(condition, containers[path]):
                return False
        else:
            # 形式4の既存hash条件は厳密一致の意味を維持し、無言で一般化しない。
            digest = hashlib.sha256(値キー(骨格(containers[path])).encode()).hexdigest()
            if digest not in condition:
                return False
    return True


def 容器署名(value):
    from .推論 import 値キー
    return 値キー((骨格(value), sorted((p, 値キー(v)) for p, v in 葉写像(value).items())))


def 構造支持条件(candidate, experiences, support, minimum):
    """生成器の主張を信用せず、結果に使う構造入力自身の変化を再確認する。"""
    from .推論 import 値キー
    sources, positions, values = set(), set(), defaultdict(set)
    for e in experiences:
        if e.経験識別子 not in support:
            continue
        source = 容器群(e.原入力)[candidate.条件経路群[0]]
        sources.add(容器署名(source))
        for p, v in 葉写像(source).items():
            positions.add(p)
            values[値キー(v)].add(p)
    return (len(sources) >= minimum and len(positions) >= 2 and len(values) >= 2
            and (candidate.関係型 == '構造同値関係' or all(len(p) >= 2 for p in values.values())))


def 予測重複を監査する(predictions):
    """全容器の予測と、その子の予測の食い違いをHDS自身が検出する。"""
    from .推論 import 値キー
    from .型 import 競合記録
    conflicts, rejected = [], set()
    for i, parent in enumerate(predictions):
        for j, child in enumerate(predictions):
            if i == j or len(parent.結果経路) >= len(child.結果経路):
                continue
            if child.結果経路[:len(parent.結果経路)] != parent.結果経路:
                continue
            relative = child.結果経路[len(parent.結果経路):]
            nodes = {**容器群(parent.予測値), **葉写像(parent.予測値)}
            missing = relative not in nodes
            if not missing:
                a, b = nodes[relative], child.予測値
                ka = 容器署名(a) if _項目(a) is not None else 値キー(a)
                kb = 容器署名(b) if _項目(b) is not None else 値キー(b)
                if ka == kb:
                    continue
            conflicts.append(競合記録(child.結果経路,
                             ({'予測構造': '当該経路なし'} if missing else nodes[relative], child.予測値),
                             (parent.原理参照, child.原理参照)))
            rejected.update((i, j))
    return tuple(conflicts), rejected


def ノード群(value, path=()):
    """未対応の別枝を解釈せず、指定経路の観測の有無を区別する。"""
    result = {path: value}
    items = _項目(value)
    if items is not None:
        for key, child in items:
            result.update(ノード群(child, path + (key,)))
    return result
