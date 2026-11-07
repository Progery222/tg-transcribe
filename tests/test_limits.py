from bot.config import Settings
from bot.services.openai_transcriber import OpenAITranscriber


def test_default_max_file_size_matches_local_bot_api_limit() -> None:
    # Local Bot API server downloads files up to 2000 MB; anything below that
    # silently drops long high-quality videos as file_too_big.
    assert Settings(_env_file=None).MAX_FILE_BYTES == 2000 * 1024 * 1024


def test_openai_client_does_not_retry_on_its_own() -> None:
    # Retries are done by tenacity in OpenAITranscriber (3 attempts). SDK retries on
    # top of that multiplied a hung request to 9 x timeout (~18 min per message).
    transcriber = OpenAITranscriber(api_key="sk-test", timeout=1.0)

    assert transcriber._client.max_retries == 0
