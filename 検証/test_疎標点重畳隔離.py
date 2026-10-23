from unittest.mock import patch

from 接続.ARC2 import 疎標点重畳候補 as 候補
from 接続.ARC2.疎標点重畳教材 import extend_overlap_family


class _既存不適合:
    def __init__(self, 教師群):
        self.全教師再現 = False

    def 候補(self, 格子, 方針):
        return None, {"failure": "placement conflict or no-op output"}

    def 記録(self):
        return {"全教師再現": False}


def test_探索上限超過は候補機構内で隔離して他のHDS照会を続けられる():
    教師 = {"input": [[0, 1]], "output": [[1, 0]]}
    wrapper = extend_overlap_family(
        _既存不適合,
        lambda 格子: (None, {"failure": "placement conflict or no-op output"}),
    )

    with patch.object(
        候補, "fit_teachers", side_effect=候補.AssemblyIncomplete("work limit")
    ) as 探索:
        view = wrapper([教師])

    assert 探索.call_count == 1
    assert view.候補(教師["input"], {}) == (
        None,
        {"failure": "placement conflict or no-op output"},
    )
    assert view.記録()["sparse_marker_overlap"] == {
        "failure": "assembly_search_incomplete",
        "exception_type": "AssemblyIncomplete",
    }
