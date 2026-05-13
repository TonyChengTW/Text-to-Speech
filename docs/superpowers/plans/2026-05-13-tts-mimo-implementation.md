# MiMo TTS CLI Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that reads `.txt` files with per-segment voice/style controls and generates MP3 audio using the MiMo-V2.5-TTS API.

**Architecture:** Single-file Python script (`tts.py`) with modular functions for parsing, API calls, and audio processing. Uses `requests` for HTTP, `pydub` for audio manipulation, and `ffmpeg` for MP3 conversion.

**Tech Stack:** Python 3.10+, requests, pydub, ffmpeg

---

## File Structure

| File | Responsibility |
|------|----------------|
| `tts.py` | Main CLI script with all logic |
| `sample.txt` | Example text file (already exists) |
| `requirements.txt` | Python dependencies |
| `tests/test_parser.py` | Unit tests for text parsing |
| `tests/test_api.py` | Unit tests for API integration (mocked) |
| `tests/test_audio.py` | Unit tests for audio processing (mocked) |

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `tts.py` (skeleton)

- [ ] **Step 1: Create requirements.txt**

```
requests>=2.28.0
pydub>=0.25.1
pytest>=7.0.0
```

- [ ] **Step 2: Create tts.py skeleton**

```python
#!/usr/bin/env python3
"""MiMo TTS CLI Tool - Read .txt files and generate MP3 audio."""

import argparse
import sys
from pathlib import Path


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate MP3 audio from .txt files using MiMo TTS API"
    )
    parser.add_argument("input", type=Path, help="Input .txt file path")
    parser.add_argument("--api-key", help="API key (or set TTS_API_KEY env var)")
    parser.add_argument("--model", default="mimo-v2.5-tts", help="Model name")
    parser.add_argument("--output", type=Path, help="Output MP3 path")
    parser.add_argument("--chunk-size", type=int, default=4000, help="Max chars per API request")
    parser.add_argument("--sample-rate", type=int, default=24000, help="Audio sample rate")
    parser.add_argument("--bitrate", default="192k", help="MP3 bitrate")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show progress")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    print(f"Input: {args.input}")
    print(f"Model: {args.model}")
    print(f"Output: {args.output or args.input.with_suffix('.mp3')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Make tts.py executable and test**

```bash
chmod +x tts.py
python tts.py --help
```

Expected: Shows help message with all options

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tts.py
git commit -m "feat: project setup with CLI skeleton"
```

---

## Task 2: Text File Parser

**Files:**
- Create: `tests/test_parser.py`
- Modify: `tts.py` (add parser functions)

- [ ] **Step 1: Write failing tests for parser**

