# Gemini TTS Integration — Design Spec

## Overview

Add support for the Gemini TTS API to the MiMo TTS CLI tool. Users can switch between the existing MiMo TTS and the new Gemini TTS by specifying the `--model` argument. The existing `sample.txt` text format (including inline `[voice:X]` and `[style:Y]` tags) remains unchanged, preserving a seamless experience.

## Requirements Summary

| Item | Decision |
|------|----------|
| Gemini Model ID | `gemini-2.5-flash-preview-tts` (or the stable alias as released) |
| Text Format | No changes to `[voice:X]` and `[style:Y]` syntax |
| Voice Mapping | Internal auto-mapping from MiMo voice names to Gemini voice names |
| API Key Management | Separate `--gemini-api-key` CLI arg and `GEMINI_API_KEY` env var |
| Architecture | `BaseTTSClient` interface + `MiMoClient` / `GeminiTTSClient` + `TTSClientFactory` |

---

## API Integration

### Endpoint

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
```

Example with model `gemini-2.5-flash-preview-tts`:
```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent
```

### Authentication

Header: `x-goog-api-key: <GEMINI_API_KEY>`

(Not `Authorization: Bearer`. Gemini uses `x-goog-api-key` for REST calls.)

### Request Payload

```json
{
  "contents": [{
    "parts": [{"text": "<style instruction + text to speak>"}]
  }],
  "generationConfig": {
    "responseModalities": ["AUDIO"],
    "speechConfig": {
      "voiceConfig": {
        "prebuiltVoiceConfig": {
          "voiceName": "Kore"
        }
      }
    }
  }
}
```

**Style injection:** The `[style:X]` tag content will be prepended to the text prompt as a natural language instruction. For example, if `segment.style = "用台灣腔，語速適中"` and `segment.text = "你好！"`, the prompt sent becomes:
```
用台灣腔，語速適中。你好！
```

### Response

The audio data is located at:
```
response["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
```

This is a **base64-encoded raw PCM** string.

### Audio Output Format

> [!IMPORTANT]
> Gemini TTS returns **raw PCM audio** (16-bit signed little-endian, 24kHz, mono). This is **NOT** a WAV file — it has **no WAV header**.

`GeminiTTSClient.synthesize()` must convert PCM → WAV bytes using Python's built-in `wave` module before returning, so the output is compatible with the existing `concatenate_wav()` → `convert_to_mp3()` pipeline.

```python
import wave, io, base64

def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)       # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
```

---

## Architecture Design

### 1. Base Client Interface

```python
from abc import ABC, abstractmethod

class BaseTTSClient(ABC):
    @abstractmethod
    def synthesize(self, segment: Segment) -> bytes:
        """Synthesize a segment and return WAV bytes."""
```

The existing `MiMoClient` will inherit from `BaseTTSClient`.

### 2. GeminiTTSClient

New class in `tts.py`, inheriting `BaseTTSClient`:
- Uses `requests.post()` (no new dependency needed).
- Looks up `segment.voice` in `GEMINI_VOICE_MAPPING` to get the `voiceName`.
- If voice not found, defaults to `"Aoede"` with a warning.
- If `segment.voice.startswith("clone:")`, raises `ValueError` immediately (clone not supported).
- Converts PCM → WAV via `_pcm_to_wav()` before returning.
- Applies same retry-with-exponential-backoff logic as `MiMoClient` (3 retries).

### 3. TTSClientFactory

```python
class TTSClientFactory:
    @staticmethod
    def create(model: str, mimo_api_key: str | None, gemini_api_key: str | None,
               profile_manager=None) -> BaseTTSClient:
        if model in GEMINI_MODELS:
            if not gemini_api_key:
                raise ValueError("Gemini model selected but GEMINI_API_KEY is not set.")
            return GeminiTTSClient(api_key=gemini_api_key, model=model)
        else:
            if not mimo_api_key:
                raise ValueError("MiMo model selected but TTS_API_KEY is not set.")
            return MiMoClient(api_key=mimo_api_key, model=model,
                              profile_manager=profile_manager)

