"""Add a sound-design track to the launch video made by make_launch_video.py.

Everything is synthesised here with numpy (no samples, nothing to license), and every cue is
placed on the video's own timeline: a key click per typed character, a heavier Enter, whooshes
on scene changes, glass tones as the mark's rings draw and a chime when its dot appears, ticks
when the report highlight moves and as the Piotroski count steps, pops for the DCF pins, a low
hit on the end card, and a quiet ambient pad underneath with a short reverb.

    python examples/make_launch_audio.py VIDEO.mp4 [--out OUT.mp4]

The video stream is copied untouched; only an AAC audio track is added. Without --out the
input file is replaced. Needs numpy and ffmpeg. Keep the cue times in sync with the scene
timings in make_launch_video.py if those change.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 48_000
DUR = 46.0
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- building blocks
def t_axis(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def band(x: np.ndarray, lo: float, hi: float, soft: float = 0.25) -> np.ndarray:
    """Band-pass by FFT with raised-cosine edges (soft is the edge width in octaves)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR) + 1e-9
    oct_lo, oct_hi = np.log2(f / lo), np.log2(f / hi)
    g = np.clip(0.5 + oct_lo / soft, 0, 1) * np.clip(0.5 - oct_hi / soft, 0, 1)
    g = 0.5 - 0.5 * np.cos(np.pi * g)
    return np.fft.irfft(spec * g, len(x))


def noise(seconds: float) -> np.ndarray:
    return rng.standard_normal(int(seconds * SR))


def decay(seconds: float, tau: float, attack: float = 0.001) -> np.ndarray:
    t = t_axis(seconds)
    return np.minimum(1, t / attack) * np.exp(-t / tau)


def norm(x: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(x))
    return x / peak if peak else x


def key_click(vol: float = 1.0) -> np.ndarray:
    n = 0.045
    click = band(noise(n), 1800 * rng.uniform(0.85, 1.15), 7500) * decay(n, 0.005)
    body = np.sin(2 * np.pi * rng.uniform(150, 230) * t_axis(n)) * decay(n, 0.011)
    return norm(0.75 * norm(click) + 0.45 * body) * vol * rng.uniform(0.8, 1.05)


def enter_key() -> np.ndarray:
    n = 0.16
    x = norm(band(noise(n), 700, 4000) * decay(n, 0.012)) * 0.8
    x += np.sin(2 * np.pi * 105 * t_axis(n)) * decay(n, 0.045) * 0.9
    rel = np.zeros_like(x)
    r = norm(band(noise(0.03), 2000, 7000) * decay(0.03, 0.004)) * 0.35
    rel[int(0.075 * SR):int(0.075 * SR) + len(r)] = r
    return norm(x + rel)


def whoosh(seconds: float = 0.9, peak_at: float = 0.62) -> np.ndarray:
    n = noise(seconds)
    t = t_axis(seconds) / seconds
    env = np.where(t < peak_at, np.sin(np.pi / 2 * t / peak_at) ** 2,
                   np.cos(np.pi / 2 * np.clip((t - peak_at) / (1 - peak_at), 0, 1)) ** 1.6)
    low, high = norm(band(n, 180, 1400)), norm(band(n, 1400, 9000))
    mix = np.clip(t / peak_at, 0, 1)  # brightens towards the peak, like air rushing past
    return norm((low * (1 - 0.6 * mix) + high * 0.55 * mix) * env)


def chime(freq: float, seconds: float = 1.6, bright: float = 1.0) -> np.ndarray:
    t = t_axis(seconds)
    x = np.zeros_like(t)
    for mult, amp, tau in ((1, 1, 0.9), (2.0, 0.32 * bright, 0.45), (3.01, 0.14 * bright, 0.3), (4.2, 0.06 * bright, 0.2)):
        x += amp * np.sin(2 * np.pi * freq * mult * t) * np.exp(-t / tau)
    return norm(x * np.minimum(1, t / 0.003))


def glass(freq: float) -> np.ndarray:
    t = t_axis(0.9)
    x = np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(2 * np.pi * freq * 2.01 * t)
    return norm(x * np.minimum(1, t / 0.02) * np.exp(-t / 0.35))


def tick(freq: float = 2400, seconds: float = 0.03) -> np.ndarray:
    t = t_axis(seconds)
    x = np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.005) + 0.25 * band(noise(seconds), 3000, 9000) * np.exp(-t / 0.002)
    return norm(x)


def pop(f0: float = 900, f1: float = 360, seconds: float = 0.09) -> np.ndarray:
    t = t_axis(seconds)
    f = f1 + (f0 - f1) * np.exp(-t / 0.012)
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * decay(seconds, 0.03, 0.002))


def blip(freq: float) -> np.ndarray:
    t = t_axis(0.075)
    x = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 3 * t)
    return norm(x * np.minimum(1, t / 0.003) * np.exp(-t / 0.028))


def thump() -> np.ndarray:
    t = t_axis(0.22)
    f = 55 + 70 * np.exp(-t / 0.03)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.07)
    return norm(x + 0.15 * band(noise(0.22), 200, 1500) * np.exp(-t / 0.02))


