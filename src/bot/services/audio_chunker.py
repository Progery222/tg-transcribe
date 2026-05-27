import asyncio
from pathlib import Path

import structlog

from bot.services.audio_pipeline import FfmpegError, _run_ffmpeg

log = structlog.get_logger(__name__)


CHUNK_MAX_BYTES = 24 * 1024 * 1024
CHUNK_SECONDS = 30 * 60


async def _probe_duration(src_path: Path) -> float | None:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(src_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    try:
        return float(out.decode().strip())
    except ValueError:
        return None


async def split_if_needed(
    src_path: Path,
    *,
    max_bytes: int = CHUNK_MAX_BYTES,
    chunk_seconds: int = CHUNK_SECONDS,
) -> list[Path]:
    """Return ``[src_path]`` if it fits ``max_bytes``; otherwise re-encode-split."""
    size = await asyncio.to_thread(lambda: src_path.stat().st_size)
    if size <= max_bytes:
        return [src_path]

    work_dir = src_path.parent / "chunks"
    await asyncio.to_thread(work_dir.mkdir, parents=True, exist_ok=True)
    pattern = work_dir / "chunk_%03d.ogg"
    try:
        await _run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(src_path),
                "-f",
                "segment",
                "-segment_time",
                str(chunk_seconds),
                "-reset_timestamps",
                "1",
                "-c",
                "copy",
                str(pattern),
            ]
        )
    except FfmpegError as e:
        log.warning("chunker_copy_failed_fallback_reencode", err=str(e))
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
                "-f",
                "segment",
                "-segment_time",
                str(chunk_seconds),
                "-reset_timestamps",
                "1",
                str(pattern),
            ]
        )

    chunks = sorted(await asyncio.to_thread(lambda: list(work_dir.glob("chunk_*.ogg"))))
    if not chunks:
        raise FfmpegError("chunker produced no output files")
    log.info("audio_chunked", source_size=size, chunks=len(chunks))
    return chunks
