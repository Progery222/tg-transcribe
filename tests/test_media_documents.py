from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from aiogram.types import Chat, Document, Message

import bot.handlers.voice as voice
from bot.utils.tg_files import extract_media_info


def _doc_msg(mime: str | None, file_name: str | None) -> object:
    doc = SimpleNamespace(file_id="dfid", file_size=2048, mime_type=mime, file_name=file_name)
    return SimpleNamespace(voice=None, video_note=None, audio=None, video=None, document=doc)


@pytest.mark.parametrize(
    ("mime", "file_name"),
    [
        ("video/mp4", "IMG_0001.MP4"),
        ("video/quicktime", "clip.mov"),
        ("audio/x-m4a", "meeting.m4a"),
        ("audio/ogg", "voice.ogg"),
        ("application/octet-stream", "Recording 12.m4a"),
        (None, "call.WAV"),
    ],
)
def test_media_document_is_transcribable(mime: str | None, file_name: str | None) -> None:
    assert extract_media_info(_doc_msg(mime, file_name)) == ("document", "dfid", 2048, mime)


@pytest.mark.parametrize(
    ("mime", "file_name"),
    [
        ("application/pdf", "report.pdf"),
        ("image/jpeg", "photo.jpg"),
        ("application/zip", "archive.zip"),
        (None, None),
    ],
)
def test_non_media_document_is_ignored(mime: str | None, file_name: str | None) -> None:
    assert extract_media_info(_doc_msg(mime, file_name)) is None


def _tg_message(document: Document) -> Message:
    return Message(
        message_id=1,
        date=datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
        chat=Chat(id=-1001, type="supergroup", title="Team"),
        document=document,
    )


async def test_router_accepts_media_document_in_group() -> None:
    message = _tg_message(
        Document(file_id="dfid", file_unique_id="u1", mime_type="video/mp4", file_name="a.mp4")
    )
    handler = voice.router.message.handlers[0]

    passed, _ = await handler.check(message)

    assert passed is True
