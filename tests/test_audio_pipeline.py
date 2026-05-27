import shutil
import subprocess
from pathlib import Path

import pytest

from bot.services.audio_pipeline import prepare_payload

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def _generate_mp4(target: Path) -> None:
    """Generate a 1-second silent MP4 with an audio track using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=160x160:rate=1:color=black:duration=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=mono:sample_rate=16000",
            "-t",
            "1",
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-b:a",
            "32k",
            str(target),
        ],
        check=True,
    )


@pytest.fixture(scope="session")
def sample_mp4(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not FFMPEG_AVAILABLE:
        pytest.skip("ffmpeg not on PATH")
    path = tmp_path_factory.mktemp("media") / "note.mp4"
    _generate_mp4(path)
    return path


async def test_voice_passthrough() -> None:
    payload = await prepare_payload("voice", b"oggbytes", "audio/ogg")
    assert payload.data == b"oggbytes"
    assert payload.mime == "audio/ogg"


async def test_audio_passthrough() -> None:
    payload = await prepare_payload("audio", b"mp3bytes", "audio/mpeg")
    assert payload.data == b"mp3bytes"
    assert payload.mime == "audio/mpeg"


async def test_unsupported_content_type_raises() -> None:
    with pytest.raises(ValueError):
        await prepare_payload("photo", b"x", None)


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg not installed")
async def test_video_note_extracts_to_m4a(sample_mp4: Path) -> None:
    mp4_bytes = sample_mp4.read_bytes()  # noqa: ASYNC240 — file is local, no event loop work
    payload = await prepare_payload("video_note", mp4_bytes, "video/mp4")
    assert payload.mime == "audio/mp4"
    assert payload.filename.endswith(".m4a")
    assert len(payload.data) > 0
    # m4a/MP4 container starts with an ftyp box near the file head.
    assert b"ftyp" in payload.data[:32]
