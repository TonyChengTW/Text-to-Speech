# tests/test_api.py
import pytest
from unittest.mock import Mock, patch
from tts import MiMoClient, Segment


def test_client_initialization():
    """Test client initializes with correct parameters."""
    client = MiMoClient(api_key="test-key", model="mimo-v2.5-tts")
    assert client.api_key == "test-key"
    assert client.model == "mimo-v2.5-tts"
    assert client.base_url == "https://api.xiaomimimo.com/v1"


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
    assert call_args[1]["headers"]["api-key"] == "test-key"
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
