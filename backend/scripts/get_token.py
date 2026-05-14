import urllib.request, json, os, sys

_here = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(_here, "..", ".env")

config = {}
try:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
except FileNotFoundError:
    print(f"ERROR: .env not found at {env_path}")
    sys.exit(1)

supabase_url = config.get("SUPABASE_URL", "").rstrip("/")
supabase_key = config.get("SUPABASE_KEY", "")

if not supabase_url or not supabase_key:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in backend/.env")
    sys.exit(1)

email = input("Email: ")
password = input("Password: ")

req = urllib.request.Request(
    f"{supabase_url}/auth/v1/token?grant_type=password",
    data=json.dumps({"email": email, "password": password}).encode(),
    headers={"apikey": supabase_key, "Content-Type": "application/json"},
    method="POST",
)

try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    print("\nACCESS TOKEN:")
    print(data["access_token"])
except urllib.error.HTTPError as e:
    print(f"ERROR {e.code}: {e.read().decode()}")
    sys.exit(1)