def boom() -> np.ndarray:
    t = t_axis(2.2)
    f = 40 + 55 * np.exp(-t / 0.08)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.55)
    x += 0.25 * band(noise(2.2), 60, 600) * np.exp(-t / 0.18)
    return norm(x * np.minimum(1, t / 0.004))


def riser(seconds: float) -> np.ndarray:
    t = t_axis(seconds) / seconds
    n = norm(band(noise(seconds), 600, 6000)) * t ** 2.2
    glide = np.sin(2 * np.pi * np.cumsum(220 * 2 ** (1.6 * t)) / SR) * t ** 3 * 0.25
    return norm(n * 0.8 + glide) * (1 - np.clip((t - 0.97) / 0.03, 0, 1))


def pad(seconds: float) -> np.ndarray:
    """A soft A-major-9 bed: detuned sine pairs with a slow swell."""
    t = t_axis(seconds)
    out = np.zeros((2, len(t)))
    for i, f in enumerate((110.0, 164.81, 246.94, 277.18, 415.30)):
        lfo = 1 + 0.12 * np.sin(2 * np.pi * (0.05 + 0.013 * i) * t + i)
        for ch, det in ((0, -0.18), (1, 0.21)):
            out[ch] += np.sin(2 * np.pi * (f + det) * t + i) * lfo / (1 + 0.35 * i)
    return out / np.max(np.abs(out))


# ---------------------------------------------------------------- mixing helpers
def place(bus: np.ndarray, sig: np.ndarray, at: float, gain: float, pan: float = 0.0) -> None:
    i = int(at * SR)
    if i >= bus.shape[1]:
        return
    sig = sig[: bus.shape[1] - i]
    ang = (pan + 1) * np.pi / 4
    bus[0, i:i + len(sig)] += sig * gain * np.cos(ang)
    bus[1, i:i + len(sig)] += sig * gain * np.sin(ang)


def eio(k: float) -> float:
    return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def reverb_ir(seconds: float = 1.5) -> np.ndarray:
    t = t_axis(seconds)
    ir = np.stack([band(noise(seconds), 200, 7000), band(noise(seconds), 200, 7000)]) * np.exp(-t / 0.32)
    return ir / np.sqrt(np.sum(ir ** 2, axis=1, keepdims=True))


def convolve(bus: np.ndarray, ir: np.ndarray) -> np.ndarray:
    n = bus.shape[1] + ir.shape[1]
    size = 1 << (n - 1).bit_length()
    out = np.fft.irfft(np.fft.rfft(bus, size) * np.fft.rfft(ir, size), size)[:, : bus.shape[1]]
    return out


