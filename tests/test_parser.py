# tests/test_parser.py
import pytest
import sys
from unittest.mock import patch, Mock
from pathlib import Path
from tts import parse_text_file, Segment


def test_parse_simple_segment():
    """Test parsing a simple segment with voice and style."""
    text = "[voice:冰糖]\n[style:用台灣口音]\n你好，歡迎使用。"
    segments = parse_text_file(text)
    assert len(segments) == 1
    assert segments[0].voice == "冰糖"
    assert segments[0].style == "用台灣口音"
    assert segments[0].text == "你好，歡迎使用。"


def test_parse_multiple_segments():
    """Test parsing multiple segments."""
    text = "[voice:冰糖]\n你好\n\n[voice:苏打]\n歡迎回來"
    segments = parse_text_file(text)
    assert len(segments) == 2
    assert segments[0].voice == "冰糖"
    assert segments[1].voice == "苏打"


def test_parse_without_voice():
    """Test segment without voice uses default."""
    text = "[style:用台灣口音]\n你好"
    segments = parse_text_file(text)
    assert segments[0].voice == "mimo_default"
    assert segments[0].style == "用台灣口音"


def test_parse_without_style():
    """Test segment without style has None style."""
    text = "[voice:冰糖]\n你好"
    segments = parse_text_file(text)
    assert segments[0].voice == "冰糖"
    assert segments[0].style is None


def test_parse_with_inline_tags():
    """Test parsing text with inline tags."""
    text = "[voice:冰糖]\n(开心)真的嗎？[大笑]太好了！"
    segments = parse_text_file(text)
    assert segments[0].text == "(开心)真的嗎？[大笑]太好了！"


def test_parse_skips_comments():
    """Test that # comment lines are skipped."""
    text = "# 這是註釋\n[voice:冰糖]\n# 另一個註釋\n你好"
    segments = parse_text_file(text)
    assert len(segments) == 1
    assert segments[0].text == "你好"


def test_parse_skips_blank_lines():
    """Test that blank lines are skipped."""
    text = "[voice:冰糖]\n\n\n你好"
    segments = parse_text_file(text)
    assert segments[0].text == "你好"


def test_parse_empty_file():
    """Test parsing empty file returns empty list."""
    text = ""
    segments = parse_text_file(text)
    assert len(segments) == 0


def test_parse_multiple_styles_last_wins():
    """Test multiple [style:] before text, last one wins."""
    text = "[voice:冰糖]\n[style:用台灣口音]\n[style:用溫柔的語調]\n你好"
    segments = parse_text_file(text)
    assert segments[0].style == "用溫柔的語調"


def test_parse_empty_segment_skipped():
    """Test segment with header but no text is skipped."""
    text = "[voice:冰糖]\n\n[voice:苏打]\n歡迎回來"
    segments = parse_text_file(text)
    assert len(segments) == 1
    assert segments[0].voice == "苏打"


def test_parse_voice_resets_style():
    """Test that [voice:] resets style from previous segment."""
    text = "[voice:冰糖]\n[style:用台灣口音]\n你好\n\n[voice:苏打]\n歡迎回來"
    segments = parse_text_file(text)
    assert len(segments) == 2
    assert segments[0].style == "用台灣口音"
    assert segments[1].style is None  # Style should be reset


@patch("tts.requests.post")
@patch("tts.concatenate_wav")
@patch("tts.convert_to_mp3")
def test_main_orchestration(mock_mp3, mock_concat, mock_post):
    """Test main orchestration: real parse_text_file, synthesize called with correct Segment."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.return_value = mock_response
    mock_concat.return_value = b"combined_wav"
    mock_mp3.return_value = Path("/tmp/output.mp3")

    from tts import main

    content = "[voice:冰糖]\n[style:用台灣口音]\n你好"
    segments = parse_text_file(content)
    assert len(segments) == 1
    assert segments[0] == Segment(voice="冰糖", style="用台灣口音", text="你好")

    test_args = ["tts.py", "input.txt", "--api-key", "test-key"]
    with patch.object(sys, "argv", test_args), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value=content):
        main()

    mock_post.assert_called_once()
    mock_concat.assert_called_once()
    mock_mp3.assert_called_once()


@patch("tts.requests.post")
@patch("tts.concatenate_wav")
@patch("tts.convert_to_mp3")
def test_main_orchestration_multiple_segments(mock_mp3, mock_concat, mock_post):
    """Test orchestration with multiple segments calls synthesize for each."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.return_value = mock_response
    mock_concat.return_value = b"combined_wav"
    mock_mp3.return_value = Path("/tmp/output.mp3")

    from tts import main

    content = "[voice:冰糖]\n你好\n\n[voice:苏打]\n歡迎回來"
    segments = parse_text_file(content)
    assert len(segments) == 2

    test_args = ["tts.py", "input.txt", "--api-key", "test-key"]
    with patch.object(sys, "argv", test_args), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value=content):
        main()

    assert mock_post.call_count == 2


def test_main_missing_api_key():
    """Test main exits with code 1 when API key is missing."""
    from tts import main

    test_args = ["tts.py", "input.txt"]
    with patch.object(sys, "argv", test_args), \
         patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_file_not_found():
    """Test main exits with code 1 when file does not exist."""
    from tts import main

    test_args = ["tts.py", "nonexistent.txt", "--api-key", "test-key"]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_empty_file():
    """Test main exits with code 0 when file is empty."""
    from tts import main

    test_args = ["tts.py", "empty.txt", "--api-key", "test-key"]
    with patch.object(sys, "argv", test_args), \
         patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value=""):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
