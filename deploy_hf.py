"""
One-command deploy to a private Hugging Face Space.

Usage:
    pip install huggingface_hub
    export HF_TOKEN=hf_...            # a WRITE token; never commit it or paste it in chat
    export APP_PASSWORD='choose-one'  # the login password for the hosted app
    python deploy_hf.py [space-name]  # default: video-finder

Windows (PowerShell):  $env:HF_TOKEN="hf_..." ; $env:APP_PASSWORD="..."
"""
import os
import sys

from huggingface_hub import HfApi

token = os.environ.get("HF_TOKEN")
password = os.environ.get("APP_PASSWORD")
if not token or not password:
    sys.exit("Set HF_TOKEN and APP_PASSWORD environment variables first (see the top of this file).")

name = sys.argv[1] if len(sys.argv) > 1 else "video-finder"
api = HfApi(token=token)
user = api.whoami()["name"]
repo = f"{user}/{name}"

api.create_repo(repo, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
api.add_space_secret(repo, "APP_PASSWORD", password)
if os.environ.get("APP_USER"):
    api.add_space_secret(repo, "APP_USER", os.environ["APP_USER"])

api.upload_folder(
    folder_path=os.path.dirname(os.path.abspath(__file__)),
    repo_id=repo,
    repo_type="space",
    allow_patterns=["app.py", "requirements.txt", "Dockerfile", "README.md", ".dockerignore"],
)

print(f"Uploaded. Build takes ~5-10 min: https://huggingface.co/spaces/{repo}")
print("Login: username 'admin' (or your APP_USER) and the APP_PASSWORD you set.")
