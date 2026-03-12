"""
Push-to-talk audio recorder.
Press SPACE to start recording, press SPACE again to stop and save as .wav.
"""

import sounddevice as sd
import numpy as np
import wave
import keyboard
import os
import time
from datetime import datetime

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")


def record_clip():
    """Records audio between two SPACE key presses and saves as .wav."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\n🎙️  Press SPACE to start recording...")
    keyboard.wait("space")

    print("🔴 Recording... Press SPACE to stop.")
    frames = []

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=1024,
        callback=callback,
    )

    stream.start()
    keyboard.wait("space")
    stream.stop()
    stream.close()

    if not frames:
        print("⚠️  No audio captured.")
        return None

    audio_data = np.concatenate(frames, axis=0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(OUTPUT_DIR, f"command_{timestamp}.wav")

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data.tobytes())

    duration = len(audio_data) / SAMPLE_RATE
    print(f"✅ Saved: {filename}  ({duration:.1f}s)")
    return filename


if __name__ == "__main__":
    print("=== Push-to-Talk Recorder ===")
    print("Press Ctrl+C to quit.\n")
    try:
        while True:
            record_clip()
    except KeyboardInterrupt:
        print("\nDone.")
