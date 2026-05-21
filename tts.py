#!/usr/bin/env python3
"""MiMo TTS CLI Tool - Read .txt files and generate MP3 audio."""

__version__ = "1.1.0"

import argparse
import os
import sys
import time
import re
import base64
import random
from pathlib import Path
from dataclasses import dataclass

VOICE_MAPPING = {
    "蘇打": "苏打",
    "白樺": "白桦",
}

GEMINI_VOICE_MAPPING = {
    "冰糖": "Aoede",
    "茉莉": "Kore",
    "蘇打": "Puck",
    "白樺": "Charon",
    "Mia": "Leda",
    "Chloe": "Sulafat",
    "Milo": "Fenrir",
    "Dean": "Enceladus",
    "mimo_default": "Aoede",
}

GEMINI_MODELS = {"gemini-2.5-flash-preview-tts", "gemini-2.0-flash-preview-tts", "gemini-2.5-flash-tts"}
MIMO_MODELS = {"mimo-v2.5-tts"}

DEFAULT_STYLE = "語調自然，不要用中國大陸捲舌腔調"
from io import BytesIO
from typing import Optional, Union
import wave
from abc import ABC, abstractmethod

import requests
from pydub import AudioSegment


@dataclass
class Segment:
    """A segment of text to synthesize."""
    voice: str
    style: Optional[str]
    text: str


