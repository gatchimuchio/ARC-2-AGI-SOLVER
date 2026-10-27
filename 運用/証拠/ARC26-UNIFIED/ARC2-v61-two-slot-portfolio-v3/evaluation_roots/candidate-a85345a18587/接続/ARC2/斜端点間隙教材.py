"""Strict adapter for an explicitly declared unowned-diagonal deletion prior.
The teacher-fit consensus is retained separately and can still abstain.
"""
from . import 斜端点間隙核 as api


def valid_teachers(teachers):
    if type(teachers) is not list or len(teachers) < 2:
        return False
    seen=set()
    for pair in teachers:
        if type(pair) is not dict:
            return False
        source,target=pair.get('input'),pair.get('output')
        if not api.valid_grid(source) or not api.valid_grid(target):
            return False
        if len(source)!=len(target) or len(source[0])!=len(target[0]):
            return False
        key=tuple(map(tuple,source))
        if key in seen:
            return False
        seen.add(key)
    return True


class 斜端点間隙教材:
    def __init__(self,teachers):
        self.model=None
        self.consensus_model=None
        if not valid_teachers(teachers):
            return
        self.consensus_model,evidence=api.fit(teachers)
        if 'delete_unowned' not in self.consensus_model['policies']:
            return
        records=next(x['records'] for x in evidence if x['policy']=='delete_unowned')
        strokes=[s for r in records for s in r['strokes']]
        # The added prior extends actually observed unowned deletion; it must
        # never originate from query behavior or an unconstrained identity fit.
        if not any(s['candidates'] for s in strokes):
            return
        if not any(not s['candidates'] and not s.get('attachments') for s in strokes):
            return
        self.model={'version':1,'policies':['delete_unowned']}

    def 候補(self,grid,_policy=None):
        return api.predict(grid,self.model)

    def 記録(self):
        return {'全教師再現': bool(self.model), '事前支持数':0,
                '保持候補':self.model,'教師整合全候補':self.consensus_model,
                '追加prior':'all unowned diagonal strokes are deleted'}
