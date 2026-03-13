import subprocess
import sys
import os

PROJECT_ID = "ui-cad-navigator-agent"
REGION = "us-central1"
REPO_NAME = "cad-navigator"
IMAGE_NAME = "backend"
SERVICE_NAME = "cad-navigator-backend"

def run_command(command, shell=True):
    print(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=shell, check=True, text=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return False

def check_auth():
    print("--- Checking Google Cloud Authentication ---")
    try:
        # Fails if not logged in
        subprocess.run("gcloud auth print-access-token", shell=True, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        print("❌ Not logged into Google Cloud.")
        print("Please run: gcloud auth login")
        return False

def deploy():
    # 0. Check authentication
    if not check_auth():
        return

    # 1. Set the project
    print(f"--- Activating Google Cloud Project: {PROJECT_ID} ---")
    if not run_command(f"gcloud config set project {PROJECT_ID}"):
        print("Failed to set project. Aborting.")
        return

    # 2. Configure Docker authentication
    print(f"--- Configuring Docker authentication for {REGION} ---")
    if not run_command(f"gcloud auth configure-docker {REGION}-docker.pkg.dev --quiet"):
        print("Failed to configure docker auth. Aborting.")
        return

    # 3. Build the Docker image
    IMAGE_TAG = f"{REGION}-docker.pkg.dev/{PROJECT_ID}/{REPO_NAME}/{IMAGE_NAME}:latest"
    print(f"--- Building Docker image: {IMAGE_TAG} ---")
    if not run_command(f"docker build -t {IMAGE_TAG} ."):
        print("Docker build failed. Aborting.")
        return

    # 4. Push the Docker image
    print(f"--- Pushing Docker image to Artifact Registry ---")
    if not run_command(f"docker push {IMAGE_TAG}"):
        print("Docker push failed. Aborting.")
        return

    # 5. Deploy to Cloud Run
    print(f"--- Deploying {SERVICE_NAME} to Cloud Run ---")
    deploy_cmd = (
        f"gcloud run deploy {SERVICE_NAME} "
        f"--image={IMAGE_TAG} "
        f"--region={REGION} "
        f"--platform=managed "
        f"--allow-unauthenticated "
        f"--port=8080 "
        f"--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest "
        f"--min-instances=0 "
        f"--max-instances=3 "
        f"--timeout=3600 "
        f"--quiet"
    )
    if not run_command(deploy_cmd):
        print("Cloud Run deployment failed.")
        return

    print("\n✅ Deployment complete!")
    print(f"Service URL will be visible in the gcloud output above.")

if __name__ == "__main__":
    deploy()
