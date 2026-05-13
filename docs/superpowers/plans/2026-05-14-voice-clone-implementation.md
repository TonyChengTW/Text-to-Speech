# Voice Clone Feature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add voice cloning support to the MiMo TTS CLI tool. Users can register audio samples as named profiles and reference them in `.txt` files using `[clone:profile_name]`.

**Architecture:** ProfileManager class handles CRUD operations on `profiles/*.json` + audio files. `parse_text_file()` gains clone tag recognition. `MiMoClient.synthesize()` branches to `voiceclone` model when `Segment.voice` starts with `clone:`. All in `tts.py` — no new files created.

**Tech Stack:** Python 3.10+, pydub, requests, existing tts.py infrastructure

---

## Task 1: ProfileManager Class

**Files:**
- Modify: `tts.py:42-72` (after the existing Segment dataclass)

- [ ] **Step 1: Write tests for ProfileManager**

Create file `tests/test_profile_manager.py`:

```python
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tts import ProfileManager

@pytest.fixture
def tmp_profiles_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def test_add_profile_creates_files(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)
    audio_src = tmp_profiles_dir / "test_audio.mp3"
    audio_src.write_bytes(b"\x00\x00\x00\x1cID3")  # minimal MP3 header

    result = pm.add_profile("test_voice", str(audio_src))

    assert result["name"] == "test_voice"
    assert result["audio_file"] == "test_voice.mp3"
    assert (tmp_profiles_dir / "test_voice.json").exists()
    assert (tmp_profiles_dir / "test_voice.mp3").exists()

def test_add_profile_rejects_duplicate(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)
    audio_src = tmp_profiles_dir / "test.mp3"
    audio_src.write_bytes(b"\x00\x00\x00\x1cID3")
    pm.add_profile("dup", str(audio_src))

    with pytest.raises(ValueError, match="already exists"):
        pm.add_profile("dup", str(audio_src))

def test_add_profile_rejects_invalid_audio(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)
    invalid_file = tmp_profiles_dir / "not_audio.txt"
    invalid_file.write_text("not audio")

    with pytest.raises(ValueError, match="Invalid audio"):
        pm.add_profile("bad", str(invalid_file))

def test_list_profiles(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)
    for name in ["voice_a", "voice_b"]:
        src = tmp_profiles_dir / f"{name}.mp3"
        src.write_bytes(b"\x00\x00\x00\x1cID3")
        pm.add_profile(name, str(src))

    profiles = pm.list_profiles()

    assert len(profiles) == 2
    names = [p["name"] for p in profiles]
    assert "voice_a" in names
    assert "voice_b" in names

def test_delete_profile(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)
    src = tmp_profiles_dir / "todel.mp3"
    src.write_bytes(b"\x00\x00\x00\x1cID3")
    pm.add_profile("todel", str(src))

    pm.delete_profile("todel")

    assert not (tmp_profiles_dir / "todel.json").exists()
    assert not (tmp_profiles_dir / "todel.mp3").exists()

def test_delete_profile_nonexistent(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)

    with pytest.raises(FileNotFoundError, match="not found"):
        pm.delete_profile("ghost")

def test_get_audio_path(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)
    src = tmp_profiles_dir / "getpath.mp3"
    src.write_bytes(b"\x00\x00\x00\x1cID3")
    pm.add_profile("getpath", str(src))

    path = pm.get_audio_path("getpath")

    assert path == tmp_profiles_dir / "getpath.mp3"
    assert path.exists()

def test_get_audio_path_missing_profile(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)

    with pytest.raises(FileNotFoundError, match="not found"):
        pm.get_audio_path("missing")

def test_profile_exists(tmp_profiles_dir):
    pm = ProfileManager(profiles_dir=tmp_profiles_dir)
    src = tmp_profiles_dir / "exists.mp3"
    src.write_bytes(b"\x00\x00\x00\x1cID3")
    pm.add_profile("exists", str(src))

    assert pm.profile_exists("exists") is True
    assert pm.profile_exists("notreal") is False

def test_auto_create_profiles_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        profiles_path = Path(tmpdir) / "profiles"
        pm = ProfileManager(profiles_dir=profiles_path)

        src = Path(tmpdir) / "test.mp3"
        src.write_bytes(b"\x00\x00\x00\x1cID3")
        pm.add_profile("autocreate", str(src))

        assert profiles_path.exists()
```

Run: `pytest tests/test_profile_manager.py -v`
Expected: 10 failures (ProfileManager not defined yet)

