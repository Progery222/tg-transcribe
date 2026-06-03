from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot.handlers.callbacks as cb
from bot.keyboards.inline import CB_DIGEST_ONE_PREFIX

pytestmark = pytest.mark.usefixtures("tmp_db")


def _query(data: str) -> object:
    return SimpleNamespace(
        data=data,
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )


async def test_on_digest_one_runs_for_selected_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    run_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(cb, "run_digest_now", run_mock)
    query = _query(f"{CB_DIGEST_ONE_PREFIX}-100500")
    bot = SimpleNamespace()
    await cb.on_digest_one(query, bot)
    run_mock.assert_awaited_once_with(bot, only_chat_id=-100500)
    query.answer.assert_awaited()
    query.message.edit_text.assert_awaited()


async def test_on_digest_all_runs_for_every_group(monkeypatch: pytest.MonkeyPatch) -> None:
    run_mock = AsyncMock(return_value=3)
    monkeypatch.setattr(cb, "run_digest_now", run_mock)
    query = _query("dg:all")
    bot = SimpleNamespace()
    await cb.on_digest_all(query, bot)
    run_mock.assert_awaited_once_with(bot, only_chat_id=None)


async def test_on_digest_cancel_edits_and_skips_run(monkeypatch: pytest.MonkeyPatch) -> None:
    run_mock = AsyncMock()
    monkeypatch.setattr(cb, "run_digest_now", run_mock)
    query = _query("dg:cancel")
    await cb.on_digest_cancel(query)
    run_mock.assert_not_awaited()
    query.message.edit_text.assert_awaited_once()
