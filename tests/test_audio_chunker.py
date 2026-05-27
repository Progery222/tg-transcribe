import shutil
import subprocess
from pathlib import Path

import pytest

from bot.services.audio_chunker import split_if_needed

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


def _gen_opus(target: Path, *, seconds: int) -> None:
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
            str(seconds),
            "-c:a",
            "libopus",
            "-b:a",
            "16k",
            str(target),
        ],
        check=True,
    )


async def test_no_split_when_under_limit(tmp_path: Path) -> None:
    p = tmp_path / "small.ogg"
    p.write_bytes(b"x" * 100)
    out = await split_if_needed(p, max_bytes=1024)
    assert out == [p]


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg not installed")
async def test_splits_when_over_limit(tmp_path: Path) -> None:
    src = tmp_path / "long.ogg"
    _gen_opus(src, seconds=8)
    # max_bytes deliberately tiny so the small file gets split anyway
    chunks = await split_if_needed(src, max_bytes=1024, chunk_seconds=2)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.exists()
        assert chunk.stat().st_size > 0
        assert chunk.suffix == ".ogg"
