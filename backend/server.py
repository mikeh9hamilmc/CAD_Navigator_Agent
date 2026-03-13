import asyncio
import json
import os
import traceback
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from agent import get_agent_config
from dotenv import load_dotenv

# Load .env.local only when running locally (the file won't exist in Docker/Cloud Run)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env.local')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

app = FastAPI()

# Ensure GEMINI_API_KEY is available
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "your_gemini_api_key_here":
    print("WARNING: GEMINI_API_KEY is missing or not configured correctly in .env.local.")

client = genai.Client(api_key=api_key)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Local client connected to backend")
    
    config = get_agent_config()
    
    # Shared mutable state accessed by both coroutines
    session_holder = {"session": None}
    waiting_for_tool_response = False
    session_ready = asyncio.Event()
    client_disconnected = asyncio.Event()

    async def manage_gemini_session():
        """Maintains a Gemini Live session, auto-reconnecting when it drops."""
        nonlocal waiting_for_tool_response
        
        while not client_disconnected.is_set():
            try:
                async with client.aio.live.connect(
                    model="gemini-2.5-flash-native-audio-preview-12-2025", config=config
                ) as gemini_session:
                    print("Connected to Gemini Live API")
                    session_holder["session"] = gemini_session
                    waiting_for_tool_response = False  # Reset on fresh session
                    # Brief delay to let the session fully initialize before
                    # accepting audio/image (prevents 1008 on first connect)
                    await asyncio.sleep(0.3)
                    session_ready.set()
                    
                    try:
                        async for response in gemini_session.receive():
                            server_content = response.server_content
                            if server_content is not None:
                                if server_content.model_turn is not None:
                                    for part in server_content.model_turn.parts:
                                        if part.inline_data:
                                            audio_b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                                            await websocket.send_json({"type": "audio", "data": audio_b64})
                                        elif part.text:
                                            await websocket.send_json({"type": "text", "text": part.text})
                                
                                if server_content.turn_complete:
                                    if waiting_for_tool_response:
                                        waiting_for_tool_response = False
                                        print("▶️  Turn complete — resuming audio/image streaming")
                                    await websocket.send_json({"type": "turn_complete"})

                            # Handle tool calls — pause audio/image forwarding
                            if response.tool_call is not None:
                                waiting_for_tool_response = True
                                print("⏸️  Pausing audio/image — waiting for tool response")
                                for call in response.tool_call.function_calls:
                                    print(f"🔧 Tool call: {call.name}")
                                    await websocket.send_json({
                                        "type": "tool_call",
                                        "id": call.id,
                                        "name": call.name,
                                        "args": call.args
                                    })
                    except Exception as e:
                        print(f"Gemini receive stream ended: {e}")
                        
            except Exception as e:
                print(f"Gemini session error: {e}")
                traceback.print_exc()
            
            # Session ended — clear references and reconnect immediately
            session_holder["session"] = None
            session_ready.clear()
            waiting_for_tool_response = False
            
            if not client_disconnected.is_set():
                print("🔄 Gemini session ended — reconnecting immediately...")

    async def receive_from_client():
        """Receives from client WebSocket, forwards to whatever Gemini session is active."""
        nonlocal waiting_for_tool_response
        try:
            while True:
                message = await websocket.receive()
                if "text" in message:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")
                    
                    # Skip audio/image while waiting for tool response or no session
                    if msg_type in ("audio", "image"):
                        if waiting_for_tool_response or not session_ready.is_set():
                            continue
                        
                        session = session_holder["session"]
                        if session is None:
                            continue
                        
                        try:
                            if msg_type == "audio":
                                audio_bytes = base64.b64decode(data["data"])
                                await session.send_realtime_input(
                                    media=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                                )
                            else:
                                img_bytes = base64.b64decode(data["data"])
                                await session.send_realtime_input(
                                    media=types.Blob(data=img_bytes, mime_type="image/jpeg")
                                )
                        except Exception as e:
                            # Session probably closed mid-send, the reconnect loop will handle it
                            print(f"Send to Gemini failed (will reconnect): {e}")
                            continue
                    
                    elif msg_type == "tool_response":
                        # Tool responses are critical — wait for session if needed
                        if not session_ready.is_set():
                            print("Waiting for Gemini session before sending tool response...")
                            await session_ready.wait()
                        
                        session = session_holder["session"]
                        if session is not None:
                            try:
                                print(f"📤 Sending tool response: {data['name']}")
                                await session.send_tool_response(
                                    function_responses=[types.FunctionResponse(
                                        name=data["name"],
                                        id=data["id"],
                                        response={"result": data["response"]}
                                    )]
                                )
                                # Do NOT resume audio/image here — wait for turn_complete
                                # so Gemini can finish generating its response undisturbed
                            except Exception as e:
                                print(f"Failed to send tool response: {e}")
                                waiting_for_tool_response = False
                                
        except WebSocketDisconnect:
            print("Local client disconnected")
        except Exception as e:
            print(f"Error receiving from local client: {e}")
        finally:
            client_disconnected.set()

    try:
        await asyncio.gather(manage_gemini_session(), receive_from_client())
    except Exception as e:
        print(f"Session error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, ws_ping_interval=None, ws_ping_timeout=None)
