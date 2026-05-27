MAX_CHUNK = 4000  # leaves headroom under Telegram's 4096 char message cap


def split_for_telegram(text: str, *, max_chunk: int = MAX_CHUNK) -> list[str]:
    """Split text into chunks <= max_chunk, preferring word boundaries."""
    if len(text) <= max_chunk:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_chunk:
        slice_ = remaining[:max_chunk]
        # Try to break on a whitespace boundary in the last 20% of the slice.
        boundary = slice_.rfind(" ", int(max_chunk * 0.8))
        if boundary == -1:
            boundary = max_chunk
        chunks.append(remaining[:boundary].rstrip())
        remaining = remaining[boundary:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
