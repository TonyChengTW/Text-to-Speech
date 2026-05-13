# tests/test_audio.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from tts import concatenate_wav, convert_to_mp3


def test_concatenate_wav_empty():
    """Test concatenating empty list returns None."""
    result = concatenate_wav([])
    assert result is None


@patch("tts.BytesIO")
@patch("tts.AudioSegment")
def test_concatenate_wav(mock_audio_segment, mock_bytesio):
    """Test concatenating multiple WAV files."""
    mock_seg1 = MagicMock()
    mock_seg2 = MagicMock()
    mock_audio_segment.from_file.side_effect = [mock_seg1, mock_seg2]
    mock_output = MagicMock()
    mock_bytesio.return_value = mock_output

    wav1 = b"fake_wav_1"
    wav2 = b"fake_wav_2"

    result = concatenate_wav([wav1, wav2])

    assert result is not None
    assert mock_audio_segment.from_file.call_count == 2
    mock_output.getvalue.assert_called_once()


@patch("tts.AudioSegment")
def test_convert_to_mp3(mock_audio_segment):
    """Test converting WAV to MP3."""
    mock_wav = MagicMock()
    mock_wav.frame_rate = 24000
    mock_audio_segment.from_file.return_value = mock_wav
    mock_wav.export = Mock()

    result = convert_to_mp3(b"fake_wav", "/tmp/output.mp3", "192k", 24000)

    assert result is not None
    mock_wav.export.assert_called_once()
    mock_audio_segment.from_file.assert_called_once()


@patch("tts.AudioSegment")
def test_convert_to_mp3_resample(mock_audio_segment):
    """Test converting WAV to MP3 with different sample rate."""
    mock_wav = MagicMock()
    mock_wav.frame_rate = 44100  # Different from target
    mock_resampled = MagicMock()
    mock_wav.set_frame_rate.return_value = mock_resampled
    mock_audio_segment.from_file.return_value = mock_wav

    result = convert_to_mp3(b"fake_wav", "/tmp/output.mp3", "192k", 24000)

    assert result is not None
    mock_wav.set_frame_rate.assert_called_once_with(24000)
    mock_resampled.export.assert_called_once()
