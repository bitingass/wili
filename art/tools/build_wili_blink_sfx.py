#!/usr/bin/env python3
"""Rebuild Wili's blink sound effect (深呼 3B) and repack FMOD FSB5/FEV assets.

Generates art/source/audio/wili_blink/blink.wav (48 kHz mono 16-bit PCM),
repacks sound/wili_blink_bank.fsb (FSB5 PCM16), and updates the waveform
duration field in sound/wili_blink.fev while preserving the bank compat hash.
"""

from __future__ import annotations

import math
import os
import struct
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
FSB5_FREQ_48000 = 9
FSB5_MODE_PCM16 = 2
FEV_BANK_HASH_OFFSET = 0x17F
FEV_WAVEFORM_NAME = b"blink.wav\x00"
FEV_LENGTH_MS_OFFSET = 0x361

REPO_ROOT = Path(__file__).resolve().parents[2]
WAV_PATH = REPO_ROOT / "art" / "source" / "audio" / "wili_blink" / "blink.wav"
FSB_PATH = REPO_ROOT / "sound" / "wili_blink_bank.fsb"
FEV_PATH = REPO_ROOT / "sound" / "wili_blink.fev"


def svf_filter(x: np.ndarray, cutoff_hz: np.ndarray, q: np.ndarray, mode: str = "bp") -> np.ndarray:
    """Zero-Delay Feedback (Cytomic) State Variable Filter with per-sample cutoff & Q."""
    n = len(x)
    out = np.empty(n, dtype=np.float64)
    ic1eq = 0.0
    ic2eq = 0.0
    fc = np.clip(cutoff_hz, 20.0, SR * 0.45)
    g = np.tan(np.pi * fc / SR)
    k = 1.0 / np.clip(q, 0.3, 25.0)
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    if mode == "bp":
        for i in range(n):
            v3 = x[i] - ic2eq
            v1 = a1[i] * ic1eq + a2[i] * v3
            v2 = ic2eq + a2[i] * ic1eq + a3[i] * v3
            ic1eq = 2.0 * v1 - ic1eq
            ic2eq = 2.0 * v2 - ic2eq
            out[i] = v1
    elif mode == "lp":
        for i in range(n):
            v3 = x[i] - ic2eq
            v1 = a1[i] * ic1eq + a2[i] * v3
            v2 = ic2eq + a2[i] * ic1eq + a3[i] * v3
            ic1eq = 2.0 * v1 - ic1eq
            ic2eq = 2.0 * v2 - ic2eq
            out[i] = v2
    elif mode == "hp":
        for i in range(n):
            v3 = x[i] - ic2eq
            v1 = a1[i] * ic1eq + a2[i] * v3
            v2 = ic2eq + a2[i] * ic1eq + a3[i] * v3
            ic1eq = 2.0 * v1 - ic1eq
            ic2eq = 2.0 * v2 - ic2eq
            out[i] = x[i] - k[i] * v1 - v2
    else:
        raise ValueError(f"Unsupported SVF mode: {mode}")
    return out


def svf_const(x: np.ndarray, fc: float, q: float = 0.707, mode: str = "lp") -> np.ndarray:
    n = len(x)
    return svf_filter(x, np.full(n, fc, dtype=np.float64), np.full(n, q, dtype=np.float64), mode=mode)


def fft_eq(x: np.ndarray, gain_fn) -> np.ndarray:
    n = len(x)
    nfft = 1 << (n * 2 - 1).bit_length()
    X = np.fft.rfft(x, n=nfft)
    freqs = np.fft.rfftfreq(nfft, d=1.0 / SR)
    return np.fft.irfft(X * gain_fn(freqs), n=nfft)[:n]


def highpass_smooth(freqs: np.ndarray, fc: float, order: float = 3.0) -> np.ndarray:
    f = np.maximum(freqs, 1e-3)
    return 1.0 / np.sqrt(1.0 + np.power(fc / f, 2.0 * order))


def lowpass_smooth(freqs: np.ndarray, fc: float, order: float = 2.5) -> np.ndarray:
    f = np.maximum(freqs, 1e-3)
    return 1.0 / np.sqrt(1.0 + np.power(f / fc, 2.0 * order))


