from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from 接続 import Kaggle操作
from 接続.Kaggle操作 import 提出可能性


def _提出(ref, date, status, public_score, error_description=None):
    return SimpleNamespace(
        ref=ref,
        date=date,
        status=SimpleNamespace(name=status),
        public_score=public_score,
        error_description=error_description,
    )


class _API:
    def __init__(self, rows):
        self.rows = rows

    def competition_submissions(self, competition, page_size):
        assert competition == "arc-prize-2026-arc-agi-2"
        assert page_size == 100
        return self.rows


def test_24時間経過した前日完了のゼロ点は提出ゲートを通る():
    api = _API([_提出(7, datetime(2026, 10, 23, 0, 1), "COMPLETE", "0.00")])

    result = 提出可能性(api, datetime(2026, 10, 24, 0, 1, tzinfo=timezone.utc))

    assert result["許可"] is True
    assert result["latest_public_score"] == "0.00"


def test_24時間未満ならUTC日付が変わっても提出できない():
    api = _API([_提出(7, datetime(2026, 10, 24, 0, 12, 39, 127000, tzinfo=timezone.utc), "COMPLETE", "0.00")])

    result = 提出可能性(api, datetime(2026, 10, 25, 0, 12, 39, 126000, tzinfo=timezone.utc))

    assert result["許可"] is False
    assert "24時間未満" in result["理由"]
    assert result["next_allowed_at_utc"] == "2026-10-25T00:12:39.127000+00:00"


def test_24時間ちょうどで提出ゲートを通る():
    submitted_at = datetime(2026, 10, 24, 0, 12, 39, 127000, tzinfo=timezone.utc)
    api = _API([_提出(7, submitted_at, "COMPLETE", "0.00")])

    result = 提出可能性(api, submitted_at + timedelta(hours=24))

    assert result["許可"] is True


def test_同一UTC日内の提出があれば二重提出を止める():
    api = _API([_提出(8, datetime(2026, 10, 24, 0, 1), "COMPLETE", "0.00")])

    result = 提出可能性(api, datetime(2026, 10, 24, 23, 59, tzinfo=timezone.utc))

    assert result["許可"] is False
    assert result["today_submission_refs"] == [8]


def test_直近提出が採点待ちなら日付が変わっても止める():
    api = _API([_提出(9, datetime(2026, 10, 23, 12, 0), "PENDING", "")])

    result = 提出可能性(api, datetime(2026, 10, 24, 12, 1, tzinfo=timezone.utc))

    assert result["許可"] is False
    assert "採点が完了" in result["理由"]


def test_COMPLETEでも空スコアは提出前に採点経路確認へ戻す():
    api = _API([_提出(10, datetime(2026, 10, 23, 12, 0), "COMPLETE", "")])

    result = 提出可能性(api, datetime(2026, 10, 24, 12, 1, tzinfo=timezone.utc))

    assert result["許可"] is False
    assert "数値スコアが未取得" in result["理由"]


def test_明示されたNotebook_timeoutは24時間後に再試行を許可する():
    submitted_at = datetime(2026, 10, 25, 0, 14, 45, tzinfo=timezone.utc)
    api = _API([
        _提出(
            12,
            submitted_at,
            "COMPLETE",
            "",
            "Your submission notebook exceeded the allowed runtime.",
        )
    ])

    result = 提出可能性(api, submitted_at + timedelta(hours=24))

    assert result["許可"] is True
    assert result["scoreless_timeout_retry"] is True


def test_明示されたNotebook_timeoutも24時間未満なら再試行できない():
    submitted_at = datetime(2026, 10, 25, 0, 14, 45, tzinfo=timezone.utc)
    api = _API([
        _提出(
            13,
            submitted_at,
            "COMPLETE",
            None,
            "Notebook Timeout: exceeded the allowed runtime.",
        )
    ])

    result = 提出可能性(api, submitted_at + timedelta(hours=24) - timedelta(seconds=1))

    assert result["許可"] is False
    assert "24時間未満" in result["理由"]


def test_曖昧な失敗詳細の空スコアは再試行許可にならない():
    api = _API([
        _提出(
            14,
            datetime(2026, 10, 25, 0, 14, 45, tzinfo=timezone.utc),
            "COMPLETE",
            None,
            "Notebook threw an exception.",
        )
    ])

    result = 提出可能性(api, datetime(2026, 10, 26, 0, 14, 45, tzinfo=timezone.utc))

    assert result["許可"] is False
    assert result["scoreless_timeout_retry"] is False
    assert "数値スコアが未取得" in result["理由"]


def test_初回提出用に履歴が空なら枠を許可する():
    result = 提出可能性(_API([]), datetime(2026, 10, 24, 12, 1, tzinfo=timezone.utc))

    assert result["許可"] is True


def test_提出操作は同一UTC日の履歴を見つけるとAPI送信前に停止する(monkeypatch):
    now = datetime.now(timezone.utc)
    api = _API([_提出(11, now, "COMPLETE", "0.00")])
    monkeypatch.setattr(Kaggle操作, "記録確認", lambda record: None)
    api.competition_submit_code = lambda **kwargs: pytest.fail("submission API must not run")

    with pytest.raises(Kaggle操作.操作エラー, match="UTC日次提出枠"):
        Kaggle操作.提出(api, {}, "guard-test")

