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
├── my_voice.json     # {"name": "my_voice", "audio_file": "my_voice.mp3", "created_at": "2026-05-13"}
├── my_voice.mp3
├── dad.json
└── dad.wav
```

### Profile JSON Schema

```json
{
  "name": "<string>",
  "audio_file": "<filename.mp3 or filename.wav>",
  "created_at": "<YYYY-MM-DD>"
}
```

Note: `name` must be unique. The `audio_file` must be in the same `profiles/` directory.

Profile files must be named `<name>.json`; the audio file is stored alongside in the same `profiles/` directory.

## CLI Interface

### Add Profile

```bash
python tts.py --clone-profile add <name> --audio <path/to/audio.mp3>
```

- Validates audio file via `pydub.AudioSegment.from_file()` (confirms valid MP3/WAV, not just extension)
- Copies audio to `profiles/<name>.<ext>` preserving original format
- Returns error if profile `<name>` already exists

### List Profiles

```bash
python tts.py --clone-profile list
```

- Output format (one profile per line):
  ```
  python tts.py --clone-profile list
  # my_voice  | my_voice.mp3 | 2026-05-13
  # dad        | dad.wav      | 2026-05-12
  ```
  Columns: `name | audio_file | created_at`

### Delete Profile

```bash
python tts.py --clone-profile delete <name>
```

- Removes both `profiles/<name>.json` and the associated audio file
- Returns error if profile does not exist

## Text File Format

### Clone Tag

`[clone:profile_name]` — selects a registered voice clone profile for the following text segment. Resets current style.

**Only line-level `[clone:X]` is supported.** Inline use (e.g., `你好[clone:voice]` as part of a paragraph line) is not parsed as a clone tag — it is treated as regular text.

### Chunking Behavior

`chunk_text()` applies to clone segments identically to built-in voices. Each chunk receives the **same** base64 audio (the clone voice reference is the same for every chunk; the API reconstructs voice quality across all chunks).

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
| `clone:<name>` | `mimo-v2.5-tts-voiceclone` | `"voice": "data:audio/mpeg;base64,<b64>"` or `"data:audio/wav;base64,<b64>"` |

### Base64 Encoding

The MIME type in the data URI must match the actual audio file encoding:
- MP3 file → `data:audio/mpeg;base64,<b64>`
- WAV file → `data:audio/wav;base64,<b64>`

```python
import pydub
audio = pydub.AudioSegment.from_file(profile_audio_path)
# Detect format from file extension
ext = Path(profile_audio_path).suffix.lower()
mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"
with open(profile_audio_path, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode("utf-8")
voice_value = f"data:{mime};base64,{audio_b64}"
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

**Location:** `tts.py` (new class, ~120–150 lines)

**Responsibilities:**
- `add_profile(name, audio_path)` — validate (pydub), copy audio to `profiles/`, write JSON
- `list_profiles()` — enumerate `profiles/*.json`, print in list format
- `delete_profile(name)` — remove both files
- `get_audio_path(name)` — return full path to audio file for a profile
- `profile_exists(name)` — check if profile exists

**Edge cases:**
- `profiles/` directory does not exist → auto-create on first `add`
- Duplicate profile name → raise error
- Missing audio file for existing profile → raise error on synthesize
- Invalid audio format → reject on add with clear message (not just extension check)

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
| API error on clone segment | Retry 3x with exponential backoff (same as existing `synthesize()`), then raise |
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