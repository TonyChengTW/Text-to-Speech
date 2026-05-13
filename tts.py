#!/usr/bin/env python3
"""MiMo TTS CLI Tool - Read .txt files and generate MP3 audio."""

__version__ = "1.0.0"

import argparse
import os
import sys
import time
import re
import base64
import random
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, Union
from io import BytesIO

import requests
from pydub import AudioSegment
from dotenv import load_dotenv

VOICE_NAME_MAP = {
    "蘇打": "苏打",
    "白樺": "白桦",
}

SCRIPT_CHARACTER_VOICE_MAP = {
    "涼子": "冰糖",
    "澈也": "茉莉",
    "阿Ken": "苏打",
    "小柔": "白桦",
    "老P": "Milo",
    "小美": "Chloe",
    "導演": "Dean",
}

def _resolve_voice(voice: str) -> str:
    """Resolve script character name to API voice ID."""
    return SCRIPT_CHARACTER_VOICE_MAP.get(voice, "mimo_default")


@dataclass
class Segment:
    """A segment of text to synthesize."""
    voice: str
    style: Optional[str]
    text: str


class ProfileManager:
    """Manages voice clone profiles in the profiles/ directory."""

    SUPPORTED_FORMATS = {".mp3": "audio/mpeg", ".wav": "audio/wav"}

    def __init__(self, profiles_dir: Union[str, Path] = "profiles"):
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


def _is_voice_tag_line(line: str) -> bool:
    return bool(re.match(r"^\[voice:[^\]]+\]$", line.strip()))


def _is_style_tag_line(line: str) -> bool:
    return bool(re.match(r"^\[style:[^\]]+\]$", line.strip()))


_SCRIPT_SKIP_KEYWORDS = {"場景", "人物", "動作", "音樂", "燈光", "道具", "備註"}

def _is_script_dialogue(line: str) -> Tuple[bool, Optional[str], str]:
    """Detect script-format dialogue like '涼子：你好'.

    Returns (is_dialogue, voice, text).
    """
    m = re.match(r"^([a-zA-Z0-9\u4e00-\u9fff]{1,6})：(.*)$", line.strip())
    if not m:
        return False, None, ""
    voice, text = m.group(1), m.group(2)
    if voice in _SCRIPT_SKIP_KEYWORDS:
        return False, None, ""
    return True, voice, text


def parse_text_file(content: str) -> list[Segment]:
    """Parse text file content into segments.
    
    Supports global default style: if [style:] appears before any [voice:],
    it becomes the default style for all segments that don't specify their own.
    """
    segments = []
    current_voice = "mimo_default"
    current_style = None
    current_text_lines = []
    default_style = None  # Global default style
    has_voice = False  # Track if we've seen any [voice:] tag

    for line in content.splitlines():
        line = line.strip()

        if line.startswith("#") or not line:
            continue

        if _is_voice_tag_line(line):
            if current_text_lines:
                final_style = current_style if current_style is not None else default_style
                segments.append(Segment(
                    voice=current_voice,
                    style=final_style,
                    text="\n".join(current_text_lines)
                ))
                current_text_lines = []
            current_voice = line[7:-1]
            current_style = None
            has_voice = True
            continue

        if _is_style_tag_line(line):
            style_text = line[7:-1]
            if not has_voice:
                default_style = style_text
            else:
                current_style = style_text
            continue

        is_dialogue, voice, text = _is_script_dialogue(line)
        if is_dialogue:
            if current_text_lines:
                final_style = current_style if current_style is not None else default_style
                segments.append(Segment(
                    voice=current_voice,
                    style=final_style,
                    text="\n".join(current_text_lines)
                ))
                current_text_lines = []
            current_voice = voice
            current_style = None
            has_voice = True
            if text:
                current_text_lines.append(text)
            continue

        current_text_lines.append(line)

    # Don't forget last segment
    if current_text_lines:
        # Apply default style if no style specified for this segment
        final_style = current_style if current_style is not None else default_style
        segments.append(Segment(
            voice=current_voice,
            style=final_style,
            text="\n".join(current_text_lines)
        ))

    return segments