- [ ] **Step 2: Implement ProfileManager**

Add after the `Segment` dataclass (tts.py:42-72):

```python
class ProfileManager:
    """Manages voice clone profiles in the profiles/ directory."""

    SUPPORTED_FORMATS = {".mp3": "audio/mpeg", ".wav": "audio/wav"}

    def __init__(self, profiles_dir: str | Path = "profiles"):
        self.profiles_dir = Path(profiles_dir)

    def _ensure_dir(self):
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _validate_audio(self, audio_path: str) -> str:
        """Validate audio file with pydub, return MIME type."""
        try:
            audio = AudioSegment.from_file(audio_path)
            ext = Path(audio_path).suffix.lower()
            if ext not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {ext}")
            return self.SUPPORTED_FORMATS[ext]
        except Exception as e:
            raise ValueError(f"Invalid audio: {e}")

    def add_profile(self, name: str, audio_path: str) -> dict:
        """Add a voice clone profile. Copies audio to profiles_dir."""
        self._ensure_dir()
        if self.profile_exists(name):
            raise ValueError(f"Profile '{name}' already exists")

        mime = self._validate_audio(audio_path)
        src_path = Path(audio_path)
        ext = src_path.suffix.lower()
        dest_audio = self.profiles_dir / f"{name}{ext}"

        import shutil
        shutil.copy2(src_path, dest_audio)

        profile = {
            "name": name,
            "audio_file": f"{name}{ext}",
            "created_at": "2026-05-14",
        }
        json_path = self.profiles_dir / f"{name}.json"
        import json
        json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

        return profile

    def list_profiles(self) -> list[dict]:
        """List all profiles."""
        profiles = []
        if not self.profiles_dir.exists():
            return profiles
        for json_file in self.profiles_dir.glob("*.json"):
            import json
            profiles.append(json.loads(json_file.read_text(encoding="utf-8")))
        return sorted(profiles, key=lambda p: p["name"])

    def delete_profile(self, name: str):
        """Delete a profile and its audio file."""
        json_path = self.profiles_dir / f"{name}.json"
        if not json_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found")
        import json
        profile = json.loads(json_path.read_text(encoding="utf-8"))
        audio_file = profile["audio_file"]
        audio_path = self.profiles_dir / audio_file
        json_path.unlink()
        if audio_path.exists():
            audio_path.unlink()

    def get_audio_path(self, name: str) -> Path:
        """Return full path to a profile's audio file."""
        json_path = self.profiles_dir / f"{name}.json"
        if not json_path.exists():
            raise FileNotFoundError(f"Profile '{name}' not found")
        import json
        profile = json.loads(json_path.read_text(encoding="utf-8"))
        audio_path = self.profiles_dir / profile["audio_file"]
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file for profile '{name}' not found")
        return audio_path

    def profile_exists(self, name: str) -> bool:
        """Check if a profile exists."""
        return (self.profiles_dir / f"{name}.json").exists()
```

