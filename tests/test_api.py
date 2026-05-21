# tests/test_api.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from tts import MiMoClient, Segment, ProfileManager


def test_client_initialization():
    """Test client initializes with correct parameters."""
    client = MiMoClient(api_key="test-key", model="mimo-v2.5-tts")
    assert client.api_key == "test-key"
    assert client.model == "mimo-v2.5-tts"
    assert client.base_url == "https://token-plan-cn.xiaomimimo.com/v1"


@patch("tts.requests.post")
def test_synthesize_with_style(mock_post):
    """Test synthesize sends correct request with style."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.return_value = mock_response

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style="用台灣口音", text="你好")
    result = client.synthesize(segment)

    assert result is not None
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
    assert call_args[1]["json"]["messages"][0]["role"] == "user"
    assert call_args[1]["json"]["messages"][1]["role"] == "assistant"


@patch("tts.requests.post")
def test_synthesize_without_style(mock_post):
    """Test synthesize sends correct request without style."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.return_value = mock_response

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style=None, text="你好")
    result = client.synthesize(segment)

    assert result is not None
    call_args = mock_post.call_args
    # Should have only assistant message, no user message
    assert len(call_args[1]["json"]["messages"]) == 1
    assert call_args[1]["json"]["messages"][0]["role"] == "assistant"


@patch("tts.requests.post")
def test_synthesize_api_error(mock_post):
    """Test synthesize handles API errors."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": "Unauthorized"}
    mock_post.return_value = mock_response

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style=None, text="你好")

    with pytest.raises(Exception) as exc_info:
        client.synthesize(segment)
    assert "401" in str(exc_info.value)


@patch("tts.requests.post")
def test_synthesize_retry_on_server_error(mock_post):
    """Test synthesize retries on server errors."""
    # First call fails with 500, second succeeds
    mock_response_fail = Mock()
    mock_response_fail.status_code = 500
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.side_effect = [mock_response_fail, mock_response_success]

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style=None, text="你好")
    result = client.synthesize(segment)

    assert result is not None
    assert mock_post.call_count == 2


@patch("tts.requests.post")
def test_synthesize_clone_segment(mock_post):
    """Clone segments use voiceclone model with base64 audio."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "YWJj"}}}]
    }
    mock_post.return_value = mock_response

    mock_pm = Mock()
    mock_pm.get_audio_path.return_value = Path("/fake/path/test.mp3")

    client = MiMoClient(api_key="test-key", profile_manager=mock_pm)
    segment = Segment(voice="clone:test", style=None, text="測試")

    mock_file = MagicMock()
    mock_file.read.return_value = b"fake audio data"
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=False)
    with patch("builtins.open", return_value=mock_file):
        result = client.synthesize(segment)

    assert result is not None
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["model"] == "mimo-v2.5-tts-voiceclone"
    voice_value = call_kwargs.kwargs["json"]["audio"]["voice"]
    assert voice_value.startswith("data:audio/mpeg;base64,")


@patch("tts.requests.post")
def test_synthesize_builtin_voice_still_works(mock_post):
    """Builtin voice segments still use standard model."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "YWJj"}}}]
    }
    mock_post.return_value = mock_response

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style=None, text="測試")

    result = client.synthesize(segment)

    assert result is not None
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"]["model"] == "mimo-v2.5-tts"
    assert mock_post.call_args.kwargs["json"]["audio"]["voice"] == "冰糖"


from tts import GeminiTTSClient, TTSClientFactory
import base64

@patch("tts.requests.post")
@patch("tts.GeminiTTSClient._pcm_to_wav")
def test_gemini_synthesize_success(mock_pcm_to_wav, mock_post):
    """Test Gemini synthesize decodes base64 and converts to WAV."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "inlineData": {
                        "data": "ZmFrZV9wY21fZGF0YQ=="
                    }
                }]
            }
        }]
    }
    mock_post.return_value = mock_response
    mock_pcm_to_wav.return_value = b"fake_wav_data"

    client = GeminiTTSClient(api_key="gemini-key")
    segment = Segment(voice="冰糖", style=None, text="測試")
    result = client.synthesize(segment)

    assert result == b"fake_wav_data"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"]["x-goog-api-key"] == "gemini-key"
    assert mock_post.call_args.kwargs["json"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Aoede"


@patch("tts.requests.post")
def test_gemini_rejects_clone(mock_post):
    """Test Gemini rejects clone segments."""
    client = GeminiTTSClient(api_key="gemini-key")
    segment = Segment(voice="clone:test", style=None, text="測試")

    with pytest.raises(ValueError) as exc_info:
        client.synthesize(segment)
    
    assert "not supported" in str(exc_info.value).lower()
    mock_post.assert_not_called()


@patch("tts.requests.post")
@patch("tts.GeminiTTSClient._pcm_to_wav")
def test_gemini_style_injection(mock_pcm_to_wav, mock_post):
    """Test style is prepended to text."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"inlineData": {"data": "YWJj"}}]}}]
    }
    mock_post.return_value = mock_response

    client = GeminiTTSClient(api_key="gemini-key")
    segment = Segment(voice="冰糖", style="開心", text="測試")
    client.synthesize(segment)

    call_args = mock_post.call_args
    assert call_args.kwargs["json"]["contents"][0]["parts"][0]["text"] == "開心。測試"


def test_factory_creates_mimo_client():
    client = TTSClientFactory.create(model="mimo-v2.5-tts", mimo_api_key="mimo-key", gemini_api_key=None)
    assert isinstance(client, MiMoClient)
    assert client.api_key == "mimo-key"


def test_factory_creates_gemini_client():
    client = TTSClientFactory.create(model="gemini-2.5-flash-preview-tts", mimo_api_key=None, gemini_api_key="gemini-key")
    assert isinstance(client, GeminiTTSClient)
    assert client.api_key == "gemini-key"


def test_factory_missing_mimo_key():
    with pytest.raises(ValueError) as exc:
        TTSClientFactory.create(model="mimo-v2.5-tts", mimo_api_key=None, gemini_api_key="gemini-key")
    assert "TTS_API_KEY" in str(exc.value)


def test_factory_missing_gemini_key():
    with pytest.raises(ValueError) as exc:
        TTSClientFactory.create(model="gemini-2.5-flash-preview-tts", mimo_api_key="mimo-key", gemini_api_key=None)
    assert "GEMINI_API_KEY" in str(exc.value)


def test_factory_unknown_model():
    with pytest.raises(ValueError) as exc:
        TTSClientFactory.create(model="invalid-model", mimo_api_key="mimo-key", gemini_api_key="gemini-key")
    assert "Unknown model 'invalid-model'" in str(exc.value)