```python
# tests/test_parser.py
import pytest
from tts import parse_text_file, Segment


def test_parse_simple_segment():
    """Test parsing a simple segment with voice and style."""
    text = "[voice:冰糖]\n[style:用台灣口音]\n你好，歡迎使用。"
    segments = parse_text_file(text)
    assert len(segments) == 1
    assert segments[0].voice == "冰糖"
    assert segments[0].style == "用台灣口音"
    assert segments[0].text == "你好，歡迎使用。"


def test_parse_multiple_segments():
    """Test parsing multiple segments."""
    text = "[voice:冰糖]\n你好\n\n[voice:苏打]\n歡迎回來"
    segments = parse_text_file(text)
    assert len(segments) == 2
    assert segments[0].voice == "冰糖"
    assert segments[1].voice == "苏打"


def test_parse_without_voice():
    """Test segment without voice uses default."""
    text = "[style:用台灣口音]\n你好"
    segments = parse_text_file(text)
    assert segments[0].voice == "mimo_default"
    assert segments[0].style == "用台灣口音"


def test_parse_without_style():
    """Test segment without style has None style."""
    text = "[voice:冰糖]\n你好"
    segments = parse_text_file(text)
    assert segments[0].voice == "冰糖"
    assert segments[0].style is None


def test_parse_with_inline_tags():
    """Test parsing text with inline tags."""
    text = "[voice:冰糖]\n(开心)真的嗎？[大笑]太好了！"
    segments = parse_text_file(text)
    assert segments[0].text == "(开心)真的嗎？[大笑]太好了！"


def test_parse_skips_comments():
    """Test that # comment lines are skipped."""
    text = "# 這是註釋\n[voice:冰糖]\n# 另一個註釋\n你好"
    segments = parse_text_file(text)
    assert len(segments) == 1
    assert segments[0].text == "你好"


def test_parse_skips_blank_lines():
    """Test that blank lines are skipped."""
    text = "[voice:冰糖]\n\n\n你好"
    segments = parse_text_file(text)
    assert segments[0].text == "你好"


def test_parse_empty_file():
    """Test parsing empty file returns empty list."""
    text = ""
    segments = parse_text_file(text)
    assert len(segments) == 0


def test_parse_multiple_styles_last_wins():
    """Test multiple [style:] before text, last one wins."""
    text = "[voice:冰糖]\n[style:用台灣口音]\n[style:用溫柔的語調]\n你好"
    segments = parse_text_file(text)
    assert segments[0].style == "用溫柔的語調"


def test_parse_empty_segment_skipped():
    """Test segment with header but no text is skipped."""
    text = "[voice:冰糖]\n\n[voice:苏打]\n歡迎回來"
    segments = parse_text_file(text)
    assert len(segments) == 1
    assert segments[0].voice == "苏打"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_parser.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'tts'"

- [ ] **Step 3: Implement parser in tts.py**

Add to tts.py before `parse_args`:

```python
from dataclasses import dataclass


@dataclass
class Segment:
    """A segment of text to synthesize."""
    voice: str
    style: str | None
    text: str


def parse_text_file(content: str) -> list[Segment]:
    """Parse text file content into segments."""
    segments = []
    current_voice = "mimo_default"
    current_style = None
    current_text_lines = []

    for line in content.splitlines():
        line = line.strip()

        # Skip comments and empty lines
        if line.startswith("#") or not line:
            continue

        # Detect [voice:X]
        if line.startswith("[voice:") and line.endswith("]"):
            # Save current segment if has text
            if current_text_lines:
                segments.append(Segment(
                    voice=current_voice,
                    style=current_style,
                    text="\n".join(current_text_lines)
                ))
                current_text_lines = []
            current_voice = line[7:-1]  # Extract voice name
            continue

        # Detect [style:X]
        if line.startswith("[style:") and line.endswith("]"):
            current_style = line[8:-1]  # Extract style text
            continue

        # Accumulate text lines
        current_text_lines.append(line)

    # Don't forget last segment
    if current_text_lines:
        segments.append(Segment(
            voice=current_voice,
            style=current_style,
            text="\n".join(current_text_lines)
        ))

    return segments
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parser.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tts.py tests/test_parser.py
git commit -m "feat: add text file parser with segment detection"
```

---

## Task 3: API Client

**Files:**
- Create: `tests/test_api.py`
- Modify: `tts.py` (add API client)

- [ ] **Step 1: Write failing tests for API client**

```python
# tests/test_api.py
import pytest
from unittest.mock import Mock, patch
from tts import MiMoClient, Segment


def test_client_initialization():
    """Test client initializes with correct parameters."""
    client = MiMoClient(api_key="test-key", model="mimo-v2.5-tts")
    assert client.api_key == "test-key"
    assert client.model == "mimo-v2.5-tts"
    assert client.base_url == "https://api.xiaomimimo.com/v1"


@patch("tts.requests.post")
def test_synthesize_with_style(mock_post):
    """Test synthesize sends correct request with style."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.return_value = mock_response

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style="用台灣口音", text="你好")
    result = client.synthesize(segment)

    assert result is not None
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[1]["headers"]["api-key"] == "test-key"
    assert call_args[1]["json"]["messages"][0]["role"] == "user"
    assert call_args[1]["json"]["messages"][1]["role"] == "assistant"


@patch("tts.requests.post")
def test_synthesize_without_style(mock_post):
    """Test synthesize sends correct request without style."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.return_value = mock_response

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style=None, text="你好")
    result = client.synthesize(segment)

    assert result is not None
    call_args = mock_post.call_args
    # Should have only assistant message, no user message
    assert len(call_args[1]["json"]["messages"]) == 1
    assert call_args[1]["json"]["messages"][0]["role"] == "assistant"