def colored_noise(rng: np.random.Generator, n: int, alpha: float = 1.5) -> np.ndarray:
    w = rng.standard_normal(n)
    W = np.fft.rfft(w)
    freqs = np.fft.rfftfreq(n, d=1.0 / SR)
    scale = np.zeros_like(freqs)
    scale[1:] = 1.0 / np.power(freqs[1:], alpha * 0.5)
    y = np.fft.irfft(W * scale, n=n)
    y /= np.std(y) + 1e-12
    return y


def wind_swell_env(t: np.ndarray, t_pk: float, dur: float, p_atk: float = 1.6, p_rel: float = 2.15) -> np.ndarray:
    env = np.zeros_like(t)
    m1 = (t >= 0.0) & (t < t_pk)
    if t_pk > 0:
        u = t[m1] / t_pk
        env[m1] = np.power(0.5 - 0.5 * np.cos(np.pi * u), p_atk * 0.65)
    m2 = (t >= t_pk) & (t <= dur)
    if dur > t_pk:
        u = (t[m2] - t_pk) / (dur - t_pk)
        env[m2] = np.power(np.clip(1.0 - u, 0.0, 1.0), p_rel)
    return env


def soft_air_space(x: np.ndarray, lp_hz: float = 900.0, wet: float = 0.16) -> np.ndarray:
    taps = [(0.0085, 0.36), (0.0172, -0.25), (0.0294, 0.17), (0.0445, -0.10)]
    ref = np.zeros_like(x)
    n = len(x)
    for dt, g in taps:
        d = int(dt * SR)
        if d < n:
            ref[d:] += g * x[: n - d]
    ref = svf_const(ref, lp_hz, 0.7, "lp")
    return x + wet * ref


def synthesize_blink_deep_hu_3b() -> np.ndarray:
    """Synthesize approved '深呼 3B' (deep, hushed shadow-wind '呼' at 48 kHz mono)."""
    rng = np.random.default_rng(8303)
    dur = 0.33
    t_pk = 0.086
    f1_base, f1_rise, f1_end = 138.0, 112.0, 122.0
    f2_base, f2_rise, f2_end = 290.0, 215.0, 240.0
    low_lp, low_hp, final_lp = 215.0, 58.0, 760.0
    target_rms_db, max_peak_db = -26.5, -13.0

    n = int(SR * dur)
    t = np.arange(n) / SR
    env = wind_swell_env(t, t_pk, dur, p_atk=1.6, p_rel=2.15)
    tau1 = (dur - t_pk) * 0.42
    tau2 = (dur - t_pk) * 0.36

    f1 = np.where(
        t < t_pk,
        f1_base + f1_rise * np.sin(0.5 * np.pi * t / t_pk),
        f1_end + (f1_base + f1_rise - f1_end) * np.exp(-(t - t_pk) / tau1),
    )
    f2 = np.where(
        t < t_pk,
        f2_base + f2_rise * np.sin(0.5 * np.pi * t / t_pk),
        f2_end + (f2_base + f2_rise - f2_end) * np.exp(-(t - t_pk) / tau2),
    )

    turb = 0.86 + 0.16 * np.tanh(svf_const(rng.standard_normal(n), 72.0, 0.7, "lp"))
    layer_u = svf_filter(colored_noise(rng, n, 1.60) * turb, f1, np.full(n, 2.55), "bp") * env
    layer_h = svf_filter(colored_noise(rng, n, 1.35) * turb, f2, np.full(n, 1.65), "bp") * (env ** 1.15)
    layer_low = svf_const(svf_const(colored_noise(rng, n, 1.90), low_lp, 0.7, "lp"), low_hp, 0.7, "hp") * (env ** 0.90)

    mix = (
        0.48 * (layer_u / (np.std(layer_u) + 1e-12))
        + 0.28 * (layer_h / (np.std(layer_h) + 1e-12))
        + 0.36 * (layer_low / (np.std(layer_low) + 1e-12))
    )
    mix = fft_eq(mix, lambda f: highpass_smooth(f, 48.0, 3.0) * lowpass_smooth(f, final_lp, 2.6))
    mix = soft_air_space(mix, lp_hz=final_lp * 0.9, wet=0.16)

    fi = int(0.010 * SR)
    fo = int(0.030 * SR)
    mix[:fi] *= np.linspace(0.0, 1.0, fi) ** 1.4
    mix[-fo:] *= np.linspace(1.0, 0.0, fo) ** 1.7

    target_rms = 10.0 ** (target_rms_db / 20.0)
    max_peak = 10.0 ** (max_peak_db / 20.0)
    mix *= target_rms / (np.sqrt(np.mean(mix * mix)) + 1e-12)
    pk = np.max(np.abs(mix))
    if pk > max_peak:
        knee = max_peak * 0.80
        mag = np.abs(mix)
        over = mag > knee
        hr = max_peak - knee
        mix[over] = np.sign(mix[over]) * (knee + hr * np.tanh((mag[over] - knee) / hr))
    mix[: int(0.004 * SR)] *= np.linspace(0.0, 1.0, int(0.004 * SR))
    mix[-int(0.016 * SR) :] *= np.linspace(1.0, 0.0, int(0.016 * SR))
    return mix


