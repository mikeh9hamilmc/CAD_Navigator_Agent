# AGENTS.md: SolidWorks UI Navigator Agent

## 🎯 Project Objective
Build a real-time, multimodal AI agent that acts as an interactive mechanical engineering and CAD assistant. The agent must visually monitor the user's Windows desktop (specifically the 3DEXPERIENCE SOLIDWORKS for Makers environment), listen to live voice commands, provide spoken feedback, and autonomously execute design actions within the CAD software. 

This project is a submission for the "Gemini Live Agent Challenge" (UI Navigator track) and must strictly adhere to the contest's required tech stack.

## 🛠️ Required Tech Stack
* **Core AI:** Google Gemini Live API (for bidirectional streaming audio and real-time vision).
* **Orchestration:** Google Agent Development Kit (ADK) for Python.
* **Target Application:** 3DEXPERIENCE SOLIDWORKS for Makers (Windows environment).
* **Cloud Hosting:** Google Cloud Run (must host the backend/agent logic to satisfy the Google Cloud Service requirement).
* **Local Client:** A Python-based desktop client to capture screen/audio and relay it to the Cloud Run backend via WebSockets/gRPC.



## 🧠 Core Agent Definition
**Name:** `CAD_Navigator_Agent`
**Role:** Expert Mechanical Engineer and SolidWorks UI Assistant.
**Behavioral Requirements:**
1.  Continuously ingest 1 FPS screen captures of the active SolidWorks window to maintain visual context.
2.  Listen to streaming audio input for user commands or questions (e.g., "Start a sketch on the front plane," or "Does this chamfer look right?").
3.  Respond via native streaming audio output, offering conversational design advice or confirming actions.
4.  Autonomously select and execute registered Python tools to interact with the SolidWorks GUI or API based on user intent.

## 🧰 Required Tools (Agent Capabilities)
The agent must be equipped with the following toolsets to affect the desktop environment:

### Toolset A: Local Input/Output Streams (Client-Side)
* **`stream_screen_context()`**: Captures the primary Windows display at ~1 FPS, compresses the frame, and pushes it to the agent's multimodal input stream.
* **`stream_audio_in()`**: Captures microphone input and pushes it to the Gemini Live API.
* **`stream_audio_out()`**: Plays the generated audio responses from Gemini through the local speakers.

### Toolset B: SolidWorks Actuators (Agent-Side)
These tools must be exposed to the ADK agent so it can physically control the CAD software. Implementation should prefer the SolidWorks COM API where possible, falling back to GUI automation (`pywinauto` / `pyautogui`) for UI-specific clicks.
* **`create_new_part()`**: Initializes a new SolidWorks part document.
* **`select_plane(plane_name: str)`**: Selects the Front, Top, or Right plane based on visual context or explicit command.
* **`start_sketch()`**: Activates the sketching environment on the currently selected plane or face.
* **`draw_shape(shape_type: str, dimensions: dict)`**: Uses SolidWorks API commands to sketch basic entities (lines, circles, rectangles) based on inferred or provided dimensions.
* **`apply_feature(feature_type: str, parameters: dict)`**: Executes 3D features (e.g., "extrude_boss", "cut_extrude") using the active sketch.
* **`analyze_ui_state()`**: A diagnostic tool that forces the agent to read the screen (e.g., checking if a sketch is fully defined or under-defined) and report back to the user verbally.

## 🚀 Deployment Constraints & Architecture
1.  **Backend (Cloud Run):** The ADK `CAD_Navigator_Agent` and the SolidWorks tool definitions must be containerized and deployed to Google Cloud Run. This backend handles the LLM logic, tool decision-making, and connection to the Gemini Live API.
2.  **Frontend (Local Windows Client):** A lightweight Python script runs locally on the user's machine. It handles the I/O (screen capture, mic, speaker) and establishes a low-latency connection to the Cloud Run backend. 
3.  **Local Tool Execution:** Because SolidWorks runs locally, the backend agent must send an execution payload (e.g., JSON specifying which tool to run and its arguments) back to the local client, which actually fires the `pywinauto` or COM API commands.

## 🏆 Hackathon Winning Criteria Focus
* **Multimodal UX (40%):** The code must ensure seamless, conversational audio interruption and low-latency visual understanding.
* **Innovation (40%):** The tool implementation must bridge complex mechanical engineering software with natural language, demonstrating a leap beyond simple chat interfaces.

## 📅 Progress Log: March 11, 2026
* **Robust Gemini Live Connection:** Implemented an auto-reconnect strategy (`manage_gemini_session`) in the FastAPI backend to seamlessly recover from normal session closures (Code 1000) that occur on the `native-audio` model after tool calls. Reconnections are now instant and invisible to the client.
* **Media Stream Synchronization:** Fixed the `1008` (policy violation) connection drop by pausing audio and image WebSocket streams from the client while the model processes and responds to tool execution. Streams now accurately resume only when the `turn_complete` signal is received from Gemini.
* **System Prompt Optimization:** Rewrote the agent's system prompt to force immediate tool execution. The model now prioritizes firing the SolidWorks tool API call over narrating its thought process, saving valuable session time and preventing timeouts.
* **Automated Audio Test Client:** Built `test_audio_sequence.py` and `record_command.py` to facilitate rapid, reproducible testing. The test client sequentially streams pre-recorded voice commands (`.wav` files) to the backend, accurately simulating a live user session to validate complex, multi-turn tool chains (e.g., *New Part -> Select Plane -> Start Sketch -> Draw Shape -> Extrude*).