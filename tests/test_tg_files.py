from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import GetFile

from bot.utils.tg_files import fetch_file_path

_API_PATH = "/var/lib/telegram-bot-api/token-dir/videos/file_1.mp4"


def _network_error() -> TelegramNetworkError:
    return TelegramNetworkError(
        method=GetFile(file_id="fid"), message="ServerDisconnectedError: Server disconnected"
    )


def _bad_request(text: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=GetFile(file_id="fid"), message=text)


@pytest.fixture
def local_file(tmp_path: Path) -> Path:
    p = tmp_path / "token-dir" / "videos" / "file_1.mp4"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"video")
    return p


async def test_fetch_retries_after_network_error(tmp_path: Path, local_file: Path) -> None:
    bot = SimpleNamespace(
        get_file=AsyncMock(side_effect=[_network_error(), SimpleNamespace(file_path=_API_PATH)])
    )

    path, is_temp = await fetch_file_path(
        bot, "fid", local_root=str(tmp_path), retry_delays=(0, 0)
    )

    assert path == local_file
    assert is_temp is False
    assert bot.get_file.await_count == 2


async def test_fetch_retries_temporarily_unavailable(tmp_path: Path, local_file: Path) -> None:
    unavailable = _bad_request(
        "Telegram server says - Bad Request: wrong file_id or the file is temporarily unavailable"
    )
    bot = SimpleNamespace(
        get_file=AsyncMock(side_effect=[unavailable, SimpleNamespace(file_path=_API_PATH)])
    )

    path, _ = await fetch_file_path(bot, "fid", local_root=str(tmp_path), retry_delays=(0, 0))

    assert path == local_file
    assert bot.get_file.await_count == 2


async def test_fetch_gives_up_after_all_attempts(tmp_path: Path) -> None:
    bot = SimpleNamespace(get_file=AsyncMock(side_effect=_network_error()))

    with pytest.raises(TelegramNetworkError):
        await fetch_file_path(bot, "fid", local_root=str(tmp_path), retry_delays=(0, 0))

    assert bot.get_file.await_count == 3


async def test_fetch_does_not_retry_permanent_bad_request(tmp_path: Path) -> None:
    bot = SimpleNamespace(
        get_file=AsyncMock(side_effect=_bad_request("Bad Request: file is too big"))
    )

    with pytest.raises(TelegramBadRequest):
        await fetch_file_path(bot, "fid", local_root=str(tmp_path), retry_delays=(0, 0))

    assert bot.get_file.await_count == 1


async def test_failed_download_leaves_no_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tempfile

    import aiohttp

    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_dir))
    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=SimpleNamespace(file_path="videos/file_1.mp4")),
        download_file=AsyncMock(side_effect=aiohttp.ClientPayloadError("cut")),
    )

    with pytest.raises(aiohttp.ClientPayloadError):
        await fetch_file_path(bot, "fid", retry_delays=(0, 0))

    assert bot.download_file.await_count == 3
    assert list(temp_dir.iterdir()) == []
