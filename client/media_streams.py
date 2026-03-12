import sounddevice as sd
import asyncio
import base64
import json
import mss
import cv2
import numpy as np

CHANNELS = 1
RATE = 16000
CHUNK = 512

class MediaStreamer:
    def __init__(self, websocket):
        self.ws = websocket
        self.stream_in = sd.RawInputStream(samplerate=RATE, channels=CHANNELS, dtype='int16', blocksize=CHUNK)
        self.stream_out = sd.RawOutputStream(samplerate=24000, channels=CHANNELS, dtype='int16')
        self.stream_in.start()
        self.stream_out.start()
        self.sct = mss.mss()
        print("\n\n🎙️ Listening for commands...\n")

    async def stream_audio_in(self):
        """Continuously captures mic input and sends it over WebSocket."""
        try:
            while True:
                # Read chunks of raw PCM audio data
                data, overflowed = self.stream_in.read(CHUNK)
                b64_data = base64.b64encode(data).decode('utf-8')
                await self.ws.send(json.dumps({
                    "type": "audio",
                    "data": b64_data
                }))
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"Mic error: {e}")

    async def stream_screen_context(self):
        """Captures the primary display at 1 FPS and sends as JPEG."""
        try:
            # monitors[1] is the primary monitor, monitors[0] is all monitors combined
            monitor = self.sct.monitors[1]
            while True:
                sct_img = self.sct.grab(monitor)
                img = np.array(sct_img)
                
                # Convert BGRA (mss default) to BGR for OpenCV
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Resize if necessary to save bandwidth (e.g. 720p)
                img = cv2.resize(img, (1280, 720))
                
                # Compress as JPEG
                _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                b64_img = base64.b64encode(buffer).decode('utf-8')
                
                await self.ws.send(json.dumps({
                    "type": "image",
                    "data": b64_img
                }))
                # Maintain ~1 FPS as per AGENTS.md requirements
                await asyncio.sleep(1.0)
        except Exception as e:
            print(f"Screen capture error: {e}")

    def play_audio(self, pcm_data: bytes):
        """Plays PCM audio received from the server."""
        self.stream_out.write(pcm_data)

    def close(self):
        self.stream_in.stop()
        self.stream_in.close()
        self.stream_out.stop()
        self.stream_out.close()