class ProfileManager:
    """Manages voice clone profiles in the profiles/ directory."""

    SUPPORTED_FORMATS = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/x-m4a"}

    def __init__(self, profiles_dir: Union[str, Path] = "profiles"):
        self.profiles_dir = Path(profiles_dir)

    def _ensure_dir(self):
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _validate_audio(self, audio_path: str) -> str:
        """Validate audio file with pydub, return MIME type."""
        try:
            AudioSegment.from_file(audio_path)
            ext = Path(audio_path).suffix.lower()
            if ext not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {ext}")
            return self.SUPPORTED_FORMATS[ext]
        except Exception as e:
            raise ValueError(f"Invalid audio: {e}")

    def add_profile(self, name: str, audio_path: str) -> dict:
        """Add a voice clone profile. Converts audio to mp3 if needed."""
        self._ensure_dir()
        if self.profile_exists(name):
            raise ValueError(f"Profile '{name}' already exists")

        self._validate_audio(audio_path)
        src_path = Path(audio_path)
        ext = src_path.suffix.lower()
        dest_audio = self.profiles_dir / f"{name}.mp3"

        if ext == ".m4a":
            audio = AudioSegment.from_file(audio_path)
            audio.export(dest_audio, format="mp3", bitrate="192k")
        else:
            import shutil
            shutil.copy2(src_path, dest_audio)

        from datetime import date
        profile = {
            "name": name,
            "audio_file": f"{name}.mp3",
            "created_at": date.today().isoformat(),
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


def _is_clone_tag_line(line: str) -> bool:
    return bool(re.match(r"^\[clone:[^\]]+\]$", line.strip()))


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
            current_style = None  # Reset style for new segment
            continue

        # Detect [style:X]
        if line.startswith("[style:") and line.endswith("]"):
            current_style = line[7:-1]  # Extract style text
            continue

        # Detect [clone:X]
        if _is_clone_tag_line(line):
            if current_text_lines:
                segments.append(Segment(
                    voice=current_voice,
                    style=current_style,
                    text="\n".join(current_text_lines)
                ))
                current_text_lines = []
            current_voice = f"clone:{line[7:-1]}"
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


class BaseTTSClient(ABC):
    @abstractmethod
    def synthesize(self, segment: Segment) -> bytes:
        """Synthesize a segment and return WAV bytes."""
        raise NotImplementedError


class MiMoClient(BaseTTSClient):
    """Client for MiMo TTS API."""

    def __init__(self, api_key: str, model: str = "mimo-v2.5-tts", profile_manager=None):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://token-plan-cn.xiaomimimo.com/v1"
        self.max_retries = 3
        self.initial_backoff = 2.0
        self.profile_manager = profile_manager if profile_manager is not None else ProfileManager()

    def synthesize(self, segment: Segment) -> bytes:
        """Synthesize a segment and return WAV bytes."""
        messages = []
        if segment.style:
            messages.append({"role": "user", "content": segment.style})
        messages.append({"role": "assistant", "content": segment.text})

        is_clone = segment.voice.startswith("clone:")

        if is_clone:
            profile_name = segment.voice[6:]
            try:
                audio_path = self.profile_manager.get_audio_path(profile_name)
            except FileNotFoundError as e:
                raise ValueError(f"Clone profile '{profile_name}' not found: {e}")
            ext = audio_path.suffix.lower()
            if ext == ".m4a":
                audio = AudioSegment.from_file(audio_path)
                audio_bytes = BytesIO()
                audio.export(audio_bytes, format="mp3")
                audio_b64 = base64.b64encode(audio_bytes.getvalue()).decode("utf-8")
                mime = "audio/mpeg"
            else:
                with open(audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode("utf-8")
                mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"
            voice_value = f"data:{mime};base64,{audio_b64}"
            model_name = "mimo-v2.5-tts-voiceclone"
        else:
            voice_value = VOICE_MAPPING.get(segment.voice, segment.voice)
            model_name = self.model

        payload = {
            "model": model_name,
            "messages": messages,
            "audio": {
                "format": "wav",
                "voice": voice_value
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
                    timeout=600
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


class GeminiTTSClient(BaseTTSClient):
    """Client for Gemini TTS API."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-preview-tts"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.max_retries = 3
        self.initial_backoff = 2.0

    def _pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
        buf = BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def synthesize(self, segment: Segment) -> bytes:
        is_clone = segment.voice.startswith("clone:")
        if is_clone:
            raise ValueError("Voice cloning is not supported with Gemini TTS")

        voice_name = GEMINI_VOICE_MAPPING.get(segment.voice, "Aoede")
        
        prompt_text = segment.text
        if segment.style:
            prompt_text = f"{segment.style}。{segment.text}"

        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                }
            }
        }

        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/{self.model}:generateContent",
                    json=payload,
                    headers=headers,
                    timeout=600
                )

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise Exception("No candidates in Gemini response")
                    
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts or "inlineData" not in parts[0]:
                        raise Exception("No audio data in Gemini response")
                        
                    audio_b64 = parts[0]["inlineData"]["data"]
                    pcm_bytes = base64.b64decode(audio_b64)
                    return self._pcm_to_wav(pcm_bytes)

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


class TTSClientFactory:
    @staticmethod
    def create(model: str, mimo_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None, profile_manager=None) -> BaseTTSClient:
        if model in GEMINI_MODELS:
            if not gemini_api_key:
                raise ValueError("Gemini model selected but GEMINI_API_KEY is not set.")
            return GeminiTTSClient(api_key=gemini_api_key, model=model)
        elif model in MIMO_MODELS:
            if not mimo_api_key:
                raise ValueError("MiMo model selected but TTS_API_KEY is not set.")
            return MiMoClient(api_key=mimo_api_key, model=model, profile_manager=profile_manager)
        else:
            supported = ", ".join(sorted(GEMINI_MODELS | MIMO_MODELS))
            raise ValueError(f"Unknown model '{model}'. Supported models are: {supported}")


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


def parse_args():
    """Parse command line arguments."""
    raw = sys.argv[1:]
    clone_mode = "--clone-profile" in raw

    parser = argparse.ArgumentParser(
        description="Generate MP3 audio from .txt files using MiMo TTS API"
    )
    if clone_mode:
        parser.add_argument("--clone-profile", action="store_true")
        parser.add_argument("subcommand", choices=["add", "list", "delete"])
        parser.add_argument("clone_profile_name", nargs="?")
        parser.add_argument("--audio", dest="clone_profile_audio")
        parser.add_argument("input", nargs="?", type=Path)
        parser.add_argument("--api-key")
        parser.add_argument("--gemini-api-key")
        parser.add_argument("--model", default="mimo-v2.5-tts")
        parser.add_argument("--output", type=Path)
        parser.add_argument("--chunk-size", type=int, default=4000)
        parser.add_argument("--sample-rate", type=int, default=24000)
        parser.add_argument("--bitrate", default="192k")
        parser.add_argument("-v", "--verbose", action="store_true")
    else:
        parser.add_argument("input", nargs="?", type=Path)
        parser.add_argument("--api-key")
        parser.add_argument("--gemini-api-key")
        parser.add_argument("--model", default="mimo-v2.5-tts")
        parser.add_argument("--output", type=Path)
        parser.add_argument("--chunk-size", type=int, default=4000)
        parser.add_argument("--sample-rate", type=int, default=24000)
        parser.add_argument("--bitrate", default="192k")
        parser.add_argument("-v", "--verbose", action="store_true")
        parser.add_argument("--clone-profile", action="store_true")
        parser.add_argument("subcommand", nargs="?", choices=["add", "list", "delete"])
        parser.add_argument("clone_profile_name", nargs="?")
        parser.add_argument("--audio", dest="clone_profile_audio")

    return parser.parse_args()


def main():
    """Main entry point."""
    from dotenv import dotenv_values
    env_vars = dotenv_values(".env")

    args = parse_args()
    profile_manager = ProfileManager()

    if args.clone_profile:
        if not args.subcommand:
            print("錯誤：需要 subcommand (add/list/delete)", file=sys.stderr)
            sys.exit(1)
        action = args.subcommand

        if action == "add":
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

        if action == "list":
            profiles = profile_manager.list_profiles()
            if not profiles:
                print("尚無 clone profiles")
            else:
                for p in profiles:
                    print(f"{p['name']}  | {p['audio_file']} | {p['created_at']}")
            sys.exit(0)

        if action == "delete":
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

    mimo_api_key = args.api_key or os.environ.get("TTS_API_KEY") or env_vars.get("TTS_API_KEY")
    gemini_api_key = args.gemini_api_key or os.environ.get("GEMINI_API_KEY") or env_vars.get("GEMINI_API_KEY")

    if not args.input:
        print("Error: input file required (or use --clone-profile add/list/delete for profile management)", file=sys.stderr)
        sys.exit(1)

    if not args.input.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    content = args.input.read_text(encoding="utf-8")
    if not content.strip():
        print(f"Warning: Empty file: {args.input}", file=sys.stderr)
        sys.exit(0)

    segments = parse_text_file(content)
    if not segments:
        print(f"Warning: No segments found in {args.input}", file=sys.stderr)
        sys.exit(0)

    try:
        client = TTSClientFactory.create(
            model=args.model,
            mimo_api_key=mimo_api_key,
            gemini_api_key=gemini_api_key,
            profile_manager=profile_manager
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    wav_files = []
    total_time = 0

    for i, segment in enumerate(segments, 1):
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
                else:
                    print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

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


if __name__ == "__main__":
    main()
