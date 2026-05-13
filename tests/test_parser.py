# tests/test_parser.py
import pytest
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


@patch("tts.MiMoClient")
@patch("tts.concatenate_wav")
@patch("tts.convert_to_mp3")
def test_main_orchestration(mock_mp3, mock_concat, mock_client):
    """Test main orchestration flow."""
    mock_instance = Mock()
    mock_client.return_value = mock_instance
    mock_instance.synthesize.return_value = b"fake_wav"
    mock_concat.return_value = b"combined_wav"
    mock_mp3.return_value = Path("/tmp/output.mp3")

    from tts import main
    import sys

    test_args = ["tts.py", "sample.txt", "--api-key", "test-key"]
    with patch.object(sys, "argv", test_args):
        mock_content = "[voice:冰糖]\n你好"
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value=mock_content):
            main()

    mock_instance.synthesize.assert_called_once()
    mock_concat.assert_called_once()
    mock_mp3.assert_called_once()
