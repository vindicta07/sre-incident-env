"""OpenEnv-compatible server entrypoint wrapping the existing FastAPI app."""

from __future__ import annotations

import argparse
import os

import uvicorn

from api.main import app


def main() -> None:
    """Run the FastAPI app with CLI-overridable host and port."""
    parser = argparse.ArgumentParser(description="Run the SRE Incident Environment server.")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "7860")),
    )
    args = parser.parse_args()

    uvicorn.run("server.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