Run: `pytest tests/test_profile_manager.py -v`
Expected: PASS (all 10 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_profile_manager.py tts.py
git commit -m "feat: add ProfileManager class for voice clone profiles"
```

---

## Task 2: Parse Text File — Clone Tag Support

**Files:**
- Modify: `tts.py:50-56` (add clone tag regex)
- Modify: `tts.py:74-144` (parse_text_file function)

- [ ] **Step 1: Write tests for clone tag parsing**

Add to `tests/test_parser.py`:

```python
def test_parse_clone_tag():
    content = "[clone:my_voice]\n測試文字\n"
    segments = parse_text_file(content)
    assert len(segments) == 1
    assert segments[0].voice == "clone:my_voice"
    assert segments[0].text == "測試文字"
    assert segments[0].style is None

def test_parse_clone_tag_with_style():
    content = "[style:平靜]\n[clone:my_voice]\n測試文字\n"
    segments = parse_text_file(content)
    assert len(segments) == 1
    assert segments[0].voice == "clone:my_voice"
    assert segments[0].style == "平靜"

def test_parse_clone_and_voice_mixing():
    content = "[clone:voice_a]\n文字A\n[voice:冰糖]\n文字B\n"
    segments = parse_text_file(content)
    assert segments[0].voice == "clone:voice_a"
    assert segments[1].voice == "冰糖"

def test_parse_clone_resets_style():
    content = "[clone:voice_a]\n[style:風格A]\n[clone:voice_b]\n文字\n"
    segments = parse_text_file(content)
    assert segments[0].voice == "clone:voice_a"
    assert segments[0].style is None
    assert segments[1].voice == "clone:voice_b"
    assert segments[1].style == "風格A"

def test_parse_clone_inline_not_treated_as_clone():
    """Inline [clone:X] on same line as text is not treated as clone tag."""
    content = "[clone:my_voice] 這是文字\n"
    segments = parse_text_file(content)
    assert len(segments) == 1
    assert segments[0].voice == "mimo_default"
```

Run: `pytest tests/test_parser.py::test_parse_clone_tag tests/test_parser.py::test_parse_clone_tag_with_style tests/test_parser.py::test_parse_clone_and_voice_mixing tests/test_parser.py::test_parse_clone_resets_style tests/test_parser.py::test_parse_clone_inline_not_treated_as_clone -v`
Expected: 5 failures

- [ ] **Step 2: Implement clone tag parsing**

Add to tts.py (after `_is_style_tag_line`):

```python
def _is_clone_tag_line(line: str) -> bool:
    return bool(re.match(r"^\[clone:[^\]]+\]$", line.strip()))
```

Modify `parse_text_file()` — in the for loop after checking `_is_voice_tag_line`:

```python
if _is_clone_tag_line(line):
    if current_text_lines:
        final_style = current_style if current_style is not None else default_style
        segments.append(Segment(
            voice=current_voice,
            style=final_style,
            text="\n".join(current_text_lines)
        ))
        current_text_lines = []
    current_voice = f"clone:{line[7:-1]}"
    current_style = None
    has_voice = True
    continue
```

Run: `pytest tests/test_parser.py::test_parse_clone_tag tests/test_parser.py::test_parse_clone_tag_with_style tests/test_parser.py::test_parse_clone_and_voice_mixing tests/test_parser.py::test_parse_clone_resets_style tests/test_parser.py::test_parse_clone_inline_not_treated_as_clone -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tts.py
git commit -m "feat: support [clone:profile] tag in parse_text_file()"
```

---

## Task 3: MiMoClient.synthesize() — Clone Path

**Files:**
- Modify: `tts.py:157-215` (MiMoClient.synthesize method)
- Modify: `tts.py:20` (add base64 to imports if not present)

- [ ] **Step 1: Write tests for clone synthesize path**

Add to `tests/test_api.py`:

```python
from unittest.mock import patch, MagicMock

def test_synthesize_clone_segment(mocker):
    """Clone segments use voiceclone model with base64 audio."""
    mock_requests_post = mocker.patch("tts.requests.post")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "YWJj"}}]}  # base64 "abc"
    }
    mock_requests_post.return_value = mock_response

    tmpdir = tempfile.mkdtemp()
    profiles_dir = Path(tmpdir)
    audio_file = profiles_dir / "test.mp3"
    audio_file.write_bytes(b"\x00\x00\x00\x1cID3")
    pm = ProfileManager(profiles_dir=profiles_dir)
    pm.add_profile("test", str(audio_file))

    client = MiMoClient(api_key="test_key")
    segment = Segment(voice="clone:test", style=None, text="測試")

    client.synthesize(segment)

    mock_requests_post.assert_called_once()
    call_kwargs = mock_requests_post.call_args
    assert call_kwargs.kwargs["json"]["model"] == "mimo-v2.5-tts-voiceclone"
    voice_value = call_kwargs.kwargs["json"]["audio"]["voice"]
    assert voice_value.startswith("data:audio/mpeg;base64,")
```

Run: `pytest tests/test_api.py::test_synthesize_clone_segment -v`
Expected: FAIL (client doesn't support clone yet)

- [ ] **Step 2: Verify base64 is imported**

Check that `import base64` is present at tts.py:11. If not:
```python
import base64
```

- [ ] **Step 3: Implement clone path in synthesize()**

In `MiMoClient.synthesize()`, after building messages, add before the headers block:

```python
is_clone = segment.voice.startswith("clone:")

if is_clone:
    profile_name = segment.voice[6:]  # strip "clone:"
    audio_path = self.profile_manager.get_audio_path(profile_name)
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = audio_path.suffix.lower()
    mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"
    voice_value = f"data:{mime};base64,{audio_b64}"
    model = "mimo-v2.5-tts-voiceclone"
