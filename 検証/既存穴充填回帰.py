from __future__ import annotations

import unittest

from 接続.ARC2.既存穴充填 import _template_hole_pack_candidates


class 既存穴充填回帰(unittest.TestCase):
    def test_右側テンプレートは左側の全素材パネルを使う(self):
        template = [
            [1, 1, 1, 2],
            [1, 1, 1, 2],
            [2, 2, 1, 2],
            [2, 2, 1, 2],
        ]
        source = [
            [2, 2, 1, 2, 2],
            [1, 1, 2, 1, 2],
            [1, 1, 1, 1, 2],
            [1, 1, 1, 1, 2],
        ]
        grid = [source[index] + row for index, row in enumerate(template)]

        candidates = _template_hole_pack_candidates(grid)
        right = [
            candidate
            for candidate in candidates
            if candidate["split_mode"] == "vertical_template_right"
            and candidate["template_origin"] == (0, 5)
            and candidate["template_shape"] == (4, 4)
        ]

        self.assertTrue(right)
        self.assertTrue(
            all(
                candidate["source_origin"] == (0, 0)
                and candidate["source_shape"] == (4, 5)
                for candidate in right
            )
        )


if __name__ == "__main__":
    unittest.main()
