"""
Automated test client that sends pre-recorded .wav files to the backend
one at a time, waiting for Gemini to finish responding (turn_complete)
before sending the next file. Also handles tool calls against SolidWorks.
"""

import asyncio
import json
import base64
import wave
import glob
import os
import sys
import traceback
import websockets

# Add parent client directory to path so we can import solidworks_tools
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'client'))
from solidworks_tools import execute_tool

# Set to your Cloud Run URL or keep as localhost for Docker/local testing
LOCAL_URI     = "ws://localhost:8080/ws"
SERVER_URI = LOCAL_URI  # Switch to CLOUD_RUN_URI to test the live cloud backend
RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
CHUNK_SIZE = 512  # Samples per chunk (matches MediaStreamer)
SAMPLE_RATE = 16000

# Try to set up audio playback, but don't crash if it fails
try:
    import sounddevice as sd
    AUDIO_OUT = sd.RawOutputStream(samplerate=24000, channels=1, dtype='int16')
    AUDIO_OUT.start()
    print("🔊 Audio playback enabled")
except Exception as e:
    AUDIO_OUT = None
    print(f"🔇 Audio playback disabled: {e}")


def load_wav(filepath: str) -> bytes:
    """Load a .wav file and return raw PCM bytes (16-bit mono 16kHz)."""
    with wave.open(filepath, "rb") as wf:
        if wf.getnchannels() != 1:
            print(f"   ⚠️  Expected mono, got {wf.getnchannels()} channels")
        if wf.getsampwidth() != 2:
            print(f"   ⚠️  Expected 16-bit, got {wf.getsampwidth() * 8}-bit")
        if wf.getframerate() != SAMPLE_RATE:
            print(f"   ⚠️  Expected {SAMPLE_RATE}Hz, got {wf.getframerate()}Hz")
        return wf.readframes(wf.getnframes())


async def send_audio_file(ws, filepath: str):
    """Send a .wav file as chunked PCM data, simulating real-time mic input."""
    pcm_data = load_wav(filepath)
    total_samples = len(pcm_data) // 2  # 16-bit = 2 bytes per sample
    chunk_bytes = CHUNK_SIZE * 2  # bytes per chunk
    
    num_chunks = (len(pcm_data) + chunk_bytes - 1) // chunk_bytes
    duration = total_samples / SAMPLE_RATE
    
    filename = os.path.basename(filepath)
    print(f"\n📤 Sending: {filename} ({duration:.1f}s, {num_chunks} chunks)")
    
    for i in range(0, len(pcm_data), chunk_bytes):
        chunk = pcm_data[i:i + chunk_bytes]
        b64_data = base64.b64encode(chunk).decode('utf-8')
        await ws.send(json.dumps({
            "type": "audio",
            "data": b64_data
        }))
        # Simulate real-time streaming pace
        await asyncio.sleep(CHUNK_SIZE / SAMPLE_RATE)
    
    print(f"   ✅ Finished sending {filename}")


async def run_test():
    """Main test loop: connect, send each .wav, wait for responses."""
    
    # Discover .wav files sorted by name
    wav_files = sorted(glob.glob(os.path.join(RECORDINGS_DIR, "*.wav")))
    if not wav_files:
        print(f"❌ No .wav files found in {RECORDINGS_DIR}")
        return
    
    print(f"\nFound {len(wav_files)} audio files:")
    for f in wav_files:
        print(f"  • {os.path.basename(f)}")
    
    print(f"\nConnecting to {SERVER_URI}...")
    
    async with websockets.connect(
        SERVER_URI, 
        ping_interval=None, 
        ping_timeout=None,
        close_timeout=10
    ) as ws:
        print("Connected to backend!\n")
        
        # Event that signals when Gemini has finished its turn
        turn_done = asyncio.Event()
        test_complete = asyncio.Event()
        
        async def receive_loop():
            """Handles all incoming messages from the server."""
            try:
                while not test_complete.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    
                    if msg_type == "audio" and "data" in data:
                        if AUDIO_OUT is not None:
                            try:
                                pcm = base64.b64decode(data["data"])
                                AUDIO_OUT.write(pcm)
                            except Exception:
                                pass
                    
                    elif msg_type == "text":
                        print(f"   💬 [Agent]: {data['text']}")
                    
                    elif msg_type == "turn_complete":
                        print("   ✅ [Turn complete]")
                        turn_done.set()
                    
                    elif msg_type == "status":
                        status_msg = data.get('message', '')
                        print(f"   ℹ️  [Server]: {status_msg}")
                        if "Reconnecting" in status_msg:
                            # After reconnect, treat as turn done so we can send next file
                            turn_done.set()
                    
                    elif msg_type == "tool_call":
                        tool_id = data.get("id")
                        name = data.get("name")
                        args = data.get("args", {})
                        print(f"   🔧 [Tool call] {name}({args})")
                        
                        try:
                            result = await execute_tool(name, args)
                            print(f"   📋 [Tool result] {result}")
                        except Exception as e:
                            result = f"Error: {e}"
                            print(f"   ❌ [Tool error] {result}")
                        
                        await ws.send(json.dumps({
                            "type": "tool_response",
                            "id": tool_id,
                            "name": name,
                            "response": result
                        }))
                        
            except websockets.exceptions.ConnectionClosed as e:
                print(f"\n   ⚠️  Connection closed: {e}")
                turn_done.set()  # Unblock main loop
            except Exception as e:
                print(f"\n   ❌ Receive error: {e}")
                traceback.print_exc()
                turn_done.set()
        
        # Start receive loop in background
        recv_task = asyncio.create_task(receive_loop())
        
        try:
            # Wait a moment for the initial connection to stabilize
            await asyncio.sleep(2)
            
            for i, wav_path in enumerate(wav_files):
                turn_done.clear()
                
                print(f"\n{'='*60}")
                print(f"  FILE {i+1}/{len(wav_files)}: {os.path.basename(wav_path)}")
                print(f"{'='*60}")
                
                # Send the audio file
                await send_audio_file(ws, wav_path)
                
                # Wait for Gemini to fully respond (turn_complete or reconnect)
                print("   ⏳ Waiting for Gemini to respond...")
                try:
                    await asyncio.wait_for(turn_done.wait(), timeout=120)
                except asyncio.TimeoutError:
                    print("   ⚠️  Timeout waiting for response (120s) — moving on")
                
                # Pause between files to let things settle
                print("   ⏸️  Pausing 3s before next file...")
                await asyncio.sleep(3)
            
            print(f"\n{'='*60}")
            print(f"  ALL {len(wav_files)} FILES COMPLETE")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n❌ Test error: {e}")
            traceback.print_exc()
        finally:
            test_complete.set()
            recv_task.cancel()
            try:
                await recv_task
            except asyncio.CancelledError:
                pass
    
    # Clean up audio
    if AUDIO_OUT is not None:
        try:
            AUDIO_OUT.stop()
            AUDIO_OUT.close()
        except Exception:
            pass


if __name__ == "__main__":
    print("=== Automated Audio Sequence Test ===\n")
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"\nFatal error: {e}")
        traceback.print_exc()
