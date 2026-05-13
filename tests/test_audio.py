# tests/test_audio.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from tts import concatenate_wav, convert_to_mp3


@patch("tts.AudioSegment")
def test_concatenate_wav(mock_audio_segment):
    """Test concatenating multiple WAV files."""
    mock_seg1 = Mock()
    mock_seg2 = Mock()
    mock_combined = Mock()
    mock_output = Mock()

    mock_audio_segment.from_file.side_effect = [mock_seg1, mock_seg2]
    mock_seg1.__add__ = Mock(return_value=mock_combined)

    # Patch BytesIO to return our mock
    with patch("tts.BytesIO") as mock_bytes_io:
        mock_bytes_io.return_value = mock_output
        mock_output.getvalue.return_value = b"combined_wav"

        result = concatenate_wav([b"wav1", b"wav2"])

    assert result == b"combined_wav"
    assert mock_audio_segment.from_file.call_count == 2


def test_concatenate_wav_empty():
    """Test concatenating empty list returns None."""
    result = concatenate_wav([])
    assert result is None


@patch("tts.AudioSegment")
def test_convert_to_mp3(mock_audio_segment):
    """Test converting WAV to MP3."""
    mock_wav = Mock()
    mock_audio_segment.from_file.return_value = mock_wav
    mock_wav.frame_rate = 24000
    mock_wav.export.return_value = None

    result = convert_to_mp3(b"fake_wav", "/tmp/output.mp3", "192k", 24000)

    assert result is not None
    mock_wav.export.assert_called_once()


@patch("tts.AudioSegment")
def test_convert_to_mp3_resample(mock_audio_segment):
    """Test converting WAV to MP3 with different sample rate."""
    mock_wav = Mock()
    mock_wav.frame_rate = 44100  # Different from requested sample_rate
    mock_resampled = Mock()
    mock_wav.set_frame_rate.return_value = mock_resampled
    mock_audio_segment.from_file.return_value = mock_wav

    result = convert_to_mp3(b"fake_wav", "/tmp/output.mp3", "192k", 24000)

    assert result is not None
    mock_wav.set_frame_rate.assert_called_once_with(24000)
    mock_resampled.export.assert_called_once()
