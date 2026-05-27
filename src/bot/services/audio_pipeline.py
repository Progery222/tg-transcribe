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
    """Bytes ready to send to a transcriber."""

    data: bytes
    mime: str
    filename: str


FFMPEG_TIMEOUT_SECONDS = 30.0


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


async def extract_audio_from_mp4(mp4_bytes: bytes) -> bytes:
    """Extract audio from MP4 to m4a (AAC) via temp files.

    Why temp files: MP4 input needs a seekable source (moov atom may sit at the end),
    and the ipod/m4a output muxer requires a seekable destination. Double-pipe gives
    truncated/corrupted streams that OpenAI rejects with 400 'unsupported'. Local
    files cost ~10 ms more and are bulletproof.
    """
    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / "in.mp4"
        out_path = Path(td) / "out.m4a"
        in_path.write_bytes(mp4_bytes)
        await _run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(in_path),
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                str(out_path),
            ]
        )
        return out_path.read_bytes()


async def prepare_payload(content_type: str, raw: bytes, mime: str | None) -> AudioPayload:
    """Convert downloaded Telegram media into a payload ready for transcribers.

    - voice (OGG/Opus) and audio (anything) → forward as-is.
    - video_note / video → ffmpeg-extract audio track to m4a.
    """
    if content_type == "voice":
        return AudioPayload(data=raw, mime=mime or "audio/ogg", filename="voice.ogg")
    if content_type == "audio":
        return AudioPayload(data=raw, mime=mime or "audio/mpeg", filename="audio.bin")
    if content_type in ("video_note", "video"):
        audio = await extract_audio_from_mp4(raw)
        return AudioPayload(data=audio, mime="audio/mp4", filename=f"{content_type}.m4a")
    raise ValueError(f"unsupported content type: {content_type}")
