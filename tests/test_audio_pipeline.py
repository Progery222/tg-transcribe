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


def _generate_voice_ogg(target: Path) -> None:
    """Generate a 1-second OGG/Opus file."""
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
            "anullsrc=channel_layout=mono:sample_rate=16000",
            "-t",
            "1",
            "-c:a",
            "libopus",
            "-b:a",
            "16k",
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


@pytest.fixture(scope="session")
def sample_voice(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not FFMPEG_AVAILABLE:
        pytest.skip("ffmpeg not on PATH")
    path = tmp_path_factory.mktemp("media") / "voice.ogg"
    _generate_voice_ogg(path)
    return path


async def test_unsupported_content_type_raises(tmp_path: Path) -> None:
    placeholder = tmp_path / "x.bin"
    placeholder.write_bytes(b"x")
    with pytest.raises(ValueError):
        await prepare_payload("photo", placeholder, None)


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg not installed")
async def test_voice_normalizes_to_opus(sample_voice: Path, tmp_path: Path) -> None:
    payload = await prepare_payload("voice", sample_voice, "audio/ogg", work_dir=tmp_path)
    assert payload.path.exists()
    assert payload.path.suffix == ".ogg"
    assert payload.mime == "audio/ogg"
    assert payload.path.stat().st_size > 0


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg not installed")
async def test_video_extracts_to_opus(sample_mp4: Path, tmp_path: Path) -> None:
    payload = await prepare_payload("video_note", sample_mp4, "video/mp4", work_dir=tmp_path)
    assert payload.mime == "audio/ogg"
    assert payload.filename.endswith(".ogg")
    assert payload.path.exists()
    assert payload.path.stat().st_size > 0
    # OGG container begins with the "OggS" capture pattern.
    assert payload.path.read_bytes()[:4] == b"OggS"
