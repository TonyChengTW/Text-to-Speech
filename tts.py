#!/usr/bin/env python3
"""MiMo TTS CLI Tool - Read .txt files and generate MP3 audio."""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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
