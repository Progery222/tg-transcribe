from bot.utils.text_split import split_for_telegram


def test_short_text_single_chunk() -> None:
    assert split_for_telegram("hello world") == ["hello world"]


def test_splits_long_text_on_word_boundary() -> None:
    text = ("word " * 1000).strip()  # ~5000 chars
    chunks = split_for_telegram(text, max_chunk=100)
    assert all(len(c) <= 100 for c in chunks)
    # No chunk should split a word — every chunk is purely "word" tokens.
    for c in chunks:
        for token in c.split():
            assert token == "word"


def test_splits_without_spaces_falls_back_to_hard_cut() -> None:
    text = "a" * 250
    chunks = split_for_telegram(text, max_chunk=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == text
