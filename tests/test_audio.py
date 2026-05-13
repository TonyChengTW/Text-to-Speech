# tests/test_audio.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from tts import concatenate_wav, convert_to_mp3


def test_concatenate_wav():
    """Test concatenating multiple WAV files."""
    # Minimal WAV header (44 bytes) + some data
    wav1 = b"RIFF" + b"\x00" * 40 + b"\x01\x02\x03\x04"
    wav2 = b"RIFF" + b"\x00" * 40 + b"\x05\x06\x07\x08"

    result = concatenate_wav([wav1, wav2])

    assert result is not None
    assert len(result) > len(wav1) + len(wav2)  # Header overhead


def test_concatenate_wav_empty():
    """Test concatenating empty list returns None."""
    result = concatenate_wav([])
    assert result is None


@patch("tts.AudioSegment")
def test_convert_to_mp3(mock_audio_segment):
    """Test converting WAV to MP3."""
    mock_wav = Mock()
    mock_audio_segment.from_wav.return_value = mock_wav
    mock_wav.export.return_value = None

    result = convert_to_mp3(b"fake_wav", "/tmp/output.mp3", "192k", 24000)

    assert result is not None
    mock_wav.export.assert_called_once()