@patch("tts.requests.post")
def test_synthesize_api_error(mock_post):
    """Test synthesize handles API errors."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": "Unauthorized"}
    mock_post.return_value = mock_response

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style=None, text="你好")

    with pytest.raises(Exception) as exc_info:
        client.synthesize(segment)
    assert "401" in str(exc_info.value)


@patch("tts.requests.post")
def test_synthesize_retry_on_server_error(mock_post):
    """Test synthesize retries on server errors."""
    # First call fails with 500, second succeeds
    mock_response_fail = Mock()
    mock_response_fail.status_code = 500
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {
        "choices": [{"message": {"audio": {"data": "dGVzdA=="}}}]
    }
    mock_post.side_effect = [mock_response_fail, mock_response_success]

    client = MiMoClient(api_key="test-key")
    segment = Segment(voice="冰糖", style=None, text="你好")
    result = client.synthesize(segment)

    assert result is not None
    assert mock_post.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: FAIL with "ImportError: cannot import name 'MiMoClient'"

- [ ] **Step 3: Implement API client in tts.py**

Add to tts.py after `parse_text_file`:

```python
import time
import base64
import requests


class MiMoClient:
    """Client for MiMo TTS API."""

    def __init__(self, api_key: str, model: str = "mimo-v2.5-tts"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.xiaomimimo.com/v1"
        self.max_retries = 3
        self.initial_backoff = 2.0

    def synthesize(self, segment: Segment) -> bytes:
        """Synthesize a segment and return WAV bytes."""
        messages = []
        if segment.style:
            messages.append({"role": "user", "content": segment.style})
        messages.append({"role": "assistant", "content": segment.text})

        payload = {
            "model": self.model,
            "messages": messages,
            "audio": {
                "format": "wav",
                "voice": segment.voice
            }
        }

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }

        # Retry with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    audio_b64 = data["choices"][0]["message"]["audio"]["data"]
                    return base64.b64decode(audio_b64)

                # Client errors (except 429) - no retry
                if response.status_code < 500 and response.status_code != 429:
                    raise Exception(
                        f"API error {response.status_code}: {response.text}"
                    )

                # Server errors or 429 - retry
                last_error = Exception(
                    f"API error {response.status_code}: {response.text}"
                )

            except requests.exceptions.Timeout:
                last_error = Exception("Request timeout")
            except requests.exceptions.ConnectionError as e:
                last_error = Exception(f"Connection error: {e}")

            # Exponential backoff with jitter
            if attempt < self.max_retries - 1:
                backoff = self.initial_backoff * (2 ** attempt)
                jitter = backoff * 0.5 * (2 * (hash(str(attempt)) % 1000) / 1000 - 1)
                time.sleep(backoff + jitter)

        raise last_error
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tts.py tests/test_api.py
git commit -m "feat: add MiMo API client with retry logic"
```

---

## Task 4: Audio Processing

**Files:**
- Create: `tests/test_audio.py`
- Modify: `tts.py` (add audio processing)

- [ ] **Step 1: Write failing tests for audio processing**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_audio.py -v
```

Expected: FAIL with "ImportError: cannot import name 'concatenate_wav'"

- [ ] **Step 3: Implement audio processing in tts.py**

Add to tts.py after `MiMoClient`:

```python
from pydub import AudioSegment
from io import BytesIO
import struct


def concatenate_wav(wav_list: list[bytes]) -> bytes | None:
    """Concatenate multiple WAV files into one."""
    if not wav_list:
        return None

    if len(wav_list) == 1:
        return wav_list[0]

    # Load first WAV to get parameters
    first = AudioSegment.from_file(BytesIO(wav_list[0]), format="wav")
    combined = first

    # Append remaining WAVs
    for wav_bytes in wav_list[1:]:
        audio = AudioSegment.from_file(BytesIO(wav_bytes), format="wav")
        combined += audio

    # Export to WAV bytes
    output = BytesIO()
    combined.export(output, format="wav")
    return output.getvalue()


def convert_to_mp3(wav_bytes: bytes, output_path: str, bitrate: str, sample_rate: int) -> Path:
    """Convert WAV bytes to MP3 file."""
    audio = AudioSegment.from_file(BytesIO(wav_bytes), format="wav")

    # Set sample rate if different
    if audio.frame_rate != sample_rate:
        audio = audio.set_frame_rate(sample_rate)

    output = Path(output_path)
    audio.export(output, format="mp3", bitrate=bitrate)
    return output
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_audio.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tts.py tests/test_audio.py
git commit -m "feat: add audio processing with WAV concatenation and MP3 conversion"
```

---

## Task 5: Chunking Logic

**Files:**
- Modify: `tts.py` (add chunking function)
- Create: `tests/test_chunking.py`

- [ ] **Step 1: Write failing tests for chunking**

```python
# tests/test_chunking.py
import pytest
from tts import chunk_text


def test_chunk_short_text():
    """Test text shorter than chunk_size is not chunked."""
    text = "你好，歡迎使用。"
    chunks = chunk_text(text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_chinese_sentences():
    """Test chunking by Chinese sentence boundaries."""
    text = "第一句話。第二句話！第三句話？"
    chunks = chunk_text(text, chunk_size=10)
    assert len(chunks) == 3


def test_chunk_english_sentences():
    """Test chunking by English sentence boundaries."""
    text = "First sentence. Second sentence! Third sentence?"
    chunks = chunk_text(text, chunk_size=20)
    assert len(chunks) == 3


def test_chunk_mixed_text():
    """Test chunking mixed Chinese and English text."""
    text = "Hello world. 你好世界！Goodbye."
    chunks = chunk_text(text, chunk_size=15)
    assert len(chunks) == 3


def test_chunk_preserves_inline_tags():
    """Test chunking preserves inline tags."""
    text = "(开心)第一句。[笑]第二句！"
    chunks = chunk_text(text, chunk_size=10)
    assert "(开心)" in chunks[0]
    assert "[笑]" in chunks[1]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_chunking.py -v
```

Expected: FAIL with "ImportError: cannot import name 'chunk_text'"

- [ ] **Step 3: Implement chunking in tts.py**

Add to tts.py after `convert_to_mp3`:

```python
import re


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    current_chunk = ""

    # Split at Chinese and English sentence boundaries
    # Pattern: 。！？ followed by .!? or whitespace
    sentence_pattern = r'(?<=[。！？.!?])\s*'
    sentences = re.split(sentence_pattern, text)

    for sentence in sentences:
        if not sentence.strip():
            continue

        # If adding this sentence exceeds chunk_size, save current and start new
        if current_chunk and len(current_chunk) + len(sentence) > chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += sentence

    # Don't forget last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_chunking.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tts.py tests/test_chunking.py
git commit -m "feat: add text chunking with sentence boundary detection"
```

---

## Task 6: Main Orchestration

**Files:**
- Modify: `tts.py` (add main logic)
- Modify: `tests/test_parser.py` (add integration test)

- [ ] **Step 1: Write integration test**

Add to `tests/test_parser.py`:

```python
@patch("tts.MiMoClient")
@patch("tts.concatenate_wav")
@patch("tts.convert_to_mp3")
def test_main_orchestration(mock_mp3, mock_concat, mock_client):
    """Test main orchestration flow."""
    mock_instance = Mock()
    mock_client.return_value = mock_instance
    mock_instance.synthesize.return_value = b"fake_wav"
    mock_concat.return_value = b"combined_wav"
    mock_mp3.return_value = Path("/tmp/output.mp3")

    from tts import main
    import sys

    # Mock sys.argv
    test_args = ["tts.py", "sample.txt", "--api-key", "test-key"]
    with patch.object(sys, "argv", test_args):
        # Mock file reading
        mock_content = "[voice:冰糖]\n你好"
        with patch("builtins.open", mock_open(read_data=mock_content)):
            main()

    # Verify calls
    mock_instance.synthesize.assert_called_once()
    mock_concat.assert_called_once()
    mock_mp3.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_parser.py::test_main_orchestration -v
```

Expected: FAIL with "NameError: name 'main' is not defined"

- [ ] **Step 3: Implement main orchestration in tts.py**

Update `main()` function in tts.py:

```python
import os
from unittest.mock import mock_open


def main():
    """Main entry point."""
    args = parse_args()

    # Get API key
    api_key = args.api_key or os.environ.get("TTS_API_KEY")
    if not api_key:
        print("Error: API key required. Use --api-key or set TTS_API_KEY env var", file=sys.stderr)
        sys.exit(1)

    # Read input file
    if not args.input.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    content = args.input.read_text(encoding="utf-8")
    if not content.strip():
        print(f"Warning: Empty file: {args.input}", file=sys.stderr)
        sys.exit(0)

    # Parse segments
    segments = parse_text_file(content)
    if not segments:
        print(f"Warning: No segments found in {args.input}", file=sys.stderr)
        sys.exit(0)

    # Initialize client
    client = MiMoClient(api_key=api_key, model=args.model)

    # Process segments
    wav_files = []
    total_time = 0

    for i, segment in enumerate(segments, 1):
        # Chunk text if needed
        text_chunks = chunk_text(segment.text, args.chunk_size)

        for chunk in text_chunks:
            chunk_segment = Segment(
                voice=segment.voice,
                style=segment.style,
                text=chunk
            )

            if args.verbose:
                print(f"[{i}/{len(segments)}] {segment.voice}: \"{chunk[:30]}...\"", end="", flush=True)

            start_time = time.time()
            try:
                wav_bytes = client.synthesize(chunk_segment)
                wav_files.append(wav_bytes)
                elapsed = time.time() - start_time
                total_time += elapsed

                if args.verbose:
                    print(f" → OK ({elapsed:.1f}s)")

            except Exception as e:
                if args.verbose:
                    print(f" → FAILED: {e}")
                raise

    # Concatenate and convert
    if wav_files:
        combined_wav = concatenate_wav(wav_files)
        output_path = args.output or args.input.with_suffix(".mp3")
        convert_to_mp3(combined_wav, str(output_path), args.bitrate, args.sample_rate)

        if args.verbose:
            print(f"\n[Done] {output_path} ({total_time:.1f}s total, {len(segments)} segments)")
        else:
            print(f"Generated: {output_path}")
    else:
        print("Warning: No audio generated", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tts.py tests/test_parser.py
git commit -m "feat: add main orchestration with CLI integration"
```

---

## Task 7: Final Testing & Cleanup

**Files:**
- Modify: `tts.py` (add missing imports)
- Create: `tests/__init__.py`

- [ ] **Step 1: Add missing imports to tts.py**

Ensure tts.py has all required imports at the top:

```python
#!/usr/bin/env python3
"""MiMo TTS CLI Tool - Read .txt files and generate MP3 audio."""

import argparse
import os
import sys
import time
import re
import base64
from pathlib import Path
from dataclasses import dataclass
from io import BytesIO

import requests
from pydub import AudioSegment
```

- [ ] **Step 2: Create tests/__init__.py**

```python
# tests/__init__.py
```

- [ ] **Step 3: Run all tests one final time**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 4: Test CLI manually**

```bash
# Test help
python tts.py --help

# Test with sample file (requires API key)
# python tts.py sample.txt --api-key YOUR_KEY -v
```

- [ ] **Step 5: Commit final changes**

```bash
git add -A
git commit -m "feat: complete MiMo TTS CLI tool"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project setup | `requirements.txt`, `tts.py` |
| 2 | Text file parser | `tts.py`, `tests/test_parser.py` |
| 3 | API client | `tts.py`, `tests/test_api.py` |
| 4 | Audio processing | `tts.py`, `tests/test_audio.py` |
| 5 | Chunking logic | `tts.py`, `tests/test_chunking.py` |
| 6 | Main orchestration | `tts.py`, `tests/test_parser.py` |
| 7 | Final testing | `tts.py`, `tests/__init__.py` |

**Total estimated time:** 25-35 minutes
