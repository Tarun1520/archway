"""
Start the Archway backend for development.

How to run (from the project root)
    backend/.venv/bin/python backend/run.py

Then open
    http://localhost:8000/api/health   a quick "is it running?" check
    http://localhost:8000/docs         an interactive page listing every endpoint

LEARNING NOTE: what is uvicorn?
    FastAPI describes the app; uvicorn is the server program that actually
    listens for requests and hands them to the app.

    - "app.main:create_app" means: in the module app.main, call create_app.
    - factory=True tells uvicorn that create_app is a function to CALL, not a
      ready-made app object.
    - reload=True restarts the server whenever you save a Python file.
    - host "127.0.0.1" means only this computer can connect. That is the
      right choice for a local-first app.
"""

from pathlib import Path

import uvicorn

# The folder this file lives in (.../backend), as a full path. Using full
# paths means the server starts correctly no matter which folder you run the
# command from.
BACKEND_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        app_dir=str(BACKEND_DIR),  # where to find the `app` package
        reload=True,
        reload_dirs=[str(BACKEND_DIR / "app")],  # only watch our own code
        # LEARNING NOTE: why a shutdown time limit?
        #   The live-progress stream keeps a connection open for as long as a
        #   browser tab is watching. When the server stops or reloads, it
        #   normally waits for open connections to finish, and a stream never
        #   does. This tells it to wait at most 2 seconds, then close them.
        #   The browser reconnects by itself and continues from the last
        #   event it saw, so nothing is lost.
        timeout_graceful_shutdown=2,
    )
