import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


class FfmpegError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioPayload:
    """Audio normalized to Opus 16k mono OGG, ready for transcribers."""

    path: Path
    mime: str
    filename: str


FFMPEG_TIMEOUT_SECONDS = 600.0


async def _run_ffmpeg(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(FFMPEG_TIMEOUT_SECONDS):
            _, stderr = await proc.communicate()
    except TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise FfmpegError("ffmpeg timeout") from e
    if proc.returncode != 0:
        raise FfmpegError(
            f"ffmpeg exit={proc.returncode}: {stderr.decode('utf-8', errors='replace')[:300]}"
        )


async def normalize_to_opus(src_path: Path, *, work_dir: Path | None = None) -> Path:
    """Re-encode any media to Opus 16 kbps mono OGG.

    Output is small (~7 MB per hour of speech) — fits OpenAI's 25 MB and Gemini's 20 MB
    inline limits with room to spare for most realistic recordings. For very long
    inputs callers should still run :func:`audio_chunker.split_if_needed`.
    """
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="tg-tx-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path = work_dir / "audio.ogg"
    await _run_ffmpeg(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src_path),
            "-vn",
            "-ac",
            "1",
            "-c:a",
            "libopus",
            "-b:a",
            "16k",
            "-application",
            "voip",
            str(out_path),
        ]
    )
    return out_path


async def prepare_payload(
    content_type: str,
    src_path: Path,
    src_mime: str | None,
    *,
    work_dir: Path | None = None,
) -> AudioPayload:
    """Convert any downloaded Telegram media into a uniform Opus payload."""
    if content_type not in ("voice", "audio", "video_note", "video"):
        raise ValueError(f"unsupported content type: {content_type}")
    out_path = await normalize_to_opus(src_path, work_dir=work_dir)
    return AudioPayload(path=out_path, mime="audio/ogg", filename=f"{content_type}.ogg")
