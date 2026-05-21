# tests/test_profile_manager.py
import pytest
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
from tts import ProfileManager


@pytest.fixture
def temp_profiles_dir():
    """Create a temporary profiles directory."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def valid_audio_file(temp_profiles_dir):
    """Create a mock valid audio file."""
    audio_path = temp_profiles_dir / "test_audio.wav"
    audio_path.write_bytes(b"RIFF....wave" + b"\x00" * 100)
    return audio_path


class TestAddProfile:
    """Tests for add_profile method."""

    @patch("tts.AudioSegment")
    def test_add_profile_creates_files(self, mock_audio_segment, temp_profiles_dir, valid_audio_file):
        """Test that add_profile creates both JSON and audio file."""
        mock_audio_segment.from_file.return_value = Mock()
        pm = ProfileManager(profiles_dir=temp_profiles_dir)

        result = pm.add_profile("test_voice", str(valid_audio_file))

        from datetime import date
        assert result["name"] == "test_voice"
        assert result["audio_file"] == "test_voice.mp3"
        assert result["created_at"] == date.today().isoformat()

        json_path = temp_profiles_dir / "test_voice.json"
        assert json_path.exists()
        with open(json_path, encoding="utf-8") as f:
            profile = json.load(f)
            assert profile["name"] == "test_voice"
            assert profile["audio_file"] == "test_voice.mp3"

        audio_dest = temp_profiles_dir / "test_voice.mp3"
        assert audio_dest.exists()

    @patch("tts.AudioSegment")
    def test_add_profile_rejects_duplicate(self, mock_audio_segment, temp_profiles_dir, valid_audio_file):
        """Test that add_profile raises error for duplicate profile."""
        mock_audio_segment.from_file.return_value = Mock()
        pm = ProfileManager(profiles_dir=temp_profiles_dir)
        pm.add_profile("duplicate", str(valid_audio_file))

        with pytest.raises(ValueError, match="already exists"):
            pm.add_profile("duplicate", str(valid_audio_file))

    @patch("tts.AudioSegment")
    def test_add_profile_rejects_invalid_audio(self, mock_audio_segment, temp_profiles_dir):
        """Test that add_profile raises error for invalid audio file."""
        mock_audio_segment.from_file.side_effect = Exception("Cannot decode")
        pm = ProfileManager(profiles_dir=temp_profiles_dir)

        invalid_path = temp_profiles_dir / "invalid.wav"
        invalid_path.write_bytes(b"not audio data")

        with pytest.raises(ValueError, match="Invalid audio"):
            pm.add_profile("bad_profile", str(invalid_path))


class TestListProfiles:
    """Tests for list_profiles method."""

    def test_list_profiles(self, temp_profiles_dir):
        """Test listing all profiles."""
        pm = ProfileManager(profiles_dir=temp_profiles_dir)

        p1 = {"name": "alice", "audio_file": "alice.wav", "created_at": "2026-05-14"}
        p2 = {"name": "bob", "audio_file": "bob.mp3", "created_at": "2026-05-14"}

        (temp_profiles_dir / "alice.json").write_text(json.dumps(p1), encoding="utf-8")
        (temp_profiles_dir / "bob.json").write_text(json.dumps(p2), encoding="utf-8")

        profiles = pm.list_profiles()

        assert len(profiles) == 2
        assert profiles[0]["name"] == "alice"
        assert profiles[1]["name"] == "bob"

    def test_list_profiles_empty(self, temp_profiles_dir):
        """Test listing returns empty list when no profiles exist."""
        pm = ProfileManager(profiles_dir=temp_profiles_dir)
        profiles = pm.list_profiles()
        assert profiles == []


class TestDeleteProfile:
    """Tests for delete_profile method."""

    @patch("tts.AudioSegment")
    def test_delete_profile(self, mock_audio_segment, temp_profiles_dir, valid_audio_file):
        """Test deleting a profile removes both JSON and audio file."""
        mock_audio_segment.from_file.return_value = Mock()
        pm = ProfileManager(profiles_dir=temp_profiles_dir)
        pm.add_profile("to_delete", str(valid_audio_file))

        pm.delete_profile("to_delete")

        assert not (temp_profiles_dir / "to_delete.json").exists()
        assert not (temp_profiles_dir / "to_delete.wav").exists()

    def test_delete_profile_nonexistent(self, temp_profiles_dir):
        """Test deleting nonexistent profile raises FileNotFoundError."""
        pm = ProfileManager(profiles_dir=temp_profiles_dir)

        with pytest.raises(FileNotFoundError, match="not found"):
            pm.delete_profile("nonexistent")


class TestGetAudioPath:
    """Tests for get_audio_path method."""

    @patch("tts.AudioSegment")
    def test_get_audio_path(self, mock_audio_segment, temp_profiles_dir, valid_audio_file):
        """Test getting audio path for existing profile."""
        mock_audio_segment.from_file.return_value = Mock()
        pm = ProfileManager(profiles_dir=temp_profiles_dir)
        pm.add_profile("voice1", str(valid_audio_file))

        audio_path = pm.get_audio_path("voice1")

        assert audio_path == temp_profiles_dir / "voice1.mp3"
        assert audio_path.exists()

    def test_get_audio_path_missing_profile(self, temp_profiles_dir):
        """Test getting audio path for nonexistent profile raises error."""
        pm = ProfileManager(profiles_dir=temp_profiles_dir)

        with pytest.raises(FileNotFoundError, match="not found"):
            pm.get_audio_path("nonexistent")


class TestProfileExists:
    """Tests for profile_exists method."""

    @patch("tts.AudioSegment")
    def test_profile_exists(self, mock_audio_segment, temp_profiles_dir, valid_audio_file):
        """Test checking if profile exists."""
        mock_audio_segment.from_file.return_value = Mock()
        pm = ProfileManager(profiles_dir=temp_profiles_dir)

        assert not pm.profile_exists("new_profile")

        pm.add_profile("new_profile", str(valid_audio_file))

        assert pm.profile_exists("new_profile")

    def test_profile_exists_nonexistent(self, temp_profiles_dir):
        """Test profile_exists returns False for nonexistent profile."""
        pm = ProfileManager(profiles_dir=temp_profiles_dir)
        assert not pm.profile_exists("nonexistent")


class TestAutoCreateProfilesDir:
    """Tests for automatic profile directory creation."""

    @patch("tts.AudioSegment")
    def test_auto_create_profiles_dir(self, mock_audio_segment, temp_profiles_dir, valid_audio_file):
        """Test that profiles directory is created automatically."""
        mock_audio_segment.from_file.return_value = Mock()
        new_dir = temp_profiles_dir / "new_profiles_dir"
        pm = ProfileManager(profiles_dir=new_dir)

        assert not new_dir.exists()

        pm.add_profile("test", str(valid_audio_file))

        assert new_dir.exists()
        assert (new_dir / "test.json").exists()