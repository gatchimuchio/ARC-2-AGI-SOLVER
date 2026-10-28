from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from 接続 import Kaggle操作


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def submission(status, score=None, error=None, date=NOW):
    return SimpleNamespace(ref=1, date=date, status=SimpleNamespace(name=status),
                           public_score=score, error_description=error)


class API:
    def __init__(self, rows, quota=1):
        self.rows, self.quota = rows, quota

    def competition_submissions(self, competition, page_size):
        return self.rows

    def competition_get_submission_limits(self, competition):
        if isinstance(self.quota, Exception):
            raise self.quota
        return SimpleNamespace(num_allowed_now=self.quota)


@pytest.mark.parametrize(("row", "state", "quota", "allowed"), [
    (submission("COMPLETE", None, "Notebook Timeout"), "TERMINAL_ERROR_NOT_SCORED", 1, True),
    (submission("ERROR"), "TERMINAL_ERROR_NOT_SCORED", 1, True),
    (submission("COMPLETE", "0.00", "Notebook Timeout"), "TERMINAL_ERROR_NOT_SCORED", 1, True),
    (submission("COMPLETE", None, "Notebook Timeout"), "TERMINAL_ERROR_NOT_SCORED", 0, False),
    (submission("PENDING"), "IN_PROGRESS", 1, False),
    (submission("COMPLETE", "0.00"), "SCORED_ACCEPTED", 1, False),
    (submission("COMPLETE", "12.34"), "SCORED_ACCEPTED", 1, False),
    (submission("COMPLETE"), "UNVERIFIED", 1, False),
])
def test_official_status_and_quota(row, state, quota, allowed):
    result = Kaggle操作.提出可能性(API([row], quota), NOW)
    assert result["latest_score_state"] == state
    assert result["許可"] is allowed


@pytest.mark.parametrize("quota", [None, -1, True, "1", RuntimeError("unavailable")])
def test_unavailable_or_invalid_quota_fails_closed(quota):
    result = Kaggle操作.提出可能性(API([], quota), NOW)
    assert result["許可"] is False


def test_scored_previous_day_can_submit_if_official_quota_allows():
    previous = submission("COMPLETE", "0.00", date=datetime(2026, 10, 27, 23, tzinfo=timezone.utc))
    assert Kaggle操作.提出可能性(API([previous], 1), NOW)["許可"] is True


def test_denied_gate_never_calls_submit(monkeypatch):
    api = API([submission("PENDING")], 1)
    monkeypatch.setattr(Kaggle操作, "記録確認", lambda record: None)
    api.competition_submit_code = lambda **kwargs: pytest.fail("must not submit")
    with pytest.raises(Kaggle操作.操作エラー):
        Kaggle操作.提出(api, {}, "guard-test")
