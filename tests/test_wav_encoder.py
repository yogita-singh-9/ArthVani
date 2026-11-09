"""
tests/test_wav_encoder.py — Tests for the WAV header structure and sample rate.

Validates that client-side-style 16-bit PCM 16 kHz mono WAV blobs pass
through _ensure_wav() unchanged (RIFF header present).
"""

from __future__ import annotations

import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest


# ════════════════════════════════════════════════════════════
# WAV building helper (mimics the browser-side encoder)
# ════════════════════════════════════════════════════════════

def build_wav(samples: bytes, sample_rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    """
    Build a minimal valid WAV blob from raw PCM samples.

    Layout (little-endian):
      RIFF<size>WAVEfmt <16><1><ch><sr><br><ba><bits>data<size><samples>
    """
    num_samples   = len(samples)
    byte_rate     = sample_rate * channels * bits // 8
    block_align   = channels * bits // 8
    data_size     = num_samples
    total_size    = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        total_size,
        b"WAVE",
        b"fmt ",
        16,              # fmt chunk size
        1,               # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )
    return header + samples


# ════════════════════════════════════════════════════════════
# 1. WAV header tests
# ════════════════════════════════════════════════════════════

def test_wav_starts_with_riff():
    wav = build_wav(b"\x00\x00" * 100)
    assert wav[:4] == b"RIFF"


def test_wav_contains_wave_marker():
    wav = build_wav(b"\x00\x00" * 100)
    assert wav[8:12] == b"WAVE"


def test_wav_sample_rate_field():
    wav = build_wav(b"\x00\x00" * 100, sample_rate=16000)
    # sample rate is at bytes 24-28 (little-endian int)
    sr = struct.unpack_from("<I", wav, 24)[0]
    assert sr == 16000


def test_wav_channels_field():
    wav = build_wav(b"\x00\x00" * 100, channels=1)
    ch = struct.unpack_from("<H", wav, 22)[0]
    assert ch == 1


def test_wav_bits_field():
    wav = build_wav(b"\x00\x00" * 100, bits=16)
    bits = struct.unpack_from("<H", wav, 34)[0]
    assert bits == 16


def test_wav_data_chunk_marker():
    wav = build_wav(b"\x00\x01" * 50)
    assert wav[36:40] == b"data"


def test_wav_total_size_correct():
    samples = b"\x00\x01" * 100   # 200 bytes
    wav = build_wav(samples)
    # RIFF chunk size = total file - 8
    riff_size = struct.unpack_from("<I", wav, 4)[0]
    assert riff_size == len(wav) - 8


def test_wav_data_size_correct():
    samples = b"\x00\x01" * 100
    wav = build_wav(samples)
    data_size = struct.unpack_from("<I", wav, 40)[0]
    assert data_size == len(samples)


# ════════════════════════════════════════════════════════════
# 2. _ensure_wav pass-through (server side)
# ════════════════════════════════════════════════════════════

def test_ensure_wav_passes_valid_wav():
    """A valid RIFF WAV must be returned unchanged."""
    from main import _ensure_wav
    samples = b"\x00\x00" * 1600   # 100ms of silence at 16 kHz mono 16-bit
    wav = build_wav(samples)
    result = _ensure_wav(wav)
    assert result == wav


def test_ensure_wav_returns_bytes_for_unknown():
    """Unknown format returns something (bytes), doesn't raise."""
    from main import _ensure_wav
    result = _ensure_wav(b"not a wav file at all")
    assert isinstance(result, bytes)


# ════════════════════════════════════════════════════════════
# 3. WAV parameters for Gnani STT
# ════════════════════════════════════════════════════════════

def test_gnani_compatible_wav():
    """
    A 16 kHz, mono, 16-bit WAV is Gnani STT-compatible.
    Verify our builder produces exactly these parameters.
    """
    samples = bytes(3200 * 2)  # 100ms at 16kHz mono 16-bit = 3200 samples × 2 bytes
    wav = build_wav(samples, sample_rate=16000, channels=1, bits=16)

    sr   = struct.unpack_from("<I", wav, 24)[0]
    ch   = struct.unpack_from("<H", wav, 22)[0]
    bits = struct.unpack_from("<H", wav, 34)[0]

    assert sr   == 16000, f"Sample rate should be 16000, got {sr}"
    assert ch   == 1,     f"Channels should be 1 (mono), got {ch}"
    assert bits == 16,    f"Bit depth should be 16, got {bits}"