def write_wav(path: Path, samples: np.ndarray) -> bytes:
    pcm = np.clip(np.round(samples * 32767.0), -32768, 32767).astype(np.int16)
    pcm_bytes = pcm.tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm_bytes)
    return pcm_bytes


def repack_fsb5(fsb_path: Path, pcm_bytes: bytes, nframes: int) -> bytes:
    """Repack single-sample 48 kHz mono PCM16 FSB5 bank preserving compat_hash, guid, and name table."""
    old = fsb_path.read_bytes()
    magic, ver, num_samples, shdr_size, name_size, _old_data_size, mode = struct.unpack_from("<4sIIIIII", old, 0)
    assert magic == b"FSB5" and ver == 1 and num_samples == 1, f"Unexpected FSB5 header: {magic!r} v{ver} n={num_samples}"
    assert shdr_size == 8 and mode == FSB5_MODE_PCM16, f"Unexpected FSB5 layout: shdr={shdr_size} mode={mode}"

    # Preserve zero/compat_hash/guid bytes [28:60] and name table [68:68+name_size]
    hdr_tail = old[28:60]
    name_table = old[60 + shdr_size : 60 + shdr_size + name_size]

    # FMOD Designer pads PCM16 bank data to 32-byte alignment with trailing zero guard bytes:
    # e.g. 14208 -> 14240 (+32), 171394 -> 171424 (+30).
    data_size = ((len(pcm_bytes) + 32) // 32) * 32
    pad_len = data_size - len(pcm_bytes)
    assert pad_len >= 1 and data_size % 32 == 0

    new_hdr = struct.pack("<4sIIIIII", b"FSB5", 1, 1, shdr_size, name_size, data_size, FSB5_MODE_PCM16) + hdr_tail
    sample0_val = (nframes << 34) | (0 << 6) | (0 << 5) | (FSB5_FREQ_48000 << 1) | 0
    new_shdr = struct.pack("<Q", sample0_val)

    repacked = new_hdr + new_shdr + name_table + pcm_bytes + (b"\x00" * pad_len)
    fsb_path.write_bytes(repacked)
    return repacked


def update_fev_length_ms(fev_path: Path, length_ms: int, expected_bank_hash: bytes) -> None:
    """Update waveform lengthms in wili_blink.fev without changing chunk sizes or bank hash."""
    fev = bytearray(fev_path.read_bytes())
    assert fev[:4] == b"RIFF" and fev[8:12] == b"FEV ", "Invalid FEV header"
    assert bytes(fev[FEV_BANK_HASH_OFFSET : FEV_BANK_HASH_OFFSET + 8]) == expected_bank_hash, "FEV bank hash mismatch"
    # Verify exact anchor before lengthms: "blink.wav\0" + bank_idx(0) + sample_idx(0)
    anchor_start = FEV_LENGTH_MS_OFFSET - len(FEV_WAVEFORM_NAME) - 8
    assert bytes(fev[anchor_start : anchor_start + len(FEV_WAVEFORM_NAME)]) == FEV_WAVEFORM_NAME, "FEV waveform anchor mismatch"
    assert bytes(fev[FEV_LENGTH_MS_OFFSET - 8 : FEV_LENGTH_MS_OFFSET]) == b"\x00" * 8, "FEV bank/sample index mismatch"

    struct.pack_into("<I", fev, FEV_LENGTH_MS_OFFSET, length_ms)
    fev_path.write_bytes(bytes(fev))


def verify_outputs() -> None:
    with wave.open(str(WAV_PATH), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == SR
        nframes = w.getnframes()
        wav_pcm = w.readframes(nframes)

    fsb = FSB_PATH.read_bytes()
    magic, ver, num_samples, shdr_size, name_size, data_size, mode = struct.unpack_from("<4sIIIIII", fsb, 0)
    assert (magic, ver, num_samples, shdr_size, mode) == (b"FSB5", 1, 1, 8, FSB5_MODE_PCM16)
    assert len(fsb) == 60 + shdr_size + name_size + data_size
    assert data_size % 32 == 0

    shdr_val = struct.unpack_from("<Q", fsb, 60)[0]
    has_next = shdr_val & 1
    freq_code = (shdr_val >> 1) & 0xF
    ch_code = (shdr_val >> 5) & 1
    data_off = ((shdr_val >> 6) & 0xFFFFFFF) * 16
    samples_cnt = (shdr_val >> 34) & 0x3FFFFFFF
    assert (has_next, freq_code, ch_code, data_off, samples_cnt) == (0, FSB5_FREQ_48000, 0, 0, nframes)

    data_start = 60 + shdr_size + name_size
    fsb_pcm = fsb[data_start : data_start + len(wav_pcm)]
    fsb_pad = fsb[data_start + len(wav_pcm) :]
    assert fsb_pcm == wav_pcm, "FSB5 PCM payload does not match blink.wav"
    assert all(b == 0 for b in fsb_pad), "FSB5 tail padding contains non-zero bytes"

    fev = FEV_PATH.read_bytes()
    assert len(fev) == 976
    assert struct.unpack_from("<I", fev, 4)[0] == len(fev) - 8
    assert fev[FEV_BANK_HASH_OFFSET : FEV_BANK_HASH_OFFSET + 8] == fsb[36:44], "FEV/FSB5 bank hash mismatch"
    fev_len_ms = struct.unpack_from("<I", fev, FEV_LENGTH_MS_OFFSET)[0]
    expected_ms = int(round(nframes * 1000.0 / SR))
    assert fev_len_ms == expected_ms, f"FEV lengthms={fev_len_ms}, expected {expected_ms}"

    arr = np.frombuffer(wav_pcm, dtype=np.int16).astype(np.float64) / 32768.0
    pk_db = 20 * math.log10(np.max(np.abs(arr)) + 1e-12)
    rms_db = 20 * math.log10(np.sqrt(np.mean(arr * arr)) + 1e-12)
    print(
        f"VERIFIED OK: {WAV_PATH.name} ({nframes} frames, {nframes/SR:.3f}s, "
        f"peak={pk_db:.1f} dBFS, rms={rms_db:.1f} dBFS) | "
        f"FSB5={len(fsb)}B (data={data_size}B, pad={len(fsb_pad)}B) | "
        f"FEV={len(fev)}B (lengthms={fev_len_ms}ms, hash={fsb[36:44].hex()})"
    )


def main() -> int:
    if "--verify-only" in sys.argv:
        verify_outputs()
        return 0

    samples = synthesize_blink_deep_hu_3b()
    pcm_bytes = write_wav(WAV_PATH, samples)
    nframes = len(samples)
    fsb_bytes = repack_fsb5(FSB_PATH, pcm_bytes, nframes)
    update_fev_length_ms(FEV_PATH, int(round(nframes * 1000.0 / SR)), fsb_bytes[36:44])
    verify_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
