# Voice Clone Feature — Design Spec

## Overview

Add voice cloning (speaker synthesis) support to the MiMo TTS CLI tool. Users record or provide an audio sample, register it as a named profile, then reference it in `.txt` files using `[clone:profile_name]`.

## Requirements Summary

| Item | Decision |
|------|----------|
| Clone type | Speaker synthesis (replicate target voice from audio sample) |
| Audio source | User-provided MP3/WAV file |
| Profile management | CLI: `add / list / delete` |
| `.txt` reference | `[clone:profile_name]` |
| Storage | `profiles/` directory (version-controlled) |
| API method | `mimo-v2.5-tts-voiceclone` model, audio base64 embedded in `voice` field per request |
| Style overlay | `[style:]` can be combined with `[clone:]` in the same segment |

## Profile Storage

### Directory Structure

```
profiles/
├── my_voice.json     # {"name": "my_voice", "audio_file": "my_voice.mp3", "language": "zh", "created_at": "2026-05-13"}
├── my_voice.mp3
├── dad.json
└── dad.wav
```

### Profile JSON Schema

```json
{
  "name": "<string>",
  "audio_file": "<filename.mp3 or filename.wav>",
  "language": "<zh | en>",
  "created_at": "<YYYY-MM-DD>"
}
```

Profile files must be named `<name>.json`; the audio file is stored alongside in the same `profiles/` directory.

## CLI Interface

### Add Profile

```bash
python tts.py --clone-profile add <name> --audio <path/to/audio.mp3>
```

- Validates audio file exists and format is MP3 or WAV
- Auto-detects language from filename or defaults to `zh`
- Returns error if profile `<name>` already exists

### List Profiles

```bash
python tts.py --clone-profile list
```

- Lists all profiles with name, audio file, and creation date

### Delete Profile

```bash
python tts.py --clone-profile delete <name>
```

- Removes both `profiles/<name>.json` and the associated audio file
- Returns error if profile does not exist

## Text File Format

### Clone Tag

`[clone:profile_name]` — selects a registered voice clone profile for the following text segment. Resets current style.

### Mixing with Built-in Voices

```
[style:用平靜的語調]
[clone:my_voice] 你好，這是我的聲音。
[voice:冰糖] 這是內建音色。
[clone:dad] 爸爸的聲音來說同樣的內容。
```

Behavior:
- `[clone:X]` resets paragraph style (same as `[voice:X]`)
- `[style:]` after `[clone:]` applies style to clone voice
- `[voice:]` and `[clone:]` are mutually exclusive per segment

## Parsing Rules

The existing `parse_text_file()` function is extended:

1. Add pattern: `r"^\[clone:[^\]]+\]$"` — detect clone tag line
2. On `[clone:X]`:
   - Flush any pending text segment
   - Set current voice to `clone:<name>` (stored in `Segment.voice`)
   - Reset current style
3. Synthesize step: if `Segment.voice` starts with `clone:`, use `voiceclone` model path

## API Integration

### Model Selection Logic

| `Segment.voice` pattern | Model | Voice field |
|------------------------|-------|-------------|
| Built-in voice (e.g. `冰糖`, `Milo`) | `mimo-v2.5-tts` | `"voice": "<voice_name>"` |
| `clone:<name>` | `mimo-v2.5-tts-voiceclone` | `"voice": "data:audio/mpeg;base64,<b64>"` |

### Base64 Encoding

```python
with open(profile_audio_path, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode("utf-8")
voice_value = f"data:audio/mpeg;base64,{audio_b64}"  # or audio/wav
```

### Message Structure for Clone

```python
messages = []
if segment.style:
    messages.append({"role": "user", "content": segment.style})
messages.append({"role": "assistant", "content": segment.text})
```

User message can be empty `""` for clone mode, or contain style instructions.

## Implementation Units

### 1. ProfileManager

**Location:** `tts.py` (new class, ~80 lines)

**Responsibilities:**
- `add_profile(name, audio_path)` — validate, copy audio, write JSON
- `list_profiles()` — enumerate `profiles/*.json`
- `delete_profile(name)` — remove both files
- `get_audio_path(name)` — return full path to audio file for a profile

**Edge cases:**
- Duplicate profile name → raise error
- Missing audio file for existing profile → raise error on synthesize
- Invalid audio format → reject on add

### 2. parse_text_file() — Clone Extension

**Location:** `tts.py:74-144` (existing function, minimal changes)

**Changes:**
- Add clone tag regex
- Set `current_voice = f"clone:{name}"` on `[clone:X]`

### 3. MiMoClient.synthesize() — Clone Path

**Location:** `tts.py:157-215` (existing function, modified)

**Changes:**
- If `segment.voice` starts with `"clone:"`, extract profile name, load audio, set model to `mimo-v2.5-tts-voiceclone`, embed base64 in voice field

### 4. CLI Subcommands

**Location:** `tts.py:314-328` (existing `parse_args()`, extended)

**Changes:**
- Add `--clone-profile` argument group with `add / list / delete` subcommands

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Profile not found for `[clone:X]` | Print warning, skip segment |
| Audio file missing | Print error with profile name, skip |
| API error on clone segment | Retry 3x, then raise |
| Invalid audio format | Reject on `add` with clear message |

## Testing Scope

1. **Profile CRUD** — add, list, delete operations
2. **Parser** — `[clone:]` parsing, mixing with `[voice:]` and `[style:]`
3. **Synthesize** — verify correct model and voice field for clone vs. built-in
4. **Integration** — full pipeline: parse → synthesize clone segment → concatenate → export

## Out of Scope (YAGNI)

- Microphone recording (user provides audio file)
- Profile renaming
- Profile export/import
- Server-side voice profile storage (API doesn't support it)
- Combining multiple clone voices in one request