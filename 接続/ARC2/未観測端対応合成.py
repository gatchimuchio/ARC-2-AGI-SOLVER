"""既存ARC物体端投射内の明示的未観測キー束縛事前仮説。"""
from missing_edge_bindings import MissingEdgeBindings

class 未観測端対応合成教材(MissingEdgeBindings):
    def 学習する(self, 機械, 観測へ):
        return self.learn(機械, 観測へ)

    def 候補(self, 格子, policy):
        return self.predict(格子, policy)

    def 記録(self):
        return {**self.legacy.記録(),
                "合成事前仮説": "単一特徴の未観測キーだけを教師整合合同peer関係で束縛",
                "保持peer候補数": None if self.peer_models is None else len(self.peer_models),
                "peer学習完了": self.peer_models is not None,
                "確認済み原理数": len(self.confirmed_principles)}
