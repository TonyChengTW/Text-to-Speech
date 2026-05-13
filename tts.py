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
