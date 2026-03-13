# GeminiCAD Live 🚀

**Elevator Pitch:** Empower your engineering with GeminiCAD: A multimodal agent that sees your screen and commands SolidWorks in real-time. Speak your design, watch it build, and let Gemini handle the clicks.

GeminiCAD Live is a real-time, multimodal AI agent built for the Google Gemini Live Agent Challenge. It acts as an interactive mechanical engineering and CAD assistant, visually monitoring your SolidWorks environment and executing design actions via voice commands.

---

## 🏗️ Architecture

- **Backend (Google Cloud Run):** A Python FastAPI/uvicorn server that orchestrates the Gemini Live API session and tool logic.
- **Client (Local Windows):** A Python script that captures screen/audio and relays it to the backend. It also executes SolidWorks commands locally via the COM API.

---

## 🛠️ Getting Started

### Prerequisites

- Python 3.12+
- SolidWorks (installed on the local machine for actuation)
- Google Cloud Project (for Gemini API access and Cloud Run deployment)
- Docker (for local container testing)

### 1. Configure the Gemini API Key

Create a `.env.local` file in the root directory (this is gitignored):

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

---

## 💻 Local Testing

You can run the entire stack locally for development and rapid testing.

### A. Run Backend Locally (Directly)

1. Open a terminal in the `backend/` directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the server:
   ```bash
   python server.py
   ```
   - The server will listen on `ws://localhost:8080/ws` by default.

### B. Run Backend Locally (Docker)

1. Build the image:
   ```bash
   docker build -t cad-navigator-backend .
   ```
2. Run the container (replace `YOUR_KEY` with your actual Gemini API key):
   ```bash
   docker run --rm -it -p 8080:8080 -e GEMINI_API_KEY=YOUR_KEY cad-navigator-backend
   ```

### C. Run the Local Client

1. Open a terminal in the `client/` directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. In `main.py`, ensure `SERVER_URI` is set to `LOCAL_URI`:
   ```python
   SERVER_URI = LOCAL_URI
   ```
4. Run the client:
   ```bash
   python main.py
   ```

---

## ☁️ Cloud Testing (Google Cloud Run)

To test the system with the backend hosted on Google Cloud Run:

### 1. Deploy the Backend
Follow the detailed **[Cloud Run Deployment Guide](./CLOUD_RUN.md)** to set up Artifact Registry, Secret Manager, and the Cloud Run service.

### 2. Connect the Local Client
1. Once deployed, obtain your Cloud Run Service URL (e.g., `https://your-service-abc.a.run.app`).
2. In `client/main.py`, update `CLOUD_RUN_URI` with your service URL (ensuring you use `wss://`):
   ```python
   CLOUD_RUN_URI = "wss://your-service-abc-uc.a.run.app/ws"
   SERVER_URI = CLOUD_RUN_URI
   ```
3. Run the client:
   ```bash
   python main.py
   ```

---

## 📄 Project Documentation

- **[PROJECT_DETAILS.md](./PROJECT_DETAILS.md):** High-level vision, core features, and technical breakdown.
- **[CLOUD_RUN.md](./CLOUD_RUN.md):** Step-by-step technical guide for GCP deployment and security.
- **[AGENTS.md](./AGENTS.md):** Detailed agent definition, tool capabilities, and project progress log.
