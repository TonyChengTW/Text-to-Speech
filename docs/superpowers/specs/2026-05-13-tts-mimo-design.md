# MiMo TTS CLI Tool — Design Spec

A Python command-line tool that reads `.txt` files with per-segment voice/style controls and generates MP3 audio using the MiMo-V2.5-TTS API.

## Overview

- **Input:** Single `.txt` file with `[voice:]`, `[style:]` headers and inline tags
- **Output:** Single `.mp3` file (same name as input by default)
- **API:** MiMo-V2.5-TTS (`https://api.xiaomimimo.com/v1/chat/completions`)
- **Approach:** Simple script with `requests` + `pydub`, non-streaming API calls

## CLI Interface

```
python tts.py input.txt [options]

Options:
  --api-key TEXT      API key (or set TTS_API_KEY env var)
  --model TEXT        Model: mimo-v2.5-tts (default)
  --output PATH       Output MP3 path (default: same name as input)
  --chunk-size INT    Max characters per API request (default: 4000)
  --sample-rate INT   Audio sample rate (default: 24000)
  --bitrate TEXT      MP3 bitrate (default: 192k)
  --verbose / -v      Show progress
```

**Examples:**
```bash
python tts.py story.txt --api-key sk-xxx --verbose
python tts.py notes.txt -v --output ./audio/narration.mp3
```

## Text File Format

Each segment consists of optional headers followed by text content:

```
[voice:冰糖]
[style:用台灣口音，語速稍慢]
(开心)真的嗎？太好了！我等這天等好久了！

[voice:苏打]
[style:用磁性的聲音，像深夜電台主播]
歡迎回來，今天過得怎麼樣？

[voice:茉莉]
(开心)真的嗎？太好了！[大笑]我等這天等好久了！
```

### Headers

| Header | Description | Maps to API |
|--------|-------------|-------------|
| `[voice:X]` | Voice ID (冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean) | `audio.voice` |
| `[style:X]` | Natural language style instruction | `role: user` content |

### Inline Tags

| Tag | Description | Example |
|-----|-------------|---------|
| `(标签)` | Audio style tag (at text beginning) | `(开心)`, `(台湾腔)`, `(磁性)` |
| `[标签]` | Inline audio tag (within text) | `[深呼吸]`, `[笑]`, `[叹气]` |

### Parsing Rules

1. Skip `#` comment lines and blank lines
2. Detect `[voice:X]` → store voice for current segment
3. Detect `[style:X]` → store style for current segment
4. Accumulate text lines until next header or EOF
5. Each accumulated block = one API segment
6. If no `[voice:]` → use `mimo_default`
7. If no `[style:]` → send empty user message
8. Multiple `[style:]` before text → last one wins
9. Empty segment (header only, no text) → skip

## API Integration

**Endpoint:** `POST https://api.xiaomimimo.com/v1/chat/completions`

**Auth:** `api-key` header

**Request body:**
```json
{
  "model": "mimo-v2.5-tts",
  "messages": [
    {"role": "user", "content": "<style from [style:]>"},
    {"role": "assistant", "content": "<text with inline tags>"}
  ],
  "audio": {
    "format": "wav",
    "voice": "<voice from [voice:]> or mimo_default"
  }
}
```

**Response:**
```json
{
  "choices": [{
    "message": {
      "audio": {
        "data": "<base64 encoded WAV>"
      }
    }
  }]
}
```

**Non-streaming only** — streaming has no advantage in current state (low-latency streaming not yet available).

**Chunking:** If a segment's text exceeds `--chunk-size` characters, split into sub-segments at sentence boundaries. Use Chinese punctuation (。！？) as primary boundaries. For mixed Chinese/English text, also split at English sentence endings (.!?) followed by whitespace or Chinese characters. Call API for each sub-segment, then concatenate the resulting audio.

## Audio Processing

1. Parse text file → list of segments
2. For each segment: build request → call API → decode base64 WAV
3. Concatenate all WAV segments into one WAV
4. Convert WAV → MP3 via ffmpeg (through pydub) with specified bitrate and sample rate
5. Write output file

**Dependencies:**
- `requests` — HTTP calls
- `pydub` — WAV manipulation & MP3 conversion
- `ffmpeg` — required by pydub for MP3 encoding

**Audio Parameters:**
- Sample rate: 24000 Hz (default, configurable via `--sample-rate`)
- Bitrate: 192k (default, configurable via `--bitrate`)
- Format: WAV (API response) → MP3 (output)

## Error Handling

| Error | Handling |
|-------|----------|
| No API key | Print error, exit code 1 |
| File not found | Print error, exit code 1 |
| Empty file | Print warning, exit code 0 |
| API error (401/403) | Print status + message, exit code 1 (no retry) |
| API error (429) | Exponential backoff retry: 2s, 4s, 8s (max 3 attempts) |
| API error (5xx) | Exponential backoff retry: 1s, 2s, 4s (max 3 attempts) |
| API timeout | Retry with exponential backoff: 2s, 4s (max 2 attempts) |
| ffmpeg not installed | Print install instructions, exit code 1 |
| Invalid `[voice:]` name | Warn + fallback to `mimo_default` (valid API voice ID) |
| Network error | Retry with exponential backoff: 2s, 4s (max 2 attempts) |

**Retry Strategy:**
- Exponential backoff with jitter (±50%)
- Max 3 retries for server errors (429, 5xx)
- Max 2 retries for network/timeout errors
- No retry for client errors (401, 403)

**Progress output (with `--verbose`):**
```
[1/5] 冰糖: "你好，歡迎使用..." → OK (1.2s)
[2/5] 苏打: "歡迎回來..." → OK (0.9s)
...
[Done] output.mp3 (12.3s total, 5 segments, 24000Hz, 192k)
```
