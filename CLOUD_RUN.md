# CAD Navigator Agent — Google Cloud Run Deployment Guide

This document explains how to deploy the **CAD Navigator Agent backend** to Google Cloud Run, how the Gemini API key is handled securely, and how to set up continuous deployment from GitHub.

---

## 🚀 Quick Deploy (Shortcut)

For subsequent redeployments, you can use the automated Python script located in the root directory:

1. **Run the script**:
   ```bash
   python deploy.py
   ```
This script handles project activation, Docker build, Artifact Registry push, and Cloud Run deployment automatically.

---

## Architecture

```
Local Windows Client (client.py)
        │  WebSocket  ws://
        ▼
Cloud Run Service (FastAPI/uvicorn)
  backend/server.py  ──────────────────► Gemini Live API (WebSocket)
        │  GEMINI_API_KEY from Secret Manager
```

The backend is a **stateful Python WebSocket server** that:
1. Accepts a WebSocket connection from the local Windows client.
2. Opens a Gemini Live API session using the injected `GEMINI_API_KEY`.
3. Proxies audio, video frames, and tool calls bidirectionally.

The Gemini key is used **at runtime** by the Python server — it is never baked into a container image. 
It is injected as a Cloud Run environment variable sourced from Google Secret Manager.

---

## Prerequisites

- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated.
- Docker Desktop installed (for local testing only).
- A Google Cloud project with billing enabled.

---

## Step-by-Step Setup

### Step 1 — Create or select your Google Cloud project

```bash
# List your projects
gcloud projects list

# Set your active project (replace PROJECT_ID with yours)
gcloud config set project PROJECT_ID
```

---

### Step 2 — Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

---

### Step 3 — Create an Artifact Registry repository

Cloud Run pulls images from Artifact Registry (not Docker Hub).

```bash
gcloud artifacts repositories create cad-navigator \
  --repository-format=docker \
  --location=us-central1 \
  --description="CAD Navigator Agent container images"
```

---

### Step 4 — Store the Gemini API key in Secret Manager

The key is **never** a build argument or environment variable in source code. It lives in Secret Manager and is mounted as an env var at Cloud Run deploy time.

```bash
# Create the secret  (you'll be prompted to enter the key value)
echo -n "YOUR_GEMINI_API_KEY_HERE" | \
  gcloud secrets create GEMINI_API_KEY \
    --data-file=- \
    --replication-policy=automatic
```

To update the key later:
```bash
echo -n "NEW_KEY_VALUE" | \
  gcloud secrets versions add GEMINI_API_KEY --data-file=-
```

---

### Step 5 — Build and push the Docker image manually (first deploy)

Authenticate Docker to Artifact Registry, then build and push:

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev

docker build -t us-central1-docker.pkg.dev/PROJECT_ID/cad-navigator/backend:latest .

docker push us-central1-docker.pkg.dev/PROJECT_ID/cad-navigator/backend:latest
```

#### Local test before pushing (optional but recommended)

```bash
docker build -t cad-navigator-backend .

docker run --rm \
  -e GEMINI_API_KEY=your_key_here \
  -p 8080:8080 \
  cad-navigator-backend
```

Then start the local client pointing at `ws://localhost:8080/ws` to verify end-to-end.

---

### Step 6 — Deploy to Cloud Run

```bash
gcloud run deploy cad-navigator-backend \
  --image=us-central1-docker.pkg.dev/PROJECT_ID/cad-navigator/backend:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest \
  --min-instances=0 \
  --max-instances=3 \
  --timeout=3600
```

Key flags explained:

| Flag | Reason |
|---|---|
| `--allow-unauthenticated` | Local client connects without a Google identity token |
| `--port=8080` | Must match `EXPOSE 8080` in the Dockerfile |
| `--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest` | Mounts the secret as an env var at runtime |
| `--timeout=3600` | WebSocket sessions can last hours; default 300 s would kill them |
| `--min-instances=0` | Scales to zero when idle (cost saving) |
| `--max-instances=3` | Caps concurrency (each instance handles one session) |

After deploy, the CLI prints a **Service URL** like:
```
https://cad-navigator-backend-abc123-uc.a.run.app
```

Update your local client (`client.py`) to use:
```
ws://cad-navigator-backend-abc123-uc.a.run.app/ws
```
> **Note**: Cloud Run terminates TLS, so use `wss://` from external clients that need secure connections.

