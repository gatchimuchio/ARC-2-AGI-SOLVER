"""Strict public boundary for generic feature-conditioned marker alignment."""
from collections import Counter
from .特徴条件整列 import FeatureAlignment
from .標識経路層教材 import valid_teachers
from .二軸補完教材 import valid_grid


class 特徴条件整列教材(FeatureAlignment):
    def __init__(self, teachers):
        valid = valid_teachers(teachers)
        # Necessary for this exact full-object teacher correspondence grammar:
        # fixed cues + bijective colored shapes + unchanged canvas preserve counts.
        # Query cropping remains a declared render prior; cropped teachers never fit.
        if valid:
            valid = all(Counter(v for row in p['input'] for v in row) ==
                        Counter(v for row in p['output'] for v in row)
                        for p in teachers)
        super().__init__(teachers if valid else [])

    def 候補(self, grid, policy=None):
        if not valid_grid(grid):
            return None, {'failure': 'invalid_grid'}
        return super().候補(grid, policy)
