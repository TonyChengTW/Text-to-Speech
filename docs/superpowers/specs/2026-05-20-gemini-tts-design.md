# Gemini TTS Integration — Design Spec

## Overview

Add support for the Gemini TTS API (e.g. `gemini` model) to the MiMo TTS CLI tool. Users can switch between the existing MiMo TTS and the new Gemini TTS by specifying the `--model` argument. The existing `sample.txt` text format (including inline voice and style tags) will remain unchanged, preserving a seamless experience. 

## Requirements Summary

| Item | Decision |
|------|----------|
| API Model | `gemini` |
| Text Format | No changes to the existing `[voice:X]` and `[style:Y]` format |
| Voice Mapping | Internal auto-mapping from MiMo voice names (e.g., "冰糖") to Gemini voice names (e.g., "Aoede") |
| API Key Management | Separate CLI argument `--gemini-api-key` and env var `GEMINI_API_KEY` |
| Architecture | Extract a base `BaseTTSClient` interface and build a `TTSClientFactory` to instantiate either `MiMoClient` or `GeminiTTSClient` based on the `--model` argument |

## Architecture Design

### 1. Base Client Interface
Create a common `BaseTTSClient` interface in `tts.py` to define the standard contract for all TTS API clients.
```python
class BaseTTSClient:
    def synthesize(self, segment: Segment) -> bytes:
        raise NotImplementedError
```
The existing `MiMoClient` will be modified to inherit from `BaseTTSClient`.

### 2. GeminiTTSClient Implementation
A new class `GeminiTTSClient` will be implemented to handle requests specifically for the Gemini TTS REST API. 
- It will parse the text and style from the `Segment`.
- It will map the requested MiMo voice name to a Gemini voice name.
- It will handle base64 audio decoding into WAV bytes similar to `MiMoClient`.

### 3. TTSClientFactory
To instantiate the appropriate client dynamically, a factory method or class will be created.
```python
class TTSClientFactory:
    @staticmethod
    def create(model_name: str, api_key: str, **kwargs) -> BaseTTSClient:
        if "gemini" in model_name.lower():
            return GeminiTTSClient(api_key=api_key, model=model_name)
        else:
            return MiMoClient(api_key=api_key, model=model_name, **kwargs)
```

## Voice Mapping Configuration

Since Gemini uses different voices from MiMo, an internal mapping dictionary will be hardcoded in the script. When `GeminiTTSClient` receives a segment, it will look up the `Segment.voice` against this mapping.
- Example mapping: `{"冰糖": "Aoede", "蘇打": "Puck", "mimo_default": "Aoede"}`
- If a voice is not found in the mapping, it defaults to a standard Gemini voice (e.g., `"Aoede"`).
- This keeps the `.txt` files provider-agnostic.

## CLI & API Key Management

The `parse_args()` function will be updated to accept the new Gemini API key.
```bash
python tts.py input.txt --model gemini --gemini-api-key YOUR_GEMINI_KEY
```
- **CLI Argument:** `--gemini-api-key`
- **Environment Variable:** `GEMINI_API_KEY` in `.env`
- **Validation:** If the selected model is `gemini` and no Gemini API key is provided, the tool will exit with an error, ignoring `TTS_API_KEY`. Conversely, if `mimo-v2.5-tts` is used, it ignores `GEMINI_API_KEY`.

## Error Handling
| Scenario | Behavior |
|----------|----------|
| Missing Gemini API Key when `--model gemini` | Print error and exit with code 1 |
| Unmapped Voice Name | Print a warning and fallback to a default Gemini voice (e.g., Aoede) |
| Voice Clone Tag `[clone:X]` used with Gemini | Gemini does not support custom voice cloning through this script. Throw a descriptive `NotSupportedError` if `is_clone` is true under `GeminiTTSClient`. |

## Testing Scope
1. **Factory Logic:** Ensure the correct client is created based on the `model` argument.
2. **Gemini API Client:** Mock the Gemini REST API endpoint to test success and failure paths.
3. **Voice Mapping:** Ensure MiMo voice names translate correctly to Gemini voice names.
4. **API Key Isolation:** Ensure Gemini does not crash if `TTS_API_KEY` is missing, and vice versa.
5. **Clone Tag Failure:** Ensure using `[clone:...]` with Gemini throws a proper unsupported exception instead of a cryptic crash.
