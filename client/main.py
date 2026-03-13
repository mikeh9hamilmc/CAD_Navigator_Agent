import asyncio
import json
import base64
import websockets
from media_streams import MediaStreamer
from solidworks_tools import execute_tool

CLOUD_RUN_URI = "ws://cad-navigator-backend-abc123-uc.a.run.app/ws" #this is just a fake URI, replace it with your own Cloud Run URI (see CLOUD_RUN.md for instructions)
LOCAL_URI     = "ws://localhost:8080/ws"
SERVER_URI = CLOUD_RUN_URI  # Switch to LOCAL_URI for local Docker testing

async def ws_handler():
    while True:
        try:
            print(f"Connecting to backend {SERVER_URI}...")
            async with websockets.connect(SERVER_URI, ping_interval=None, ping_timeout=None) as ws:
                print("Connected to backend!")
                streamer = MediaStreamer(ws)
                
                # Create independent tasks for all asynchronous loops
                audio_task = asyncio.create_task(streamer.stream_audio_in())
                video_task = asyncio.create_task(streamer.stream_screen_context())
                
                async def message_loop():
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        # Handle incoming audio payload from Gemini
                        if data.get("type") == "audio" and "data" in data:
                            pcm_data = base64.b64decode(data["data"])
                            streamer.play_audio(pcm_data)
                            
                        # Handle incoming text from Gemini
                        elif data.get("type") == "text":
                            print(f"[Agent says]: {data['text']}")

                        # Gemini has finished its turn — ready for next command
                        elif data.get("type") == "turn_complete":
                            print("\n\n🎙️ Listening for commands...\n")
                        
                        # Status updates from server (e.g. Gemini reconnecting)
                        elif data.get("type") == "status":
                            print(f"[Server]: {data.get('message', '')}")
                            
                        # Handle incoming tool execution request from Gemini
                        elif data.get("type") == "tool_call":
                            tool_id = data.get("id")
                            name = data.get("name")
                            args = data.get("args", {})
                            print(f"[Agent requested Tool] {name}({args})")
                            
                            # Execute the tool against the local SolidWorks instance
                            response = await execute_tool(name, args)
                            print(f"[Tool Response] {response}")
                            
                            # Send the result back to Gemini so it understands what happened
                            await ws.send(json.dumps({
                                "type": "tool_response",
                                "id": tool_id,
                                "name": name,
                                "response": response
                            }))

                message_task = asyncio.create_task(message_loop())
                
                try:
                    # Run all tasks concurrently. return_exceptions=True prevents one crash
                    # from taking down the whole connection silently.
                    results = await asyncio.gather(
                        audio_task, video_task, message_task,
                        return_exceptions=True
                    )
                    for i, r in enumerate(results):
                        if isinstance(r, Exception):
                            print(f"Task {i} failed with: {type(r).__name__}: {r}")
                except Exception as e:
                    print(f"Gather exception caught: {e}")
                finally:
                    # Cleanly shut down all tasks when the connection inevitably drops
                    audio_task.cancel()
                    video_task.cancel()
                    message_task.cancel()
                    streamer.close()
                    
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 3s...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(ws_handler())