else:
    voice_value = SCRIPT_CHARACTER_VOICE_MAP.get(
        segment.voice,
        VOICE_NAME_MAP.get(segment.voice, segment.voice)
    )
    model = self.model
```

Update the payload building to use these variables instead of `segment.voice` and `self.model`.

```python
payload = {
    "model": model,
    "messages": messages,
    "audio": {
        "format": "wav",
        "voice": voice_value
    }
}
```

Note: The `MiMoClient.__init__` needs `self.profile_manager: ProfileManager` passed in:
```python
def __init__(self, api_key: str, model: str = "mimo-v2.5-tts", profile_manager: ProfileManager = None):
    self.api_key = api_key
    self.model = model
    self.base_url = "https://token-plan-cn.xiaomimimo.com/v1"
    self.max_retries = 3
    self.initial_backoff = 2.0
    self.profile_manager = profile_manager or ProfileManager()
```

Run: `pytest tests/test_api.py::test_synthesize_clone_segment -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tts.py
git commit -m "feat: synthesize clone segments with voiceclone model and base64 audio"
```

---

## Task 4: CLI Subcommands — clone-profile

**Files:**
- Modify: `tts.py:314-328` (parse_args function)

- [ ] **Step 1: Write tests for clone-profile CLI**

Add to `tests/test_parser.py`:

```python
def test_args_clone_profile_add():
    with patch("sys.argv", ["tts.py", "--clone-profile", "add", "my_voice", "--audio", "test.mp3"]):
        args = parse_args()
    assert args.clone_profile_action == "add"
    assert args.clone_profile_name == "my_voice"
    assert args.clone_profile_audio == "test.mp3"

def test_args_clone_profile_list():
    with patch("sys.argv", ["tts.py", "--clone-profile", "list"]):
        args = parse_args()
    assert args.clone_profile_action == "list"

def test_args_clone_profile_delete():
    with patch("sys.argv", ["tts.py", "--clone-profile", "delete", "old_voice"]):
        args = parse_args()
    assert args.clone_profile_action == "delete"
    assert args.clone_profile_name == "old_voice"

def test_args_no_clone_profile_returns_none():
    with patch("sys.argv", ["tts.py", "input.txt"]):
        args = parse_args()
    assert args.clone_profile_action is None
```

Run: `pytest tests/test_parser.py::test_args_clone_profile_add tests/test_parser.py::test_args_clone_profile_list tests/test_parser.py::test_args_clone_profile_delete tests/test_parser.py::test_args_no_clone_profile_returns_none -v`
Expected: 4 failures (arguments not defined)

- [ ] **Step 2: Add --clone-profile arguments**

In `parse_args()`, add after the existing argument definitions:

```python
clone_profile = parser.add_argument_group("clone-profile")
clone_profile_exclusive = clone_profile.add_mutually_exclusive_group()
clone_profile_exclusive.add_argument("--clone-profile", dest="clone_profile_action", choices=["add", "list", "delete"], help="Manage voice clone profiles")
clone_profile.add_argument("clone_profile_name", nargs="?", help="Profile name for add/delete")
clone_profile.add_argument("--audio", dest="clone_profile_audio", help="Audio file path for add")
```

- [ ] **Step 3: Implement clone-profile actions in main()**

Add to `main()` before the existing segment processing:

```python
profile_manager = ProfileManager()

if args.clone_profile_action == "add":
    if not args.clone_profile_name or not args.clone_profile_audio:
        print("錯誤：add 需要 <name> 和 --audio", file=sys.stderr)
        sys.exit(1)
    try:
        profile = profile_manager.add_profile(args.clone_profile_name, args.clone_profile_audio)
        print(f"已建立 profile：{profile['name']} ({profile['audio_file']})")
    except ValueError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)

if args.clone_profile_action == "list":
    profiles = profile_manager.list_profiles()
    if not profiles:
        print("尚無 clone profiles")
    for p in profiles:
        print(f"{p['name']}  | {p['audio_file']} | {p['created_at']}")
    sys.exit(0)

if args.clone_profile_action == "delete":
    if not args.clone_profile_name:
        print("錯誤：delete 需要 <name>", file=sys.stderr)
        sys.exit(1)
    try:
        profile_manager.delete_profile(args.clone_profile_name)
        print(f"已刪除 profile：{args.clone_profile_name}")
    except FileNotFoundError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
