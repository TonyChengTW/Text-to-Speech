#!/usr/bin/env python3
"""MiMo TTS CLI Tool - Read .txt files and generate MP3 audio."""

import argparse
import base64
import random
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from io import BytesIO

import requests
from pydub import AudioSegment


@dataclass
class Segment:
    """A segment of text to synthesize."""
    voice: str
    style: Optional[str]
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
            current_style = None  # Reset style for new segment
            continue

        # Detect [style:X]
        if line.startswith("[style:") and line.endswith("]"):
            current_style = line[7:-1]  # Extract style text
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

    combined = b"".join(wav_list)
    return b"RIFF" + struct.pack("<I", len(combined) + 4) + b"WAVE" + combined


def convert_to_mp3(wav_bytes: bytes, output_path: str, bitrate: str, sample_rate: int) -> Path:
    """Convert WAV bytes to MP3 file."""
    audio = AudioSegment.from_wav(BytesIO(wav_bytes))
    output = Path(output_path)
    audio.export(output, format="mp3", bitrate=bitrate)
    return output


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
