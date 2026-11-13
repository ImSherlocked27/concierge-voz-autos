"""Populate non-key local settings without printing secrets or changing the API key."""
import argparse
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv, set_key

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--voice-id", required=True)
    args = parser.parse_args()
    env = ROOT / ".env"
    if not env.exists():
        raise SystemExit("Create .env from .env.example and connect ElevenLabs first")
    load_dotenv(env)
    for name, value in {"API_BASE": args.api_base.rstrip("/"), "VOICE_ID": args.voice_id,
                        "TOOLS_SECRET": os.getenv("TOOLS_SECRET") or secrets.token_urlsafe(32),
                        "DEMO_ACCESS_CODE": os.getenv("DEMO_ACCESS_CODE") or secrets.token_urlsafe(12)}.items():
        set_key(str(env), name, value)
    print("Local settings saved. API key preserved. Access code stays in .env; no secrets printed.")


if __name__ == "__main__":
    main()
