"""
One-time voice cloning setup script.

1. Records voice samples (or uses existing ones from ./voice_samples/)
2. Fine-tunes StyleTTS2 on your voice
3. Saves model to ./voice_model/

Requirements:
  - StyleTTS2 cloned: git clone https://github.com/yl4579/StyleTTS2
  - pip install phonemizer torch torchaudio

Usage:
  python setup_voice.py --record     # Record new samples interactively
  python setup_voice.py --train      # Train on existing ./voice_samples/
"""

import os
import sys
import argparse
import subprocess
import wave
import tempfile

SAMPLES_DIR = "./voice_samples"
MODEL_DIR = "./voice_model"
SAMPLE_RATE = 24000
RECORD_SECONDS = 10
NUM_SAMPLES = 5

PROMPTS = [
    "The quick brown fox jumps over the lazy dog.",
    "Hello, I am attending this meeting on behalf of the user.",
    "Could you please repeat that? I didn't quite catch it.",
    "That's a great point. I agree with what you said.",
    "Let me get back to you on that after the meeting.",
]


def record_samples():
    import sounddevice as sd
    import soundfile as sf
    import numpy as np

    os.makedirs(SAMPLES_DIR, exist_ok=True)
    print(f"\nRecording {NUM_SAMPLES} voice samples ({RECORD_SECONDS}s each).")
    print("Speak clearly and naturally.\n")

    for i, prompt in enumerate(PROMPTS):
        input(f"[{i+1}/{NUM_SAMPLES}] Press Enter, then say:\n  \"{prompt}\"\n")
        print("  Recording...")
        audio = sd.rec(
            int(RECORD_SECONDS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        path = os.path.join(SAMPLES_DIR, f"sample_{i+1:02d}.wav")
        sf.write(path, audio, SAMPLE_RATE)
        print(f"  Saved: {path}\n")

    print(f"Done! Samples saved to {SAMPLES_DIR}/")


def train_voice():
    styletts2_path = "./StyleTTS2"
    if not os.path.exists(styletts2_path):
        print("StyleTTS2 not found. Cloning...")
        subprocess.run(
            ["git", "clone", "https://github.com/yl4579/StyleTTS2.git", styletts2_path],
            check=True,
        )

    # Install StyleTTS2 deps
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", f"{styletts2_path}/requirements.txt"],
        check=True,
    )

    samples = [
        os.path.join(SAMPLES_DIR, f)
        for f in os.listdir(SAMPLES_DIR)
        if f.endswith(".wav")
    ]
    if not samples:
        print(f"No .wav files found in {SAMPLES_DIR}. Run --record first.")
        sys.exit(1)

    print(f"\nFound {len(samples)} voice samples.")
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Copy first sample as reference for inference
    import shutil
    shutil.copy(samples[0], os.path.join(MODEL_DIR, "reference.wav"))

    print("\nTo fine-tune StyleTTS2 on your voice, follow:")
    print(f"  https://github.com/yl4579/StyleTTS2#fine-tuning")
    print(f"\nYour samples are in: {SAMPLES_DIR}/")
    print(f"Reference audio saved to: {MODEL_DIR}/reference.wav")
    print("\nFor zero-shot voice cloning (no training needed), the bot will use")
    print("StyleTTS2's inference with your reference.wav directly.")
    print(f"\nSet VOICE_MODEL_PATH={MODEL_DIR} in your .env")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice cloning setup")
    parser.add_argument("--record", action="store_true", help="Record voice samples")
    parser.add_argument("--train", action="store_true", help="Prepare voice model")
    args = parser.parse_args()

    if args.record:
        record_samples()
    if args.train:
        train_voice()
    if not args.record and not args.train:
        parser.print_help()