# ---------------------------------------------------------------- the score
def build() -> np.ndarray:
    n = int(DUR * SR)
    dry = np.zeros((2, n))   # clicks and ticks: close and dry
    fx = np.zeros((2, n))    # everything else: sent to the reverb

    # scene 1: terrain draws in, the mark's rings and dot, title lands
    place(fx, riser(1.1), 0.0, 0.18)
    for i, f in enumerate((659.25, 830.61, 987.77)):
        place(fx, glass(f), 0.35 + i * 0.22, 0.16, pan=-0.3 + 0.3 * i)
    place(fx, chime(1318.5), 1.12, 0.26)
    place(fx, pop(1100, 520), 1.12, 0.12)
    place(fx, whoosh(0.9), 1.75, 0.20, pan=-0.4)
    for i in range(3):
        place(fx, thump(), 2.58 + i * 0.14, 0.20)
        place(fx, whoosh(0.32, 0.4), 2.47 + i * 0.14, 0.07, pan=-0.2 + 0.2 * i)
    place(dry, tick(2600), 2.92, 0.07)
    place(dry, tick(2100), 3.52, 0.05)

    # scene changes: a whoosh that peaks on the cut
    for cut in (6.2, 14.6, 22.6, 28.8, 34.0, 40.9):
        place(fx, whoosh(0.95), cut - 0.62, 0.30, pan=0.0)

    # scene 2: the terminal
    for k in range(1, 20):
        place(dry, key_click(), 6.9 + (k - 0.5) / 19 * 1.0, 0.24, pan=rng.uniform(-0.15, 0.15))
    place(dry, enter_key(), 8.12, 0.42)
    place(dry, tick(1900), 8.6, 0.06)
    for k in range(1, 18):
        place(dry, key_click(), 8.9 + (k - 0.5) / 17 * 0.9, 0.24, pan=rng.uniform(-0.15, 0.15))
    place(dry, enter_key(), 10.02, 0.42)
    for i in range(0, 61, 2):  # output streaming in
        place(dry, tick(rng.uniform(2800, 3800), 0.02), 10.1 + (i + 1) / 61 * 2.9, 0.035, pan=rng.uniform(-0.4, 0.4))
    place(fx, chime(739.99, 1.0, 0.5), 13.15, 0.16)
    place(fx, blip(660), 13.15, 0.05)

    # scene 3: the report and its callouts
    place(dry, tick(2300), 15.5, 0.08)
    place(fx, pop(800, 420), 15.6, 0.07)
    for at in (16.85, 18.75, 20.6):
        place(dry, tick(2300), at, 0.08)
        place(fx, whoosh(0.85, 0.45), at, 0.07, pan=0.35)

    # scene 4: scores
    for i in range(3):
        place(fx, thump(), 22.95 + i * 0.45, 0.16, pan=-0.45 + 0.45 * i)
    last = 0
    for f in range(int(1.4 * SR / 480)):  # Piotroski counter, one tick per step
        t = 23.1 + f * 480 / SR
        v = round(9 * eio(min(1, (t - 23.1) / 1.4)))
        if v != last:
            place(dry, tick(1800 + 90 * v), t, 0.07, pan=-0.45)
            last = v
    place(fx, chime(1108.73, 1.4), 24.5, 0.18, pan=-0.45)
    t_alt = t_axis(1.4)  # Altman counting up: a faint rising tone under the digits
    k = t_alt / 1.4
    eased = np.where(k < 0.5, 4 * k ** 3, 1 - (-2 * k + 2) ** 3 / 2)
    sweep = np.sin(2 * np.pi * np.cumsum(500 + 700 * eased) / SR)
    place(fx, sweep * np.minimum(1, t_alt / 0.1) * (1 - k) ** 0.5, 23.55, 0.025)
    place(fx, chime(1318.5, 1.4), 24.95, 0.18)
    for i, f in enumerate((520, 440, 370)):
        place(dry, blip(f), 24.2 + i * 0.135, 0.10, pan=0.45)
    place(fx, whoosh(1.1, 0.5), 25.4, 0.06, pan=-0.5)
    for i, (at, f0) in enumerate(((25.7, 700), (26.05, 980), (26.4, 820))):
        place(fx, pop(f0, f0 * 0.45), at, 0.12, pan=-0.5 + 0.5 * i)
    place(fx, chime(987.77, 1.2, 0.6), 26.05, 0.12)

    # scene 5: feature cards typing themselves in
    place(fx, thump(), 28.92, 0.14)
    cmds = ("isoline statements ACME", "isoline compare AAPL MSFT", "isoline screen IT",
            "isoline value ACME", "isoline scan ACME --export a.xlsx", "isoline serve")
    for i, cmd in enumerate(cmds):
        st = 29.25 + 0.2 * i
        pan = -0.5 + 0.5 * (i % 3)
        place(fx, pop(760, 380), st + 0.05, 0.06, pan=pan)
        for k in range(1, len(cmd) + 1, 2):
            place(dry, key_click(0.7), st + 0.2 + (k - 0.5) * 0.022, 0.07, pan=pan)

    # scene 6: the website scrolling
    for a, b in ((34.93, 35.87), (36.33, 38.13), (38.6, 39.4)):
        place(fx, whoosh(b - a + 0.2, 0.45), a, 0.07, pan=0.2)
    place(fx, chime(830.61, 1.2, 0.5), 39.6, 0.09)

    # scene 7: end card
    place(fx, boom(), 40.9, 0.42)
    for i, f in enumerate((659.25, 830.61, 987.77)):
        place(fx, glass(f), 41.05 + i * 0.22, 0.15, pan=-0.3 + 0.3 * i)
    place(fx, chime(1318.5, 2.2), 41.82, 0.24)
    place(fx, chime(1975.5, 2.0, 0.4), 41.84, 0.08)
    place(fx, whoosh(0.5, 0.5), 41.45, 0.08, pan=0.3)
    place(fx, pop(900, 420), 42.22, 0.10)
    place(dry, key_click(), 42.24, 0.10)
    place(dry, tick(2200), 42.82, 0.05)

    wet = convolve(fx, reverb_ir())
    mix = dry + fx * 0.85 + wet * 0.22 + convolve(dry, reverb_ir(0.6)) * 0.05

    bed = pad(DUR)
    t = t_axis(DUR)
    bed_env = np.clip(t / 2.5, 0, 1) * np.clip((DUR - t) / 1.2, 0, 1) * (1 + 0.6 * np.clip((t - 40.9) / 1.5, 0, 1) * np.clip((45.0 - t) / 1.0, 0, 1))
    mix += bed * bed_env * 0.045

    # gentle high-pass, soft limit, fade to silence with the picture, -1 dBFS peak
    mix = np.stack([band(ch, 30, 18000, soft=0.5) for ch in mix])
    mix = np.tanh(mix * 1.6) / 1.6
    mix *= np.clip((DUR - t) / 0.8, 0, 1)
    return mix / np.max(np.abs(mix)) * 10 ** (-1 / 20)


def write_wav(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x.T, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="Default: replace the input file.")
    ap.add_argument("--wav", type=Path, default=None, help="Also keep the audio as a WAV here.")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required")
    audio = build()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "score.wav"
        write_wav(wav, audio)
        if a.wav:
            shutil.copy(wav, a.wav)
        out = a.out or a.video
        staged = Path(tmp) / "with-audio.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a.video), "-i", str(wav),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000",
                        "-shortest", "-movflags", "+faststart", str(staged)], check=True)
        shutil.move(str(staged), out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