class MiMoClient:
    """Client for MiMo TTS API."""

    def __init__(self, api_key: str, model: str = "mimo-v2.5-tts"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://token-plan-cn.xiaomimimo.com/v1"
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
                "voice": SCRIPT_CHARACTER_VOICE_MAP.get(
                    segment.voice,
                    VOICE_NAME_MAP.get(segment.voice, segment.voice)
                )
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

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

                if response.status_code < 500 and response.status_code != 429:
                    raise Exception(
                        f"API error {response.status_code}: {response.text}"
                    )

                last_error = Exception(
                    f"API error {response.status_code}: {response.text}"
                )

            except requests.exceptions.Timeout:
                last_error = Exception("Request timeout")
            except requests.exceptions.ConnectionError as e:
                last_error = Exception(f"Connection error: {e}")

            if attempt < self.max_retries - 1:
                backoff = self.initial_backoff * (2 ** attempt)
                sleep_time = random.uniform(0, backoff)
                time.sleep(sleep_time)

        raise last_error


def concatenate_wav(wav_list: list[bytes]) -> Optional[bytes]:
    """Concatenate multiple WAV files into one."""
    if not wav_list:
        return None

    if len(wav_list) == 1:
        return wav_list[0]

    first = AudioSegment.from_file(BytesIO(wav_list[0]), format="wav")
    combined = first

    for wav_bytes in wav_list[1:]:
        audio = AudioSegment.from_file(BytesIO(wav_bytes), format="wav")
        combined += audio

    output = BytesIO()
    combined.export(output, format="wav")
    return output.getvalue()


def convert_to_mp3(wav_bytes: bytes, output_path: str, bitrate: str, sample_rate: int) -> Path:
    """Convert WAV bytes to MP3 file."""
    audio = AudioSegment.from_file(BytesIO(wav_bytes), format="wav")
    if audio.frame_rate != sample_rate:
        audio = audio.set_frame_rate(sample_rate)
    output = Path(output_path)
    audio.export(output, format="mp3", bitrate=bitrate)
    return output


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    current_chunk = ""

    # Split at Chinese and English sentence boundaries
    sentence_pattern = r'(?<=[。！？.!?])\s*'
    sentences = re.split(sentence_pattern, text)

    for sentence in sentences:
        if not sentence.strip():
            continue

        # Single sentence longer than chunk_size — flush and add as its own chunk
        if len(sentence) > chunk_size:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
                current_chunk = ""
            chunks.append(sentence.strip())
            continue

        # Always break at sentence boundaries when total text exceeds chunk_size
        if current_chunk:
            chunks.append(current_chunk.strip())
        current_chunk = sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def _is_valid_segment_text(text: str) -> bool:
    """Check if segment text is worth synthesizing."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped in ("…", "—", "——", "——…", "…—", "...", "？", "！", "。"):
        return False
    if re.match(r"^=+$", stripped):
        return False
    if stripped.startswith("================================"):
        return False
    if re.match(r"^[=\-—\s]+$", stripped):
        return False
    if len(stripped) < 2:
        return False
    return True


def _is_valid_segment(segment: "Segment") -> bool:
    """Check if entire segment (voice + text) is worth synthesizing."""
    if not _is_valid_segment_text(segment.text):
        return False
    if segment.voice == "mimo_default":
        first_line = segment.text.strip().split("\n")[0]
        if re.match(r"^[=\-—【\[]", first_line):
            return False
        if len(segment.text.strip()) < 10:
            return False
    return True


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate MP3 audio from .txt files using MiMo TTS API"
    )
    parser.add_argument("input", nargs="?", type=Path, help="Input .txt file path")
    parser.add_argument("--api-key", help="API key (or set TTS_API_KEY env var)")
    parser.add_argument("--model", default="mimo-v2.5-tts", help="Model name")
    parser.add_argument("--output", type=Path, help="Output MP3 path")
    parser.add_argument("--chunk-size", type=int, default=4000, help="Max chars per API request")
    parser.add_argument("--sample-rate", type=int, default=24000, help="Audio sample rate")
    parser.add_argument("--bitrate", default="192k", help="MP3 bitrate")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show progress")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args()


def main():
    """Main entry point."""
    load_dotenv()  # Load .env file if present
    args = parse_args()

    api_key = args.api_key or os.environ.get("TTS_API_KEY")
    if not api_key:
        print("錯誤：需要 API 金鑰。請使用 --api-key 參數、設定 TTS_API_KEY 環境變數、或建立 .env 檔案", file=sys.stderr)
        sys.exit(1)

    if not args.input.exists():
        print(f"錯誤：找不到檔案：{args.input}", file=sys.stderr)
        sys.exit(1)

    content = args.input.read_text(encoding="utf-8")
    if not content.strip():
        print(f"警告：空檔案：{args.input}", file=sys.stderr)
        sys.exit(0)

    segments = parse_text_file(content)

    active_segments = [(i, s) for i, s in enumerate(segments) if _is_valid_segment(s)]
    if not active_segments:
        print(f"警告：在 {args.input} 中找不到有效段落", file=sys.stderr)
        sys.exit(0)

    valid_count = len(active_segments)
    print(f"解析完成：{len(segments)} 段落 → {valid_count} 有效片段", flush=True)

    client = MiMoClient(api_key=api_key, model=args.model)

    wav_files = []
    total_time = 0

    for idx, (orig_idx, segment) in enumerate(active_segments, 1):
        text_chunks = chunk_text(segment.text, args.chunk_size)

        for chunk in text_chunks:
            chunk_segment = Segment(
                voice=segment.voice,
                style=segment.style,
                text=chunk
            )

            print(f"[{idx}/{valid_count}] {segment.voice}: {chunk[:20]}...", end="", flush=True)

            start_time = time.time()
            try:
                wav_bytes = client.synthesize(chunk_segment)
                wav_files.append(wav_bytes)
                elapsed = time.time() - start_time
                total_time += elapsed
                avg_time = total_time / idx
                remaining = avg_time * (valid_count - idx)
                print(f" ✓ ({elapsed:.1f}s, 預估剩余 {remaining:.0f}s)")

            except Exception as e:
                print(f" ✗ {e}")
                raise

    if wav_files:
        combined_wav = concatenate_wav(wav_files)
        output_path = args.output or args.input.with_suffix(".mp3")
        convert_to_mp3(combined_wav, str(output_path), args.bitrate, args.sample_rate)

        if args.verbose:
            print(f"\n[完成] {output_path} (共 {total_time:.1f}s，{valid_count} 個有效片段)")
        else:
            print(f"已產生：{output_path}")
    else:
        print("警告：未產生音訊", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