---

### Step 7 — Grant Cloud Run access to the secret

The Cloud Run service runs under the **Compute Engine default service account**. Grant it Secret Accessor permission:

```bash
# Get the service account email
gcloud run services describe cad-navigator-backend \
  --region=us-central1 \
  --format="value(spec.template.spec.serviceAccountName)"

# Grant Secret Manager access (replace SA_EMAIL with the output above)
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

If the service is using the default Compute SA, you can use:
```bash
PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Continuous Deployment (GitHub → Cloud Run)

### Step 8 — Connect your GitHub repository

1. Open the [Cloud Run console](https://console.cloud.google.com/run).
2. Click your service → **Edit & Deploy New Revision** → **Continuously deploy new revisions from a source repository**.
3. Click **Set up with Cloud Build** and authorize the GitHub App on your repository.
4. Select the repository `Google-Hackathon-Live-CAD` and branch `main`.
5. Set **Build type** to **Dockerfile** (it auto-detects `Dockerfile` in the repo root).

### Step 9 — Add `cloudbuild.yaml` for Secret Manager integration

Create this file at the repo root so Cloud Build can access the key during the build phase (not needed for the image itself — just for any build-time validation steps):

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'us-central1-docker.pkg.dev/$PROJECT_ID/cad-navigator/backend:$COMMIT_SHA'
      - '-t'
      - 'us-central1-docker.pkg.dev/$PROJECT_ID/cad-navigator/backend:latest'
      - '.'

  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - '--all-tags'
      - 'us-central1-docker.pkg.dev/$PROJECT_ID/cad-navigator/backend'

  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'cad-navigator-backend'
      - '--image=us-central1-docker.pkg.dev/$PROJECT_ID/cad-navigator/backend:$COMMIT_SHA'
      - '--region=us-central1'
      - '--platform=managed'
      - '--allow-unauthenticated'
      - '--port=8080'
      - '--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest'
      - '--timeout=3600'

images:
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/cad-navigator/backend'
```

> The `GEMINI_API_KEY` does **not** appear in this file. It is mounted into the running Cloud Run container by the `--set-secrets` flag — not the build step.

---

## API Key Security

```
Secret Manager (Google Cloud)
        │
        ▼  mounted at deploy time (not build time)
Cloud Run runtime environment  →  os.getenv("GEMINI_API_KEY")  →  genai.Client()
```

| Concern | Detail |
|---|---|
| **Key never in source code** | `server.py` reads `os.getenv("GEMINI_API_KEY")` — no hardcoded value |
| **Key never in Git** | `.env.local` is gitignored; the Docker image has no key baked in |
| **Key never in image layers** | No `ARG` / `ENV` in the Dockerfile; `docker inspect` reveals nothing |
| **Key never in Cloud Build logs** | It's not a substitution variable — it's a Secret Manager reference |
| **Recommend: API key restriction** | In Google AI Studio, restrict the key to the Cloud Run service IP or add an API quota to limit blast radius |

---

## Files Required for Deployment

| File | Required? | Reason |
|---|---|---|
| `Dockerfile` | ✅ Essential | Defines the Python container |
| `.dockerignore` | ✅ Essential | Keeps the image small and secrets out |
| `backend/server.py` | ✅ Essential | FastAPI WebSocket server — the application |
| `backend/agent.py` | ✅ Essential | Gemini agent configuration and tool definitions |
| `backend/requirements.txt` | ✅ Essential | Python dependencies installed by `pip` in Docker |
| `cloudbuild.yaml` | ✅ For CI/CD | Only needed if using Cloud Build continuous deployment |
| `.env.local` | ❌ Not deployed | Local dev only; gitignored |
| `backend/venv/` | ❌ Not committed | Rebuilt by pip inside Docker |
| `client/` | ❌ Not deployed | Runs on the local Windows machine only |
| `tools/` | ❌ Not deployed | Automated testing audio clips |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `WebSocket connection failed` from client | Cloud Run URL is `https://` not `wss://` | Change client URL scheme to `wss://` |
| `GEMINI_API_KEY is missing` in Cloud Run logs | Secret not mounted or wrong IAM role | Re-check Step 7 IAM binding |
| Connection closes after 5 minutes | Cloud Run request timeout too short | Ensure `--timeout=3600` is set |
| `port 8080 already in use` locally | Another process using 8080 | `docker run -p 9090:8080 ...` and update client port |