```

Also update the client instantiation to pass profile_manager:
```python
client = MiMoClient(api_key=api_key, model=args.model, profile_manager=profile_manager)
```

Run: `pytest tests/test_parser.py::test_args_clone_profile_add tests/test_parser.py::test_args_clone_profile_list tests/test_parser.py::test_args_clone_profile_delete tests/test_parser.py::test_args_no_clone_profile_returns_none -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tts.py
git commit -m "feat: add --clone-profile CLI subcommands (add/list/delete)"
```

---

## Task 5: Integration Test

**Files:**
- Create: `tests/test_clone_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""Full flow: parse [clone:X] → synthesize → concatenate → export."""
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tts import parse_text_file, MiMoClient, concatenate_wav, convert_to_mp3, Segment, ProfileManager

def test_clone_and_builtin_mixing(mocker):
    """Test parsing and synthesizing mix of clone and builtin segments."""
    tmpdir = tempfile.mkdtemp()
    profiles_dir = Path(tmpdir)
    audio_file = profiles_dir / "my_ref.mp3"
    audio_file.write_bytes(b"\x00\x00\x00\x1cID3")
    pm = ProfileManager(profiles_dir=profiles_dir)
    pm.add_profile("my_ref", str(audio_file))

    content = "[style:平靜]\n[clone:my_ref]\nclone文字\n[voice:冰糖]\nbuiltin文字\n"
    segments = parse_text_file(content)

    assert len(segments) == 2
    assert segments[0].voice == "clone:my_ref"
    assert segments[0].style == "平靜"
    assert segments[0].text == "clone文字"
    assert segments[1].voice == "冰糖"
    assert segments[1].text == "builtin文字"
```

Run: `pytest tests/test_clone_integration.py -v`
Expected: FAIL (integration not yet implemented)

Implement the test logic. Then:

```python
def test_clone_and_builtin_mixing(mocker):
    mock_post = mocker.patch("tts.requests.post")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "YWJj"}}}]
    }
    mock_post.return_value = mock_response

    tmpdir = tempfile.mkdtemp()
    profiles_dir = Path(tmpdir)
    audio_file = profiles_dir / "my_ref.mp3"
    audio_file.write_bytes(b"\x00\x00\x00\x1cID3")
    pm = ProfileManager(profiles_dir=profiles_dir)
    pm.add_profile("my_ref", str(audio_file))

    client = MiMoClient(api_key="test", profile_manager=pm)

    # synthesize clone segment
    seg_clone = Segment(voice="clone:my_ref", style="平靜", text="clone文字")
    wav1 = client.synthesize(seg_clone)

    # synthesize builtin segment
    seg_builtin = Segment(voice="冰糖", style=None, text="builtin文字")
    wav2 = client.synthesize(seg_builtin)

    # concatenate
    combined = concatenate_wav([wav1, wav2])
    assert combined is not None

    # verify clone call used voiceclone model
    clone_call = mock_post.call_args_list[0]
    builtin_call = mock_post.call_args_list[1]
    assert clone_call.kwargs["json"]["model"] == "mimo-v2.5-tts-voiceclone"
    assert builtin_call.kwargs["json"]["model"] == "mimo-v2.5-tts"
    assert clone_call.kwargs["json"]["audio"]["voice"].startswith("data:audio/mpeg;base64,")
    assert builtin_call.kwargs["json"]["audio"]["voice"] == "冰糖"
```

Run: `pytest tests/test_clone_integration.py -v`
Expected: PASS

- [ ] **Step 2: Commit**

```bash
git add tests/test_clone_integration.py
git commit -m "test: add integration test for clone + builtin mixing"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|------------------|------|
| Profile JSON schema | Task 1 |
| profiles/ directory | Task 1 |
| add_profile | Task 1 |
| list_profiles | Task 1 |
| delete_profile | Task 1 |
| get_audio_path | Task 1 |
| profile_exists | Task 1 |
| Auto-create profiles/ | Task 1 |
| Audio validation (pydub) | Task 1 |
| `[clone:X]` parsing | Task 2 |
| Mix with `[voice:]` and `[style:]` | Task 2 |
| Line-level only | Task 2 |
| voiceclone model | Task 3 |
| base64 encoding (correct MIME) | Task 3 |
| --clone-profile add | Task 4 |
| --clone-profile list | Task 4 |
| --clone-profile delete | Task 4 |
| List output format | Task 4 |
| Chunking same audio per chunk | Task 3 (same base64 per chunk) |
| Retry behavior (same as existing) | Task 3 |

All spec requirements covered. No placeholders, no TODOs.