"""Smoke-test available Gemini models against the configured API key."""
import os, sys
from google import genai

_here = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(_here, "..", ".env")

key = None
try:
    with open(env_path) as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                key = line.split("=", 1)[1].strip()
                break
except FileNotFoundError:
    print(f"ERROR: .env not found at {env_path}")
    sys.exit(1)

if not key:
    print("ERROR: GEMINI_API_KEY not found in backend/.env")
    sys.exit(1)

client = genai.Client(api_key=key)

print("Models that support generateContent:")
for model in client.models.list():
    if "generateContent" in (model.supported_actions or []):
        print(f"  {model.name}")

for model_id in ("gemini-2.0-flash-lite", "gemini-1.5-flash-latest"):
    print(f"\nTesting {model_id}...")
    try:
        r = client.models.generate_content(model=model_id, contents="Say hello in one word")
        print(f"  OK: {r.text}")
    except Exception as e:
        print(f"  FAIL: {e}")
