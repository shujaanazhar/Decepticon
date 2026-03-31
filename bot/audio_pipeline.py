"""
Virtual audio pipeline using PipeWire/PulseAudio.

Architecture:
  - meet_capture (null sink): Chrome routes Meet audio here automatically (set as default sink before Chrome launches)
  - decepticon_tts_sink (null sink): Bot TTS plays here
  - decepticon_virtual_mic (remap-source): Exposes TTS monitor as a real mic Chrome accepts
  - No loopbacks = no beeping
"""

import subprocess
import os

CAPTURE_SINK = "meet_capture"
TTS_SINK = "decepticon_tts_sink"
VIRTUAL_MIC = "decepticon_virtual_mic"

_loaded_modules = []
_real_default_sink = None
_real_default_source = None


def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode


def _cleanup_stale():
    out, _ = run("pactl list modules short")
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        mod_id = parts[0]
        rest = " ".join(parts[1:])
        if any(name in rest for name in [CAPTURE_SINK, TTS_SINK, VIRTUAL_MIC]):
            run(f"pactl unload-module {mod_id}")


def setup_virtual_audio():
    global _real_default_sink, _real_default_source
    _cleanup_stale()

    # Save real defaults to restore on teardown
    _real_default_sink, _ = run("pactl get-default-sink")
    _real_default_source, _ = run("pactl get-default-source")
    _real_default_sink = _real_default_sink.strip()
    _real_default_source = _real_default_source.strip()

    # Sink 1: Meet audio capture — Chrome will route here (it's the default sink)
    out, rc = run(
        f"pactl load-module module-null-sink "
        f"sink_name={CAPTURE_SINK} "
        f"sink_properties=device.description=MeetCapture"
    )
    if rc == 0:
        _loaded_modules.append(out.strip())
        print(f"[audio] Capture sink loaded: module #{out.strip()}")

    # Sink 2: TTS output — bot plays synthesized speech here
    out2, rc2 = run(
        f"pactl load-module module-null-sink "
        f"sink_name={TTS_SINK} "
        f"sink_properties=device.description=DecepticonTTS"
    )
    if rc2 == 0:
        _loaded_modules.append(out2.strip())
        print(f"[audio] TTS sink loaded: module #{out2.strip()}")

    # Virtual mic: remap TTS monitor as a real Audio/Source Chrome accepts
    out3, rc3 = run(
        f"pactl load-module module-remap-source "
        f"master={TTS_SINK}.monitor "
        f"source_name={VIRTUAL_MIC} "
        f"source_properties=device.description=DecepticonMic"
    )
    if rc3 == 0:
        _loaded_modules.append(out3.strip())
        print(f"[audio] Virtual mic loaded: module #{out3.strip()}")
    else:
        print(f"[audio] WARNING: module-remap-source failed, falling back to set-default-source")
        run(f"pactl set-default-source {TTS_SINK}.monitor")

    # Max TTS sink volume — loudnorm in play_audio_file normalizes per-file, this is a safety boost
    run(f"pactl set-sink-volume {TTS_SINK} 200%")

    # Set defaults BEFORE Chrome launches so it picks them up automatically
    run(f"pactl set-default-sink {CAPTURE_SINK}")
    run(f"pactl set-default-source {VIRTUAL_MIC}")
    print(f"[audio] Default sink → {CAPTURE_SINK}, default source → {VIRTUAL_MIC}")


def teardown_virtual_audio():
    # Restore real defaults
    if _real_default_sink:
        run(f"pactl set-default-sink {_real_default_sink}")
    if _real_default_source:
        run(f"pactl set-default-source {_real_default_source}")

    for mod_id in reversed(_loaded_modules):
        run(f"pactl unload-module {mod_id}")
    _loaded_modules.clear()
    print("[audio] Virtual audio torn down.")


def move_chrome_audio_to_capture_sink():
    """No-op — Chrome already routes to meet_capture since it's the default sink."""
    print("[audio] Chrome using meet_capture sink (set as default before launch)")


def play_audio_file(path: str):
    """Boost volume and play to TTS sink."""
    # Amplify by 8x so WebRTC doesn't treat the signal as silence/background noise
    cmd = (
        f"ffmpeg -y -i {path} "
        f"-af volume=8.0 "
        f"-ar 48000 -ac 1 -f wav pipe:1 2>/dev/null "
        f"| paplay --device={TTS_SINK} --raw --rate=48000 --channels=1 --format=s16le"
    )
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        # Fallback: play directly without processing
        subprocess.run(["paplay", "--device", TTS_SINK, path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def record_from_meet(output_path: str, duration_sec: float = 30.0):
    """Record meeting audio from meet_capture.monitor using parec + ffmpeg."""
    cmd = (
        f"parec --device={CAPTURE_SINK}.monitor "
        f"--rate=16000 --channels=1 --format=s16le --latency-msec=50 "
        f"| ffmpeg -y -f s16le -ar 16000 -ac 1 -i pipe:0 "
        f"-t {duration_sec:.1f} {output_path} 2>/dev/null"
    )
    subprocess.run(cmd, shell=True)
    return output_path