GEMINI_MODELS = {"gemini-2.5-flash-preview-tts", "gemini-2.0-flash-preview-tts"}
```

Using a **whitelist set** (`GEMINI_MODELS`) instead of a substring match to avoid false positives.

---

## Voice Mapping Configuration

All 8 MiMo voices mapped to the closest Gemini prebuilt voice:

| MiMo Voice | Character | Gemini Voice | Gender |
|-----------|-----------|-------------|--------|
| `冰糖` | Bright & cheerful (female) | `Aoede` | Female |
| `茉莉` | Gentle & soft (female) | `Kore` | Female |
| `蘇打` | Energetic (male) | `Puck` | Male |
| `白樺` | Calm & deep (male) | `Charon` | Male |
| `Mia` | Clear & professional (female) | `Leda` | Female |
| `Chloe` | Warm & expressive (female) | `Sulafat` | Female |
| `Milo` | Friendly (male) | `Fenrir` | Male |
| `Dean` | Authoritative (male) | `Enceladus` | Male |
| `mimo_default` | (fallback) | `Aoede` | Female |

Available Gemini voices (30 total, as of 2025): Aoede, Achernar, Achird, Algenib, Alnilam, Autonoe, Callirrhoe, Charon, Despina, Enceladus, Fenrir, Iapetus, Kore, Leda, Pulcherrima, Puck, Rasalgethi, Sadachbia, Sadaltager, Schedar, Sulafat, and others.

---

## CLI & API Key Management

```bash
# Use MiMo (default)
python tts.py input.txt -v

# Use Gemini
python tts.py input.txt --model gemini-2.5-flash-preview-tts --gemini-api-key YOUR_KEY -v

# Or via .env
# GEMINI_API_KEY=xxx
python tts.py input.txt --model gemini-2.5-flash-preview-tts -v
```

- **New CLI arg:** `--gemini-api-key`
- **New env var:** `GEMINI_API_KEY` (read from `.env` via `dotenv_values`)
- Key selection is driven by `TTSClientFactory` — wrong key type causes a clear error.
- `.env.example` will be updated to include `# GEMINI_API_KEY=your_gemini_key_here`.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Missing `GEMINI_API_KEY` when Gemini model selected | `TTSClientFactory` raises `ValueError`, `main()` prints error and exits 1 |
| Missing `TTS_API_KEY` when MiMo model selected | `TTSClientFactory` raises `ValueError`, `main()` prints error and exits 1 |
| Unmapped voice name | Print warning, fallback to `"Aoede"` |
| `[clone:X]` tag used with Gemini model | `GeminiTTSClient.synthesize()` raises `ValueError("Voice cloning is not supported with Gemini TTS")` |
| API 4xx error (except 429) | Raise immediately, no retry |
| API 5xx or 429 | Retry up to 3× with exponential backoff (same as `MiMoClient`) |

---

## Testing Scope

1. **Factory Logic** — Correct client created for MiMo vs Gemini models; missing key raises `ValueError`.
2. **Gemini API Client** — Mock REST endpoint; verify request payload structure (endpoint URL, header, `responseModalities`, `voiceName`).
3. **PCM → WAV Conversion** — `_pcm_to_wav()` produces valid WAV with correct headers.
4. **Voice Mapping** — All 8 MiMo voices resolve to the correct Gemini voice.
5. **Style Injection** — Style text is prepended to the prompt correctly.
6. **Clone Tag Failure** — `[clone:...]` raises `ValueError` under `GeminiTTSClient`.
7. **API Key Isolation** — Gemini client does not crash if `TTS_API_KEY` is absent, and vice versa.
8. **Retry Logic** — Gemini client retries on 5xx/429, not on 4xx.

---

## Out of Scope

- Multi-speaker mode (Gemini supports it, but MiMo does not — out of scope for now)
- Streaming audio output
- Voice cloning via Gemini (no equivalent feature exists)
- Switching models mid-file (model is global per CLI invocation)
