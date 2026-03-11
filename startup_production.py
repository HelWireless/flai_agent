#!/usr/bin/env python3
import subprocess
import sys
import os
os.chdir("c:/Users/cody/PycharmProjects/flai_agent")
print("Starting Flai Agent in production mode...")
print("Current directory:", os.getcwd())
print("Config: config/config.yaml")

workers = "4"
cmd = ["py", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0",
    "--port", "8000", "--workers", workers]

try:
    print("Running command:", " ".join(cmd))
    print("Press Ctrl+C to stop the server")
    subprocess.run(cmd, check=True)
except subprocess.CalledProcessError as e:
    print(f"Failed to start FastAPI application: {e}", file=sys.stderr)
    sys.exit(1)
except KeyboardInterrupt:
    print("\nServer stopped by user (Ctrl+C)")
    sys.exit(0)
